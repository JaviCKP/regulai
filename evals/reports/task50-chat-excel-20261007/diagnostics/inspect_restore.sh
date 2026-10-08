set -e
test "$(hostname)" = task48-e2b-vm
docker compose --project-directory /home/probe/e2b logs --since 10m --no-color orchestrator | grep -E 'error while building|uffd|mmap|ENOMEM|cannot allocate|error loading|failed to start|signal: killed' | tail -30
docker inspect e2b-orchestrator-1 --format '{{json .HostConfig.Ulimits}} {{.HostConfig.Memory}}'
for pid in $(pgrep -f '/orchestrator$'); do cat /proc/$pid/limits; done
grep -E 'Huge|MemFree|MemAvailable' /proc/meminfo
df -h /dev/hugepages /dev/shm /
docker ps --format '{{.Names}} {{.Status}}'
