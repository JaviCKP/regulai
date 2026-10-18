"""In-memory negative control: the new materialization test must fail without the shortcut."""
import inspect
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'regulai'))
os.environ['DJANGO_SETTINGS_MODULE'] = 'regulai.test_settings'
import django
django.setup()
from django.test.runner import DiscoverRunner
from front.agents import history

source = inspect.getsource(history.for_prompt)
shortcut = "    if snapshot['pairs'] == []:\n        return []\n"
assert source.count(shortcut) == 1
exec(compile(source.replace(shortcut, ''), '<before-empty-history-shortcut>', 'exec'), history.__dict__)
failures = DiscoverRunner(verbosity=1, interactive=False).run_tests([
    'front.test_agent_context_performance.AgentContextPerformanceTests.'
    'test_empty_history_preserves_selection_without_materializing_available_messages',
])
print(json.dumps({'negative_control': 'empty-selection-shortcut-removed-in-memory',
                  'expected_failing_tests': 1, 'actual_failing_tests': failures}))
sys.exit(0 if failures == 1 else 1)
