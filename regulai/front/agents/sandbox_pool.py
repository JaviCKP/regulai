"""Executor-only one-slot pool of clean E2B environments. Used slots are killed."""
import ipaddress
from pathlib import Path
import threading
import time
import logging
from urllib.parse import urlsplit

from e2b import Sandbox


def e2b_options(config):
    for name in ('api_url', 'sandbox_url'):
        parsed = urlsplit(config[name])
        address = ipaddress.ip_address(parsed.hostname)
        if (parsed.scheme not in ('http', 'https') or not address.is_private
                or address.is_link_local or parsed.username or parsed.password):
            raise ValueError('Explicit private E2B endpoint required')
    return {key: config[key] for key in ('api_url', 'sandbox_url')} | {
        'api_key': Path(config['api_key_file']).read_text().strip(),
        'domain': 'task48.internal', 'debug': False, 'retries': 0, 'request_timeout': 15}


def create_clean(config):
    sandbox = Sandbox.create(template=config['template'], timeout=180,
        allow_internet_access=False,
        network={'deny_out': ['0.0.0.0/0'], 'allow_public_traffic': False}, **e2b_options(config))
    try:
        sandbox.commands.run('printf 1 > /proc/sys/net/ipv6/conf/default/disable_ipv6 && '
            'printf 1 > /proc/sys/net/ipv6/conf/all/disable_ipv6 && '
            'find / -xdev -type f -perm /6000 -exec chmod a-s {} + && '
            # E2B deny_out does not cover its link-local metadata endpoint.
            # The pinned microVM kernel lacks xt_owner. A kernel prohibit route
            # covers link-local metadata for every UID without touching envd.
            'ip route replace prohibit 169.254.0.0/16 && '
            'ip route show type prohibit | grep -q 169.254.0.0/16 && '
            'mount --bind /skills /skills && mount -o remount,bind,ro /skills', user='root', timeout=10)
        sandbox.commands.run('test "$(id -u)" = 1000 && '
            'test -z "$(ls -A /workspace/input)" && test -z "$(ls -A /workspace/work)" && '
            'test -z "$(ls -A /workspace/output)" && '
            'test "$(cat /proc/sys/net/ipv6/conf/all/disable_ipv6)" = 1 && '
            'test "$(cat /proc/sys/net/ipv6/conf/default/disable_ipv6)" = 1', timeout=10)
        return sandbox
    except BaseException:
        sandbox.kill()
        raise


class CleanPool:
    def __init__(self, factory):
        self.factory, self.ready, self.closed = factory, None, False
        self.leased = False
        self.lock = threading.Lock()
        self.wake = threading.Event()
        self.metrics = []
        self.thread = threading.Thread(target=self._prepare, daemon=True)
        self.thread.start()

    def _prepare(self):
        while not self.closed:
            with self.lock:
                ready = self.ready
                leased = self.leased
            if leased:
                self.wake.wait(1)
                self.wake.clear()
                continue
            if ready:
                try:
                    ready.set_timeout(180)
                except Exception:
                    with self.lock:
                        if self.ready is ready:
                            self.ready = None
                    try:
                        ready.kill()
                    except Exception:
                        pass  # Backend TTL is the fallback after a network loss.
                self.wake.wait(30)
                self.wake.clear()
                continue
            try:
                started = time.monotonic()
                ready = self.factory()
                with self.lock:
                    if self.closed or self.ready is not None:
                        ready.kill()
                        if self.closed:
                            return
                        continue
                    self.ready = ready
                    self.metrics.append({'preparation_seconds': time.monotonic() - started,
                                         'sandbox_id': ready.sandbox_id})
            except Exception:
                logging.getLogger(__name__).warning('Clean sandbox preparation unavailable; queued work remains unclaimed')
                self.wake.wait(2)
                self.wake.clear()

    def take(self):
        with self.lock:
            ready, self.ready = self.ready, None
            if ready:
                self.leased = True
        return ready

    def release(self, sandbox):
        # Never return a used environment to the queue, even on error/cancel.
        try:
            sandbox.kill()
        finally:
            with self.lock:
                self.leased = False
            self.wake.set()

    def return_unassigned(self, sandbox):
        """Only for an idle claim: this clean slot has never received customer data."""
        with self.lock:
            if self.ready is not None or not self.leased:
                raise RuntimeError('Invalid clean slot ownership')
            self.ready, self.leased = sandbox, False
        self.wake.set()

    def close(self):
        self.closed = True
        self.wake.set()
        self.thread.join(timeout=20)
        with self.lock:
            ready, self.ready = self.ready, None
        if ready:
            ready.kill()
