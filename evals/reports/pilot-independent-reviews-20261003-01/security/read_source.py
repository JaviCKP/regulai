from pathlib import Path
import sys

root = Path(__file__).resolve().parent / 'snapshot'
path = (root / sys.argv[1]).resolve()
assert path.is_relative_to(root) and 'local_settings' not in path.name
start = int(sys.argv[2]) if len(sys.argv) > 2 else 1
end = int(sys.argv[3]) if len(sys.argv) > 3 else 10000
for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
    if start <= number <= end:
        print(f'{number:4}: {line}')
