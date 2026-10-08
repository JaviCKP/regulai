set -e
test "$(hostname)" = task48-e2b-vm
docker inspect e2b-orchestrator-1 --format '{{.Config.Image}} {{json .HostConfig.ShmSize}} {{json .Mounts}}'
for pid in $(pgrep -f '/orchestrator$'); do cat /proc/$pid/cgroup; cat /proc/$pid/mountinfo | grep -E 'huge|cgroup'; done
find /sys/fs/cgroup -name '*hugetlb*' -maxdepth 4 | head -30
mount | grep huge
ls -lh /dev/hugepages
grep -R -nE 'HUGE|UFFD|MEMFD' /home/probe/e2b --include='*.yaml' --include='*.yml' --include='*.sh' | head -40
dmesg | grep -Ei 'oom|out of memory|huge' | tail -20
