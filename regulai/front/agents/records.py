"""Private application records. This module is never installed in the executor."""
import uuid
from django.conf import settings
from django.db import models
from front.encrypted_fields import EncryptedTextField


class AgentModelProfile(models.Model):
    company = models.ForeignKey('front.Company', on_delete=models.CASCADE)
    name = models.CharField(max_length=80)
    enabled = models.BooleanField(default=False)
    connection = models.ForeignKey('front.CompanyEngine', on_delete=models.PROTECT)
    model = models.ForeignKey('front.EngineModel', on_delete=models.PROTECT)
    compaction = models.BooleanField(default=True)
    vision = models.BooleanField(default=False)
    tools = models.JSONField(default=list)
    min_group_size = models.PositiveIntegerField(default=3)

    class Meta:
        app_label = 'front'


class AgentExecution(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    prompt = models.OneToOneField('front.Prompt', on_delete=models.CASCADE)
    profile = models.ForeignKey(AgentModelProfile, on_delete=models.PROTECT)
    attempt = models.UUIDField(default=uuid.uuid4)
    token_digest = models.CharField(max_length=64, unique=True)
    authorization_digest = models.CharField(max_length=64)
    expires_at = models.DateTimeField()
    status = models.CharField(max_length=24, default='active')
    active_call = models.UUIDField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # Null only for the task-49 integration records. Chat jobs own this lock key.
    conversation = models.ForeignKey('front.Conversation', null=True, on_delete=models.CASCADE)
    claim_id = models.UUIDField(null=True, unique=True)
    worker_id = models.UUIDField(null=True)
    started_at = models.DateTimeField(null=True)
    finished_at = models.DateTimeField(null=True)
    job = models.JSONField(default=dict)

    class Meta:
        app_label = 'front'
        constraints = [models.CheckConstraint(condition=models.Q(status__in=[
            'queued', 'active', 'cancelled', 'outcome_unknown', 'completed', 'interrupted', 'failed']),
            name='agent_execution_status'),
            models.UniqueConstraint(fields=['conversation'], condition=models.Q(
                status__in=['queued', 'active', 'outcome_unknown']), name='agent_one_writer')]


class AgentInference(models.Model):
    execution = models.ForeignKey(AgentExecution, on_delete=models.CASCADE)
    call_id = models.UUIDField()
    attempt = models.UUIDField()
    request_digest = models.CharField(max_length=64)
    status = models.CharField(max_length=24, default='received')
    response = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'front'
        constraints = [models.UniqueConstraint(fields=['execution', 'call_id'], name='agent_unique_inference')]


class ConversationAlias(models.Model):
    company = models.ForeignKey('front.Company', on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    conversation = models.ForeignKey('front.Conversation', on_delete=models.CASCADE)
    kind = models.CharField(max_length=24)
    version = models.PositiveIntegerField(default=1)
    lookup_digest = models.CharField(max_length=64)
    token = models.CharField(max_length=64, unique=True)
    original = EncryptedTextField()

    class Meta:
        app_label = 'front'
        constraints = [models.UniqueConstraint(fields=['company', 'user', 'conversation', 'kind',
            'version', 'lookup_digest'], name='agent_unique_alias')]


class AgentInput(models.Model):
    """Only trusted application code can grant immutable data to an execution."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    execution = models.ForeignKey(AgentExecution, on_delete=models.CASCADE)
    kind = models.CharField(max_length=20)  # csv or model_image (already approved render)
    path = models.CharField(max_length=160)
    original = EncryptedTextField()
    digest = models.CharField(max_length=64)

    class Meta:
        app_label = 'front'
        constraints = [models.UniqueConstraint(fields=['execution', 'path'], name='agent_unique_input')]


class AgentToolResult(models.Model):
    execution = models.ForeignKey(AgentExecution, on_delete=models.CASCADE)
    call_id = models.CharField(max_length=160)
    request_digest = models.CharField(max_length=64)
    view = models.JSONField(default=dict)
    raw = EncryptedTextField()

    class Meta:
        app_label = 'front'
        constraints = [models.UniqueConstraint(fields=['execution', 'call_id'], name='agent_unique_tool_result')]


class AgentEvent(models.Model):
    execution = models.ForeignKey(AgentExecution, on_delete=models.CASCADE, related_name='events')
    kind = models.CharField(max_length=32)
    data = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'front'
        ordering = ['id']


class AgentArtifact(models.Model):
    """Private immutable candidates/revisions; only verified bytes are downloadable."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    execution = models.ForeignKey(AgentExecution, on_delete=models.CASCADE, related_name='artifacts')
    logical_id = models.UUIDField(default=uuid.uuid4)
    revision = models.PositiveIntegerField()
    base = models.ForeignKey('self', null=True, on_delete=models.RESTRICT)
    source = models.ForeignKey(AgentInput, on_delete=models.RESTRICT)
    operation_id = models.UUIDField()
    status = models.CharField(max_length=12, default='draft')
    content = EncryptedTextField()
    sha256 = models.CharField(max_length=64)
    verification = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'front'
        constraints = [models.UniqueConstraint(fields=['logical_id', 'revision'], name='agent_revision'),
            models.UniqueConstraint(fields=['execution', 'operation_id'], name='agent_artifact_operation'),
            models.CheckConstraint(condition=models.Q(status__in=['draft', 'verified']), name='agent_artifact_status')]
