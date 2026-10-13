"""Task 53 fixture account only; no real Drive requests are possible here."""
import argparse
from datetime import timedelta
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lab_server


def prepare(evidence=None):
    lab_server.prepare(evidence=evidence)
    import httpx
    from asgiref.sync import async_to_sync
    from django.conf import settings
    from django.contrib.auth.models import User
    from django.utils import timezone
    from front.models import AgentDocumentConnection
    from front.agents import document_mcp as mcp
    from front.test_agent_mcp import DriveFixture
    actor = User.objects.get(username='agent-synthetic-ui')
    AgentDocumentConnection.objects.update_or_create(user=actor, company=actor.profile.company,
        defaults={'enabled': True, 'expires_at': timezone.now() + timedelta(hours=1),
            'private_config': json.dumps({'token': 'synthetic-private-token', 'identity': 'person-one', 'folders': ['folder-one']})})
    settings.REGULAY_AGENT_MCP_ENABLED = True
    remote = DriveFixture()
    mcp.call = lambda private, operation, args: async_to_sync(mcp._call)(private, operation, args,
        transport=httpx.MockTransport(remote))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8501)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--evidence')
    args = parser.parse_args()
    prepare(args.evidence)
    import uvicorn
    from django.core.asgi import get_asgi_application
    from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler
    uvicorn.run(ASGIStaticFilesHandler(get_asgi_application()), host=args.host, port=args.port, access_log=False)
