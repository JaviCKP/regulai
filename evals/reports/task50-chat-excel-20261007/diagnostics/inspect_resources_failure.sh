set -e
test "$(hostname)" = task48-e2b-vm
docker compose --project-directory /home/probe/e2b logs --tail 350 --no-color orchestrator | grep -Ei 'ERROR|failed to|not enough|huge|out of|cannot|invalid|error building' | tail -25
grep -E 'Huge|MemFree|MemAvailable' /proc/meminfo
