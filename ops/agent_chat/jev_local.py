"""Update only agent service.py on the current chat-12 web image; no policy/DB edits."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import runpy
import shlex
import subprocess

ROOT = Path(__file__).resolve().parents[2]
IDENTITY = 'jev-difficulty-20261018-a1'
SERVICE = 'regulai/front/agents/service.py'
TESTS = ['regulai/front/' + name + '.py' for name in (
    'test_agent_difficulty', 'test_agent_transparency', 'test_agent_inference', 'test_agent_state',
    'test_agent_context_performance', 'test_agent_message_batch', 'test_privacy_agent',
    'test_difficulty_routing', 'test_chat_flow', 'test_pipeline', 'test_chat_island',
    'test_local_masking')]
EXPECTED_WEB = 'sha256:11d2287cdfd36a91ffd777f1b3ec79359abd84e1a853f05521642740bc7c8251'
BASELINE_SERVICE = '466efcdc96c46a636627e49b4ebec311f1eb27bce7c1a8553bd7453c7f71ee5b'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('init', 'build', 'tests', 'apply', 'verify', 'rollback'))
    parser.add_argument('--round', type=int, default=0)
    args = parser.parse_args()
    source = (ROOT / SERVICE).read_bytes().replace(b'\r\n', b'\n')
    request = {'action': args.action, 'identity': IDENTITY, 'expected_web': EXPECTED_WEB,
        'baseline_service': BASELINE_SERVICE, 'target_sha256': hashlib.sha256(source).hexdigest(),
        'helper': (ROOT / 'ops/agent_chat/p1_activation_remote.py').read_text(encoding='utf-8'),
        'primitives': (ROOT / 'ops/agent_chat/latency_remote.py').read_text(encoding='utf-8')}
    if args.action == 'build':
        request['service'] = base64.b64encode(source).decode()
        request['tests'] = {path: base64.b64encode((ROOT / path).read_bytes()).decode() for path in TESTS}
    activation = runpy.run_path(str(ROOT / 'ops/agent_chat/p1_activate_local.py'))
    activation['owner_check']()
    ssh = activation['SSH']
    loader = ('import sys,json; REQUEST=json.loads(sys.stdin.buffer.readline()); '
              'exec(compile(sys.stdin.buffer.read(),"jev_remote.py","exec"))')
    response = subprocess.run([*ssh, 'sudo python3 -c ' + shlex.quote(loader)],
        input=json.dumps(request).encode() + b'\n' + (ROOT / 'ops/agent_chat/jev_remote.py').read_bytes(),
        capture_output=True)
    if response.returncode:
        raise SystemExit(response.stdout.decode(errors='replace')[-1500:] or 'Inspect the private Jev update stage.')
    result = json.loads(response.stdout)
    output = ROOT / 'output/jev-difficulty-20261018'
    output.mkdir(parents=True, exist_ok=True)
    (output / f'{args.action}-{args.round}.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))
    raise SystemExit(result.get('exit_code', 0))


if __name__ == '__main__':
    main()
