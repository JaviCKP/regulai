set -euo pipefail
test "$(hostname)" = task48-e2b-vm
cd /home/probe/task50
tar -xf /home/probe/task50-source.tar
# Separate output from preserved task-50 evidence and its old restart marker.
test ! -e evidence-live/task51-regression
install -d -o 1000 -g 1000 evidence-live/task51-regression
(
  for iteration in $(seq 1 240); do
    if test -e evidence-live/task51-regression/restart-request; then
      docker kill --signal KILL task50-worker
      for retry in $(seq 1 30); do
        if ! docker inspect task50-worker >/dev/null 2>&1; then break; fi
        sleep 1
      done
      bash ops/agent_chat/start_worker.sh
      exit
    fi
    sleep 1
  done
  exit 1
) &
controller=$!
trap 'kill "$controller" 2>/dev/null || true' EXIT
docker exec -i -e PYTHONPATH=/app/ops/agent_chat:/app/regulai \
  -e REGULAY_LIVE_EVIDENCE_DIR=/evidence/task51-regression task50-web python - < ops/agent_chat/live_cases.py
wait "$controller"
docker logs task50-worker
