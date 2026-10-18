"""Serial paired measurements; raw reports are written by latency_local.py."""
import argparse
import json
from pathlib import Path
import statistics
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--start', type=int, required=True)
    parser.add_argument('--rounds', type=int, required=True)
    parser.add_argument('--count', type=int, default=7)
    parser.add_argument('--variant', choices=('paired', 'baseline', 'after'), default='paired')
    parser.add_argument('--scenario', choices=('simple', 'history', 'concurrency'), default='simple')
    args = parser.parse_args()
    for number in range(args.start, args.start + args.rounds):
        variants = (('baseline', 'after') if number % 2 == 0 else ('after', 'baseline')) if args.variant == 'paired' else (args.variant,)
        for variant in variants:
            action = 'bench-' + variant
            command = ['rtk', 'proxy', sys.executable, str(ROOT / 'ops/agent_chat/latency_local.py'),
                action, '--series', 'second', '--round', str(number), '--count', str(args.count),
                '--scenario', args.scenario]
            result = subprocess.run(command, cwd=ROOT, capture_output=True)
            if result.returncode:
                print(json.dumps({'round': number, 'variant': variant, 'status': 'failed'}), flush=True)
                sys.stderr.write(result.stdout.decode(errors='replace')[-2000:])
                sys.stderr.write(result.stderr.decode(errors='replace')[-2000:])
                raise SystemExit(result.returncode)
            suffix = '' if args.scenario == 'simple' else '-' + args.scenario
            report = json.loads((ROOT / f'output/latency-optimization-20261017-v2/{action}-{number}{suffix}.json').read_text())
            rows = report['rows']
            print(json.dumps({'round': number, 'variant': variant, 'n': len(rows),
                'median_preparation_s': statistics.median(row['preparation_s'] for row in rows),
                'median_queue_s': statistics.median(row['queue_s'] for row in rows),
                'selects': sorted({row['sql_preparation'].get('SELECT', 0) for row in rows})}), flush=True)


if __name__ == '__main__':
    main()
