set -e
test "$(hostname)" = task48-e2b-vm
find /orchestrator -maxdepth 5 -name '*header*' -o -name '*metadata*' | head -25
docker compose --project-directory /home/probe/e2b logs --since 30m --no-color orchestrator | grep -E 'mem_size_mib|memory_mib|memory.mb|"memory"|memory size|Memory MiB' | tail -20
find /orchestrator/template/0b60b68c-0f25-4bef-9787-91884bcee38b -maxdepth 3 -type f -printf '%p %s\n' | head -20
