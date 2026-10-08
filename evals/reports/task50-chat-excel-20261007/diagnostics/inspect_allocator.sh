set -e
test "$(hostname)" = task48-e2b-vm
for pid in $(pgrep -f '/orchestrator$'); do
  cgroup=$(cut -d: -f3 /proc/$pid/cgroup)
  cat /sys/fs/cgroup${cgroup}/hugetlb.2MB.max /sys/fs/cgroup${cgroup}/hugetlb.2MB.rsvd.max /sys/fs/cgroup${cgroup}/hugetlb.2MB.events /sys/fs/cgroup${cgroup}/memory.max
done
python3 - <<'PY'
import os, mmap
for mib in (256,512,1024):
    fd = os.memfd_create('task50-allocation-probe', os.MFD_HUGETLB | os.MFD_HUGE_2MB)
    try:
        os.ftruncate(fd, mib * 1024**2)
        mapping = mmap.mmap(fd, mib * 1024**2)
        print('Host hugepage mmap succeeds:', mib, 'MiB')
        mapping.close()
    except OSError as exc:
        print('Host hugepage mmap:', mib, str(exc))
    finally:
        os.close(fd)
PY
grep -nE 'memory|mem_size' /orchestrator/template/0b60b68c-0f25-4bef-9787-91884bcee38b/* 2>/dev/null || true
