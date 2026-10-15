"""Erase expired professional execution contents, keeping minimal audit metadata."""
from datetime import timedelta
import json
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from front.models import AgentExecution, AgentInput, AgentToolResult, AgentOperation, AgentInference


class Command(BaseCommand):
    help = 'Preview expired professional run contents. --apply erases their protected bytes; never active runs.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--run-id', action='append', default=[])

    def handle(self, *args, **options):
        query = AgentExecution.objects.filter(job__kind='professional', status__in=('completed', 'failed', 'cancelled', 'interrupted'))
        if options['run_id']:
            query = query.filter(pk__in=options['run_id'])
        erased, expired = [], []
        for candidate in query.iterator():
            days = candidate.job.get('limits', {}).get('retention_days', 30)
            if candidate.job.get('expired') or (candidate.finished_at or candidate.created_at) > timezone.now() - timedelta(days=days):
                continue
            expired.append(str(candidate.pk))
            if not options['apply']:
                continue
            with transaction.atomic():
                run = AgentExecution.objects.select_for_update().get(pk=candidate.pk)
                days = run.job.get('limits', {}).get('retention_days', 30)
                if (run.status not in ('completed', 'failed', 'cancelled', 'interrupted') or run.job.get('expired')
                        or (run.finished_at or run.created_at) > timezone.now() - timedelta(days=days)):
                    continue
                run.job.update(expired=True, expired_at=timezone.now().isoformat())
                run.save(update_fields=['job'])
                # Keep FK lineage and hashes; downloads/previews are revoked.
                AgentInput.objects.filter(execution=run).update(original='')
                AgentToolResult.objects.filter(execution=run).update(raw='', protected_view='', view={})
                AgentOperation.objects.filter(execution=run).update(request='', result='')
                for record in AgentInference.objects.filter(execution=run):
                    record.response = {key: value for key, value in record.response.items() if key in ('status', 'code', 'usage', 'inference')}
                    record.save(update_fields=['response'])
                for artifact in run.artifacts.all():
                    artifact.content, artifact.render_bundle = '', ''
                    artifact.verification = {key: value for key, value in artifact.verification.items()
                        if key in ('contract', 'sha256', 'format', 'bytes', 'pages', 'pdf_sha256', 'docx_sha256', 'page_sha256')}
                    artifact.save(update_fields=['content', 'render_bundle', 'verification'])
                erased.append(str(run.pk))
        self.stdout.write(json.dumps({'apply': options['apply'], 'eligible_runs': expired, 'erased_runs': erased}))
