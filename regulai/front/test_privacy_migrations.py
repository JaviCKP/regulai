"""Forward/backward on disposable PostgreSQL; preserve the preexisting registry."""
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class PrivacyMigrationTests(TransactionTestCase):
    def test_additive_forward_reverse_preserves_existing_alias_ciphertext_and_defaults(self):
        old = [('front', '0043_p1_skills_and_events')]
        new = [('front', '0045_privacy_call_identity')]
        executor = MigrationExecutor(connection)
        self.addCleanup(lambda: MigrationExecutor(connection).migrate(new))
        executor.migrate(old)
        apps = executor.loader.project_state(old).apps
        user = apps.get_model('auth', 'User').objects.create(username='migration-fixture')
        company = apps.get_model('front', 'Company').objects.create(name='Migration synthetic')
        chat = apps.get_model('front', 'Conversation').objects.create(user_id=user.pk)
        alias = apps.get_model('front', 'ConversationAlias').objects.create(company_id=company.pk,
            user_id=user.pk, conversation_id=chat.pk, kind='EMAIL', version=1,
            token='[[R_EMAIL_00000000000000000000000000000001]]', lookup_digest='f' * 64,
            original='migration@example.invalid')
        def ciphertext():
            with connection.cursor() as cursor:
                cursor.execute('SELECT original FROM front_conversationalias WHERE id=%s', [alias.pk])
                return cursor.fetchone()[0]
        before = ciphertext()
        self.assertNotIn('migration@', before)
        for target in (new, old, new):
            executor = MigrationExecutor(connection)
            executor.migrate(target)
            models = executor.loader.project_state(target).apps
            self.assertEqual(ciphertext(), before)
            self.assertEqual(models.get_model('front', 'ConversationAlias').objects.get(pk=alias.pk).original,
                             'migration@example.invalid')
            self.assertNotIn('privacy', models.get_model('front', 'Company').objects.get(pk=company.pk).ai_config)
