"""Local-only measured latency update. No deployment outside the owned local VM."""
import argparse
import base64
import json
from pathlib import Path
import runpy
import shlex
import subprocess

ROOT = Path(__file__).resolve().parents[2]
SSH = runpy.run_path(str(ROOT / 'ops/agent_chat/p1_activate_local.py'))['SSH']
IDENTITY = 'latency-20261017-a1'
OUTPUT = ROOT / 'output/latency-optimization-20261017'
CHANGED = ['regulai/front/privacy.py', 'regulai/front/agents/jobs.py',
    'regulai/front/agents/skill_context.py', 'regulai/front/agents/skill_backend.py',
    'regulai/front/agents/checkpoints.py', 'regulai/front/agents/worker.py',
    'regulai/front/agents/queue_wakeup.py', 'regulai/front/agents/capacity.py',
    'regulai/front/agents/service.py']
TESTS = ['regulai/front/test_agent_inference.py', 'regulai/front/test_agent_message_batch.py', 'regulai/front/test_privacy_batch.py', 'regulai/front/test_agent_queue_wakeup.py',
    'regulai/front/test_privacy_batch_revocation.py', 'ops/agent_chat/test_queue_dispatch.py',
    'regulai/front/test_agent_skills_runtime.py', 'ops/agent_chat/test_p1_skills_runtime.py',
    'ops/agent_chat/test_p1_skill_materialization.py']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action')
    parser.add_argument('--count', type=int, default=7)
    parser.add_argument('--round', type=int, default=0)
    args = parser.parse_args()
    request = {'action': args.action, 'identity': IDENTITY, 'count': args.count, 'round': args.round,
        'helper': (ROOT / 'ops/agent_chat/p1_activation_remote.py').read_text(encoding='utf-8'),
        'scripts': {name: base64.b64encode((ROOT / 'ops/agent_chat' / name).read_bytes()).decode()
            for name in ('latency_benchmark_server.py', 'latency_benchmark_worker.py')}}
    if args.action == 'build':
        import hashlib
        request['files'] = {p: base64.b64encode((ROOT / p).read_bytes()).decode() for p in CHANGED + TESTS}
        request['changed'] = CHANGED
        request['baseline'] = {}
        for path in CHANGED:
            result = subprocess.run(['rtk', 'proxy', 'git', 'show', '5e9f775:' + path], cwd=ROOT, capture_output=True)
            request['baseline'][path] = hashlib.sha256(result.stdout.replace(b'\r\n', b'\n')).hexdigest() if result.returncode == 0 else None
    source = (ROOT / 'ops/agent_chat/latency_remote.py').read_bytes()
    loader = 'import sys,json; REQUEST=json.loads(sys.stdin.buffer.readline()); exec(compile(sys.stdin.buffer.read(),"latency_remote.py","exec"))'
    result = subprocess.run([*SSH, 'sudo python3 -c ' + shlex.quote(loader)],
        input=json.dumps(request).encode() + b'\n' + source, capture_output=True)
    if result.returncode:
        raise SystemExit(result.stdout.decode(errors='replace')[-3000:] or 'Local latency stage failed; inspect private log.')
    value = json.loads(result.stdout)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / f'{args.action}-{args.round}.json').write_bytes(json.dumps(value, indent=2).encode('utf-8'))
    visible = value
    if 'rows' in value:
        visible = {key: item for key, item in value.items() if key != 'rows'}
        visible['rows'] = [{key: row[key] for key in ('cache', 'sensitive', 'queue_s', 'preparation_s',
            'first_inference_s', 'sql_preparation', 'seconds', 'sql') if key in row} for row in value['rows']]
    print(json.dumps(visible, indent=2))


if __name__ == '__main__':
    main()
