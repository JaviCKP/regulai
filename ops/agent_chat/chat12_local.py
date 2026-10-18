"""Local chat-12 fix using the tested latency activation/rollback protocol."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import runpy
import shlex
import subprocess

ROOT = Path(__file__).resolve().parents[2]
IDENTITY = 'chat12-20261018-a1'
CHANGED = ['regulai/front/agents/general_tools.py', 'regulai/front/agents/checkpoints.py',
           'regulai/front/agents/history.py', 'regulai/front/agents/continuation.py']
TESTS = ['regulai/front/test_chat12_recovery.py', 'regulai/front/test_agent_tools_p1.py',
         'ops/agent_chat/test_p0_runtime.py', 'ops/agent_chat/test_p1_skills_runtime.py',
         'ops/agent_chat/test_queue_dispatch.py', 'ops/agent_chat/test_professional_tool_preparation.py']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['init','build','tests','sdk-tests','apply','verify','rollback'])
    parser.add_argument('--round', type=int, default=0)
    args = parser.parse_args()
    output = ROOT/'output/chat12-fix-20261018'
    request = {'action': args.action, 'identity': IDENTITY, 'round': args.round,
        'helper': (ROOT/'ops/agent_chat/p1_activation_remote.py').read_text(encoding='utf-8'),
        'scripts': {'latency_worker_profile.py': base64.b64encode(
            (ROOT/'ops/agent_chat/latency_worker_profile.py').read_bytes()).decode()}}
    if args.action == 'build':
        request['changed'] = CHANGED
        request['files'] = {p:base64.b64encode((ROOT/p).read_bytes()).decode() for p in CHANGED+TESTS}
        request['baseline'] = {}
        for p in CHANGED:
            prior = subprocess.run(['rtk','proxy','git','show','ab6a90c:'+p],cwd=ROOT,capture_output=True)
            request['baseline'][p] = hashlib.sha256(prior.stdout.replace(b'\r\n',b'\n')).hexdigest() if prior.returncode==0 else None
    # Reuse the reviewed backup, source checks, idle fencing, identity switch and
    # data-preserving rollback; give this update an independent private stage.
    source = (ROOT/'ops/agent_chat/latency_remote.py').read_text(encoding='utf-8')
    source = source.replace('latency-20261017-a2', IDENTITY)
    source = source.replace('test_regulai_latency_v2_20261017','test_regulai_chat12_20261018')
    source = source.replace("labels=[", "labels=['front.test_chat12_recovery','front.test_agent_tools_p1','front.test_agent_history_window','front.test_agent_professional.ProfessionalTests.test_tool_replay_never_reexecutes_and_uncertain_intent_is_not_replayed','front.test_agent_professional.ProfessionalTests.test_revocation_cancellation_and_profile_budget_stop_further_inference','front.test_agent_professional.ProfessionalTests.test_private_computation_removes_network_tools_at_provider_boundary','front.test_agent_professional.ProfessionalTests.test_failure_after_a_security_rejection_reports_the_check_not_missing_sources',")
    source = source.replace(",\n 'front.test_agent_professional.ProfessionalTests.test_three_entries_real_account_free_text_and_http_idempotency'", '')
    ssh = runpy.run_path(str(ROOT/'ops/agent_chat/p1_activate_local.py'))['SSH']
    loader = 'import sys,json; REQUEST=json.loads(sys.stdin.buffer.readline()); exec(compile(sys.stdin.buffer.read(),"chat12_remote.py","exec"))'
    result = subprocess.run([*ssh,'sudo python3 -c '+shlex.quote(loader)],
        input=json.dumps(request).encode()+b'\n'+source.encode(),capture_output=True)
    if result.returncode:
        raise SystemExit(result.stdout.decode(errors='replace')[-1500:] or 'Inspect private stage error.log')
    value = json.loads(result.stdout)
    output.mkdir(parents=True,exist_ok=True)
    (output/f'{args.action}-{args.round}.json').write_text(json.dumps(value,indent=2),encoding='utf-8',newline='\n')
    print(json.dumps(value,indent=2))
    raise SystemExit(value.get('exit_code',0))


if __name__ == '__main__':
    main()
