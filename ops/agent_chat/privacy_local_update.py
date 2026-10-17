"""Local-only privacy update: backup, isolated clone, prepare, then apply.

Uses the installed web image as its base and retains its private mounts and
worker. No credentials are transferred and no model generation is invoked.
"""
import argparse
import base64
import json
from pathlib import Path
import runpy
import shlex
import subprocess

ROOT = Path(__file__).resolve().parents[2]
SSH = runpy.run_path(str(ROOT / 'ops/agent_chat/p1_activate_local.py'))['SSH']
IDENTITY = 'privacy-20261017-a1'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'apply', 'status', 'sandbox', 'finish'])
    args = parser.parse_args()
    payload = {'action': args.action, 'identity': IDENTITY,
               'helper': (ROOT / 'ops/agent_chat/p1_activation_remote.py').read_text(encoding='utf-8')}
    if args.action == 'prepare':
        folder = ROOT / 'output/privacy-20261017/real-source'
        manifest = json.loads((folder / 'manifest.json').read_text())
        if manifest['conflicts']:
            raise RuntimeError('unresolved_source_conflicts')
        payload['files'] = {p: base64.b64encode((folder/'source'/p).read_bytes()).decode()
                            for p in manifest['paths']}
        payload['baseline'] = {p: row['live_sha256'] for p, row in manifest['paths'].items()}
        extras = ['ops/agent_chat/privacy_demo_account.py', 'regulai/front/security_presets.py']
        extras += [str(p.relative_to(ROOT)).replace('\\','/') for p in (ROOT/'regulai/front').glob('test_privacy_*.py')]
        extras += ['regulai/front/test_security_presets.py', 'regulai/front/test_chat_flow.py']
        for p in extras:
            payload['files'][p] = base64.b64encode((ROOT/p).read_bytes()).decode()
    source = (ROOT / 'ops/agent_chat/privacy_update_remote.py').read_text(encoding='utf-8')
    loader = 'import sys,json; request=json.loads(sys.stdin.buffer.readline()); source=sys.stdin.buffer.read().decode(); exec(compile(source,"privacy_update.py","exec"),{"__name__":"__main__","REQUEST":request})'
    result = subprocess.run([*SSH, 'sudo python3 -c '+shlex.quote(loader)],
        input=json.dumps(payload).encode()+b'\n'+source.encode(), capture_output=True)
    if result.returncode:
        # The remote wrapper emits only a deliberately public error code.
        raise SystemExit(result.stdout.decode(errors='replace')[-1200:] or 'Remote update failed; inspect the private stage log.')
    value = json.loads(result.stdout)
    report = ROOT/'output/privacy-20261017'/('real-'+args.action+'.json')
    report.write_text(json.dumps(value,indent=2),encoding='utf-8')
    print(json.dumps(value,indent=2))


if __name__ == '__main__':
    main()
