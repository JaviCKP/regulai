"""SDK backend for arbitrary code; every command crosses the isolated runner."""
import base64
import asyncio
import json
from pathlib import PurePosixPath
import shlex
import uuid

from deepagents.backends.protocol import ExecuteResponse, FileDownloadResponse, FileUploadResponse, EditResult
from langchain_e2b import E2BSandbox


def valid_path(path, *, write=False):
    p = PurePosixPath(path)
    roots = ('/workspace/work/', '/workspace/output/') if write else ('/workspace/', '/skills/')
    if (not p.is_absolute() or '..' in p.parts or '\\' in path or '\x00' in path
            or not (str(p) + '/').startswith(roots)):
        raise ValueError('Workspace path denied')
    return str(p)


class WorkspaceSandbox(E2BSandbox):
    def __init__(self, *, sandbox, limits, lease):
        super().__init__(sandbox=sandbox, workdir='/workspace/work', timeout=limits['command_seconds'])
        self.limits, self.lease = limits, lease

    def execute(self, command, *, timeout=None):
        self.lease.check()
        if not isinstance(command, str) or len(command.encode()) > 200000:
            raise ValueError('Command size limit')
        seconds = min(timeout or self.limits['command_seconds'], self.limits['command_seconds'])
        if seconds < 1:
            raise ValueError('Command timeout must be positive')
        payload = base64.b64encode(json.dumps({'command': command, 'limits': self.limits, 'timeout': seconds}).encode()).decode()
        response = self._sandbox.commands.run('python -I /skills/sandbox_runner.py ' + shlex.quote(payload),
            user='user', timeout=seconds + 10)
        self.lease.check()
        value = json.loads(response.stdout)
        return ExecuteResponse(output=json.dumps(value, ensure_ascii=False), exit_code=value['exit_code'], truncated=value['truncated'])

    def _part(self, path, body, flags, *, parents=False):
        # Open every component with O_NOFOLLOW. Native SDK uploads/downloads would
        # follow user-controlled symlinks outside the command's namespace.
        code = '''import os,base64,json,stat
p=PATH.split('/')[1:]
fd=os.open('/',os.O_RDONLY|os.O_DIRECTORY)
try:
 for part in p[:-1]:
  CREATE
  new=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
  os.close(fd); fd=new
 f=os.open(p[-1],FLAGS|os.O_NOFOLLOW,0o600,dir_fd=fd)
 try:
  if not stat.S_ISREG(os.fstat(f).st_mode): raise ValueError('regular file required')
  BODY
 finally: os.close(f)
finally: os.close(fd)
'''
        code = code.replace('PATH', repr(path))
        create = "try: os.mkdir(part,0o700,dir_fd=fd)\n  except FileExistsError: pass" if parents else 'pass'
        code = code.replace('CREATE', create).replace('FLAGS', flags).replace('BODY', body)
        response = self.execute('python -I -c ' + shlex.quote(code), timeout=30)
        result = json.loads(response.output)
        if result['exit_code'] or result['truncated']:
            raise ValueError('Workspace file unavailable: ' + result['stderr'][:500])
        return result['stdout']

    def _file(self, path, content=None):
        path = valid_path(path, write=content is not None)
        # Chunks stay below command/output bounds, including base64 expansion.
        chunk_size = min(65536, self.limits['output_bytes'] // 3)
        if content is None:
            stamp = self._part(path, "s=os.fstat(f); print(json.dumps([s.st_ino,s.st_size,s.st_mtime_ns]))", 'os.O_RDONLY')
            identity = json.loads(stamp)
            if identity[1] > self.limits['file_bytes']:
                raise ValueError('Workspace file size limit')
            result = bytearray()
            for start in range(0, identity[1], chunk_size):
                body = (f"s=os.fstat(f); assert [s.st_ino,s.st_size,s.st_mtime_ns]=={identity!r}; "
                    f"os.lseek(f,{start},0); print(base64.b64encode(os.read(f,{chunk_size})).decode())")
                result.extend(base64.b64decode(self._part(path, body, 'os.O_RDONLY').strip(), validate=True))
            if len(result) != identity[1]:
                raise ValueError('Workspace file changed during transfer')
            return bytes(result)
        if len(content) > self.limits['file_bytes']:
            raise ValueError('Workspace file size limit')
        temporary = str(PurePosixPath(path).with_name('.transfer-' + uuid.uuid4().hex))
        try:
            self._part(temporary, 'pass', 'os.O_WRONLY|os.O_CREAT|os.O_EXCL', parents=True)
            for start in range(0, len(content), chunk_size):
                encoded = base64.b64encode(content[start:start + chunk_size]).decode()
                self._part(temporary, f"data=base64.b64decode({encoded!r}); assert os.write(f,data)==len(data)", 'os.O_WRONLY|os.O_APPEND')
            self._part(temporary, f"assert os.fstat(f).st_size=={len(content)}; os.rename(p[-1],{PurePosixPath(path).name!r},src_dir_fd=fd,dst_dir_fd=fd)", 'os.O_RDONLY')
        except Exception:
            try:
                self._part(temporary, 'os.unlink(p[-1],dir_fd=fd)', 'os.O_RDONLY')
            except Exception:
                pass
            raise

    def download_files(self, paths):
        result = []
        for path in paths:
            try:
                result.append(FileDownloadResponse(path=path, content=self._file(path), error=None))
            except (ValueError, OSError):
                result.append(FileDownloadResponse(path=path, content=None, error='permission_denied'))
        return result

    def upload_files(self, files):
        result = []
        for path, content in files:
            try:
                self._file(path, content)
                result.append(FileUploadResponse(path=path, error=None))
            except (ValueError, OSError):
                result.append(FileUploadResponse(path=path, error='permission_denied'))
        return result

    # BaseSandbox parses execute.output as command stdout; unwrap only for its
    # file helpers, leaving the execute tool's full diagnostics intact.
    def _helper(self, name, *args, **kwargs):
        def execute(command, *, timeout=None):
            result = self.execute(command, timeout=timeout)
            value = json.loads(result.output)
            return ExecuteResponse(output=value['stdout'] + value['stderr'], exit_code=result.exit_code, truncated=result.truncated)
        helper = E2BSandbox(sandbox=self._sandbox, workdir='/workspace/work')
        helper.execute = execute
        helper.upload_files = self.upload_files
        helper.download_files = self.download_files
        return getattr(helper, name)(*args, **kwargs)

    def read(self, file_path, offset=0, limit=2000):
        valid_path(file_path)
        # A no-follow preflight also prevents symlink escapes in SDK helper code.
        self._file(file_path)
        return self._helper('read', file_path, offset, min(limit, 1000))

    def ls(self, path):
        return self._helper('ls', valid_path(path))

    def glob(self, pattern, path=None):
        return self._helper('glob', pattern, valid_path(path or '/workspace'))

    def grep(self, pattern, path=None, glob=None):
        return self._helper('grep', pattern, valid_path(path or '/workspace'), glob)

    def write(self, file_path, content):
        return self._helper('write', valid_path(file_path, write=True), content)

    def edit(self, file_path, old_string, new_string, replace_all=False):
        try:
            valid_path(file_path, write=True)
            content = self._file(file_path).decode('utf-8')
            if not old_string:
                return EditResult(error='The text to replace must not be empty.')
            count = content.count(old_string)
            if not count:
                return EditResult(error='The exact text was not found in ' + file_path)
            if count > 1 and not replace_all:
                return EditResult(error='The text occurs more than once; provide more context or replace_all.')
            self._file(file_path, content.replace(old_string, new_string).encode('utf-8'))
            return EditResult(path=file_path, occurrences=count)
        except (ValueError, OSError, UnicodeError) as error:
            return EditResult(error=str(error))

    # BaseSandbox's async file helpers parse stdout directly. Route them through
    # the same validated synchronous helpers, including no-follow transfers.
    async def als(self, path):
        return await asyncio.to_thread(self.ls, path)

    async def aread(self, file_path, offset=0, limit=2000):
        return await asyncio.to_thread(self.read, file_path, offset, limit)

    async def awrite(self, file_path, content):
        return await asyncio.to_thread(self.write, file_path, content)

    async def aedit(self, file_path, old_string, new_string, replace_all=False):
        return await asyncio.to_thread(self.edit, file_path, old_string, new_string, replace_all)

    async def aglob(self, pattern, path=None):
        return await asyncio.to_thread(self.glob, pattern, path)

    async def agrep(self, pattern, path=None, glob=None):
        return await asyncio.to_thread(self.grep, pattern, path, glob)
