"""Revocation interleavings between local batch protection and the next exit."""
from unittest.mock import patch

from django.test import TestCase

from front.models import Company, PrivacyCall, PrivacyRevision, PrivacyUse, Profile
from front.privacy import outbound, protect_batch
from front.test_privacy_batch import BatchFixture


class PrivacyBatchRevocationTests(BatchFixture, TestCase):
    def assert_outbound_denied(self, protected, reason):
        with self.assertRaisesMessage(ValueError, reason):
            outbound(self.prompt, "revoked-exit", protected)
        self.assertFalse(PrivacyCall.objects.exists())
        self.assertFalse(PrivacyUse.objects.exists())

    def test_user_revoked_during_masking_cannot_use_the_operation_snapshot_at_exit(self):
        from front.local_masking import mask_local_texts
        masked = []

        def revoke_after_real_mask(texts, **kwargs):
            result = mask_local_texts(texts, **kwargs)
            self.user.is_active = False
            self.user.save(update_fields=["is_active"])
            masked.append(True)
            return result

        with patch("front.local_masking.mask_local_texts", side_effect=revoke_after_real_mask):
            protected = protect_batch(self.prompt, ["Ana Fixture ana@example.invalid"])
        self.assertTrue(masked)
        self.assertNotIn("ana@example.invalid", protected[0])
        self.assert_outbound_denied(protected, "privacy_access_revoked")

    def test_company_change_between_batch_and_exit_revokes_cached_context(self):
        protected = protect_batch(self.prompt, ["Ana Fixture ana@example.invalid"])
        other = Company.objects.create(name="Other exit company")
        Profile.objects.filter(pk=self.profile.pk).update(company=other)
        self.assert_outbound_denied(protected, "privacy_access_revoked")

    def test_revision_change_between_batch_and_exit_rejects_the_old_turn(self):
        protected = protect_batch(self.prompt, ["Ana Fixture ana@example.invalid"])
        revision = PrivacyRevision.objects.create(company=self.company, author=self.user,
            configuration=self.revision.configuration, fingerprint="new-exit-revision",
            detector_version=self.revision.detector_version)
        self.company.ai_config = {"privacy": {"version": 1, "revision_id": revision.pk}}
        self.company.save(update_fields=["ai_config"])
        self.assert_outbound_denied(protected, "privacy_policy_changed")

    def test_policy_removal_between_batch_and_exit_cannot_disable_the_gate(self):
        protected = protect_batch(self.prompt, ["Ana Fixture ana@example.invalid"])
        self.company.ai_config = {}
        self.company.save(update_fields=["ai_config"])
        self.assert_outbound_denied(protected, "privacy_policy_revoked")
