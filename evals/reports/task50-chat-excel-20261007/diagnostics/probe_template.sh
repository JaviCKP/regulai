set -e
test "$(hostname)" = task48-e2b-vm
cd /home/probe/task50
docker run --rm --network host --mount type=bind,src=/home/probe/task50/.runtime,dst=/run/task50,readonly regulay-task50-executor:local python -c 'import json,sys; sys.path.insert(0,"/app/ops/agent_chat"); from build_template import build; config=json.load(open("/run/task50/template.json")); print(build(config))'
