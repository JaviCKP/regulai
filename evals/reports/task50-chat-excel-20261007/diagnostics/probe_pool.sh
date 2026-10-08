set -e
test "$(hostname)" = task48-e2b-vm
docker exec task50-worker python -c 'import json; from front.agents.sandbox_pool import create_clean; s=create_clean(json.load(open("/run/task50/config.json"))); print(s.sandbox_id); s.kill()'
