"""Server-only reversible protection records; no natural projection is persisted."""
from django.conf import settings
from django.db import models
from .encrypted_fields import EncryptedTextField


class PrivacyRevision(models.Model):
    company = models.ForeignKey('front.Company', on_delete=models.CASCADE)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    # Includes literal dictionaries: never store those values in public policy JSON.
    configuration = EncryptedTextField()
    fingerprint = models.CharField(max_length=64)
    detector_version = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError('privacy_revision_immutable')
        return super().save(*args, **kwargs)


class PrivacyTurn(models.Model):
    prompt = models.OneToOneField('front.Prompt', on_delete=models.CASCADE)
    revision = models.ForeignKey(PrivacyRevision, on_delete=models.PROTECT)
    fingerprint = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)


class PrivacyMessage(models.Model):
    turn = models.ForeignKey(PrivacyTurn, on_delete=models.CASCADE, related_name='messages')
    source_key = models.CharField(max_length=160)
    # Keyed digest permits idempotent writes without disclosing low-entropy input.
    input_digest = models.CharField(max_length=64)
    protected = models.TextField()
    # Original spelling, only if distinct from the canonical value, by occurrence.
    variants = EncryptedTextField(default='{}')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['turn', 'source_key'], name='privacy_message_once')]


class PrivacyOccurrence(models.Model):
    message = models.ForeignKey(PrivacyMessage, on_delete=models.CASCADE, related_name='occurrences')
    alias = models.ForeignKey('front.ConversationAlias', null=True, on_delete=models.SET_NULL)
    start = models.PositiveIntegerField()
    end = models.PositiveIntegerField()
    category = models.CharField(max_length=24)
    detector = models.CharField(max_length=100)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['message', 'start', 'end'], name='privacy_occurrence_once')]


class PrivacyUse(models.Model):
    turn = models.ForeignKey(PrivacyTurn, on_delete=models.CASCADE, related_name='uses')
    # Stable ID of the governed call/inference, not an SSE chunk or visual offset.
    call_key = models.CharField(max_length=160)
    alias = models.ForeignKey('front.ConversationAlias', on_delete=models.CASCADE)
    count = models.PositiveIntegerField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=['turn', 'call_key', 'alias'], name='privacy_use_once')]


class PrivacySelection(models.Model):
    alias = models.OneToOneField('front.ConversationAlias', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
