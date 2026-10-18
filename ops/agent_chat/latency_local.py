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
    parser.add_argument('--series', choices=('first', 'second'), default='first')
    parser.add_argument('--profile', action='store_true')
    parser.add_argument('--scenario', choices=('simple', 'history', 'concurrency'), default='simple')
    args = parser.parse_args()
    second = args.series == 'second'
    identity = 'latency-20261017-a2' if second else IDENTITY
    output = ROOT / 'output/latency-optimization-20261017-v2' if second else OUTPUT
    scripts = ['latency_benchmark_server.py', 'latency_benchmark_worker.py']
    if (ROOT / 'ops/agent_chat/latency_profile.py').exists():
        scripts.append('latency_profile.py')
    if args.scenario == 'concurrency':
        scripts.append('latency_concurrency_server.py')
    if args.action in ('sdk-tests', 'sdk-profile'):
        scripts.append('latency_worker_profile.py')
    request = {'action': args.action, 'identity': identity, 'count': args.count, 'round': args.round,
        'profile': args.profile, 'scenario': args.scenario,
        'helper': (ROOT / 'ops/agent_chat/p1_activation_remote.py').read_text(encoding='utf-8'),
        'scripts': {name: base64.b64encode((ROOT / 'ops/agent_chat' / name).read_bytes()).decode()
            for name in scripts}}
    if second and args.action == 'cleanup-benchmarks':
        # Explicit immutable build evidence from this series, not tag discovery.
        # A stopped benchmark can outlive Docker's old image metadata.
        request['historical_builds'] = [
            {'artifact': f'build-{number}.json',
             'manifest': json.loads((output / f'build-{number}.json').read_text(encoding='utf-8'))}
            for number in (0, 2, 3, 4, 5)]
    if args.action == 'build':
        import hashlib
        changed, tests = list(CHANGED), list(TESTS)
        if second:
            changed += ['regulai/front/agents/views.py', 'regulai/front/agents/history.py',
                'regulai/front/agents/capabilities.py', 'regulai/front/governance.py', 'regulai/front/access.py',
                'regulai/front/agents/adapter.py', 'regulai/front/agents/professional_worker.py',
                'regulai/front/agents/professional.py']
            tests += [p.relative_to(ROOT).as_posix() for p in (ROOT / 'regulai/front').glob('test_agent_context*.py')]
            tests += ['regulai/front/test_privacy_service.py', 'ops/agent_chat/test_professional_tool_preparation.py',
                'ops/agent_chat/test_p0_runtime.py', 'regulai/front/test_agent_admission_context.py']
        request['files'] = {p: base64.b64encode((ROOT / p).read_bytes()).decode() for p in changed + tests}
        request['changed'] = changed
        request['baseline'] = {}
        for path in changed:
            result = subprocess.run(['rtk', 'proxy', 'git', 'show', ('a9e58ed' if second else '5e9f775') + ':' + path], cwd=ROOT, capture_output=True)
            request['baseline'][path] = hashlib.sha256(result.stdout.replace(b'\r\n', b'\n')).hexdigest() if result.returncode == 0 else None
    source = (ROOT / 'ops/agent_chat/latency_remote.py').read_bytes()
    loader = 'import sys,json; REQUEST=json.loads(sys.stdin.buffer.readline()); exec(compile(sys.stdin.buffer.read(),"latency_remote.py","exec"))'
    result = subprocess.run([*SSH, 'sudo python3 -c ' + shlex.quote(loader)],
        input=json.dumps(request).encode() + b'\n' + source, capture_output=True)
    if result.returncode:
        raise SystemExit(result.stdout.decode(errors='replace')[-3000:] or 'Local latency stage failed; inspect private log.')
    value = json.loads(result.stdout)
    output.mkdir(parents=True, exist_ok=True)
    suffix = '-profile' if args.profile else ''
    if args.scenario != 'simple':
        suffix += '-' + args.scenario
    (output / f'{args.action}-{args.round}{suffix}.json').write_bytes(json.dumps(value, indent=2).encode('utf-8'))
    visible = value
    if 'rows' in value:
        visible = {key: item for key, item in value.items() if key != 'rows'}
        visible['rows'] = [{key: row[key] for key in ('cache', 'sensitive', 'queue_s', 'preparation_s',
            'first_inference_s', 'sql_preparation', 'seconds', 'sql') if key in row} for row in value['rows']]
    print(json.dumps(visible, indent=2))
    if value.get('exit_code'):
        raise SystemExit(value['exit_code'])


if __name__ == '__main__':
    main()
