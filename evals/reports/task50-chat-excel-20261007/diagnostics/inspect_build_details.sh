set -e
test "$(hostname)" = task48-e2b-vm
docker compose --project-directory /home/probe/e2b logs --since 2026-10-07T21:34:00 --until 2026-10-07T21:39:04 --no-color orchestrator | grep -Ei 'sandbox.*(memory|failed|error|exit|kill|oom)|kernel|firecracker|creating sandbox' | tail -40
docker inspect e2b-orchestrator-1 --format '{{json .Mounts}}'
