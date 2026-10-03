"""Freeze the reviewed local-v2 manifests and run only offline pilot preparation."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def save(name, value):
    with (HERE / name).open('x', encoding='utf-8') as handle:
        handle.write(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def main():
    if (HERE / 'snapshot.json').exists():
        raise SystemExit('Evidence already exists; use a new execution directory.')
    prepared = []
    for bank in ('pilot-real', 'pilot-human'):
        folder = ROOT / 'evals' / bank
        previous = (folder / 'manifest.json').read_bytes()
        candidate = folder / 'manifest-local-v2.json'
        fresh = candidate.read_bytes()
        old, new = json.loads(previous), json.loads(fresh)
        changed = {key for key in set(old) | set(new) if old.get(key) != new.get(key)}
        assert changed <= {'source_sha256', 'runtime_versions', 'masking'}, changed
        assert {k: v for k, v in old['masking'].items() if k != 'detector_version'} == {
            k: v for k, v in new['masking'].items() if k != 'detector_version'}
        assert new['masking']['detector_version'] == 'regulai-local-v2'
        (HERE / (bank + '-manifest-before.json')).write_bytes(previous)
        (HERE / (bank + '-manifest-final.json')).write_bytes(fresh)
        prepared.append((folder, candidate, fresh, new, changed))
    approval_path = ROOT / 'evals/pilot-real/authorization.pending.json'
    prior_approval = approval_path.read_bytes()
    approval = json.loads(prior_approval)
    assert approval['status'] == 'pending' and approval['approved_by'] is None
    (HERE / 'authorization-before.json').write_bytes(prior_approval)
    approval['manifest_sha256s'] = [sha256(row[2]).hexdigest() for row in prepared]
    approval['masking'] = prepared[0][3]['masking']
    for folder, candidate, fresh, _, _ in prepared:
        (folder / 'manifest.json').write_bytes(fresh)
        # Remove only the two freshly prepared files named explicitly above.
        candidate.unlink()
    approval_path.write_text(json.dumps(approval, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (HERE / 'authorization-final.json').write_bytes(approval_path.read_bytes())
    revision = subprocess.run(['rtk', 'proxy', 'git', 'rev-parse', 'HEAD'], cwd=ROOT,
        capture_output=True, text=True, check=True).stdout.strip()
    save('snapshot.json', {'revision': revision, 'time_utc': datetime.now(timezone.utc).isoformat(),
        'manifest_sha256s': approval['manifest_sha256s'],
        'changes': {row[0].name: sorted(row[4]) for row in prepared},
        'approval_status': approval['status'], 'actual_api_spend_usd': '0',
        'human_reviews_completed': 0, 'official_prices_rechecked_on': '2026-10-03'})
    manage = [sys.executable, 'regulai/manage.py']
    settings = ['--settings=regulai.test_settings']
    common = ['--authorization', 'evals/pilot-real/authorization.pending.json']
    commands = [
        ('smoke', [*manage, 'smoke_ai', *settings, '--output', str(HERE / 'smoke')]),
        ('human', [*manage, 'evaluate_ai', *settings, '--manifest', 'evals/pilot-human/manifest.json',
                   '--output', str(HERE / 'human')]),
        ('preflight-smoke', [*manage, 'smoke_ai', *settings, '--preflight', *common,
                            '--output', str(HERE / 'must-not-exist-smoke')]),
        ('preflight-human', [*manage, 'evaluate_ai', *settings, '--manifest', 'evals/pilot-human/manifest.json',
                            '--preflight', *common, '--output', str(HERE / 'must-not-exist-human')]),
    ]
    outcomes = []
    for name, arguments in commands:
        start = time.monotonic()
        result = subprocess.run(['rtk', 'proxy', *arguments], cwd=ROOT, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, encoding='utf-8', errors='replace')
        log = HERE / (name + '.log')
        log.write_text(result.stdout, encoding='utf-8')
        outcomes.append({'name': name, 'command': ['rtk', 'proxy', *arguments],
            'exit_code': result.returncode, 'seconds': round(time.monotonic() - start, 3),
            'log': log.name, 'sha256': sha256(log.read_bytes()).hexdigest()})
        print(f'{name}: exit {result.returncode}', flush=True)
    save('commands.json', outcomes)
    assert not (HERE / 'must-not-exist-smoke').exists() and not (HERE / 'must-not-exist-human').exists()
    assert all(row['exit_code'] == 0 for row in outcomes), outcomes


if __name__ == '__main__':
    main()
