param([string]$Action = 'prepare')
$env:REGULAI_CHAT_LAB_PORT = '55483'
$env:REGULAI_CHAT_LAB_DATABASE = 'test_regulai_privacy_ui'
$env:REGULAI_PRIVACY_LAB = '1'
if ($Action -eq 'prepare') {
    rtk proxy C:\Users\javi\Documents\Codex\regulai-platform\.venv\Scripts\python.exe ops/chat_ui/lab.py prepare --fresh
} elseif ($Action -eq 'serve') {
    rtk proxy C:\Users\javi\Documents\Codex\regulai-platform\.venv\Scripts\python.exe ops/chat_ui/lab.py serve --port 8893 --frontend react
} elseif ($Action -eq 'session') {
    rtk proxy C:\Users\javi\Documents\Codex\regulai-platform\.venv\Scripts\python.exe ops/chat_ui/lab.py session
} elseif ($Action -eq 'migrate') {
    rtk proxy C:\Users\javi\Documents\Codex\regulai-platform\.venv\Scripts\python.exe -c "from ops.chat_ui import lab; lab.owner_check(); lab.configure(); from django.core.management import call_command; call_command('migrate', interactive=False)"
}
