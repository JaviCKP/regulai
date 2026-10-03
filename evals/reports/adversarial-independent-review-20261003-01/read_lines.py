import sys
from pathlib import Path

path = Path(sys.argv[1])
start = int(sys.argv[2]) if len(sys.argv) > 2 else 1
end = int(sys.argv[3]) if len(sys.argv) > 3 else 10**9
for number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
    if start <= number <= end:
        print(f"{number}: {line}")
