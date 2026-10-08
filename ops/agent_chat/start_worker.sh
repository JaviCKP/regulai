set -euo pipefail
test "$(hostname)" = task48-e2b-vm
docker run -d --rm --name task50-worker --label regulay.task=50 --network task50-exec \
  --user 1000:1000 --read-only --cap-drop ALL --security-opt no-new-privileges --dns 127.0.0.1 \
  --memory 768m --cpus 1 --pids-limit 128 --tmpfs /tmp:rw,nosuid,nodev,size=64m,uid=1000,gid=1000 \
  --mount type=bind,src=/home/probe/task50/.runtime,dst=/run/task50,readonly regulay-task50-executor:local
