set -euo pipefail
test "$(hostname)" = task48-e2b-vm
cd /home/probe/task50
tar -xf /home/probe/task50-source.tar
docker stop task50-worker
sysctl -w vm.nr_hugepages=1536
python3 ops/agent_chat/local_image.py spreadsheet-image.tar > image-server.log 2>&1 &
image_server=$!
trap 'kill "$image_server" || true' EXIT
for iteration in $(seq 1 60); do
  if curl --silent --fail http://127.0.0.1:5000/v2/ >/dev/null; then break; fi
  sleep 1
done
docker run --rm --network host --mount type=bind,src=/home/probe/task50/.runtime,dst=/run/task50,readonly \
  regulay-task50-executor:local python /app/ops/agent_chat/build_template.py /run/task50/template.json
