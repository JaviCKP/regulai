set -e
test "$(hostname)" = task48-e2b-vm
docker compose --project-directory /home/probe/e2b logs --tail 100 --no-color orchestrator
dmesg | tail -30
