"""Read-only evidence audit. Does not import Django or call a provider."""
import argparse
from hashlib import sha256
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compare-originals', action='store_true',
        help='Also compare retained .claude files; captured reports have an explicit link-only revision.')
    args = parser.parse_args()
    manifest = json.loads((HERE / 'manifest.json').read_text(encoding='utf-8'))
    failures = []
    original_checks = 0
    for row in manifest['entries']:
        destination = HERE / row['destination']
        data = destination.read_bytes()
        if len(data) != row['bytes'] or sha256(data).hexdigest() != row['copy_sha256']:
            failures.append(row['destination'])
        if row['copy_sha256'] != row['source_sha256']:
            failures.append(row['destination'] + ': original/copy hash mismatch')
        if args.compare_originals and row['kind'] == 'closed_review_evidence':
            original_checks += 1
            if sha256((ROOT / row['source']).read_bytes()).hexdigest() != row['source_sha256']:
                failures.append(row['source'] + ': retained original changed')
    print(json.dumps({'files': len(manifest['entries']), 'original_files_checked': original_checks,
        'failures': failures, 'product_or_provider_executed': False}))
    return bool(failures)


if __name__ == '__main__':
    raise SystemExit(main())
