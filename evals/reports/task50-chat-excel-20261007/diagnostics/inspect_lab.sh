set -e
test "$(hostname)" = task48-e2b-vm
free -m
df -h /
docker ps --format '{{.Names}} {{.Status}}'
docker stats --no-stream --format '{{.Name}} {{.CPUPerc}} {{.MemUsage}}'
docker compose --project-directory /home/probe/e2b logs --tail 15 --no-color template-manager
