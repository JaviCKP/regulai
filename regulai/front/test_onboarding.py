import json
from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import AuditLog, Company, CompanyEngine, Engine, EngineModel, Profile, Role


class RegistrationTests(TestCase):
    def setUp(self):
        cache.clear()

    def registration(self, name):
        return {'username': name, 'email': name + '@example.test', 'company_name': name,
            'password': 'Synthetic-password-123', 'password_confirm': 'Synthetic-password-123'}

    def test_public_registration_is_disabled_by_default_and_hidden_at_login(self):
        login = self.client.get(reverse('front:login'))
        self.assertFalse(login.context['allow_registration'])
        self.client.post(reverse('front:signup'), self.registration('disabled'))
        self.assertFalse(User.objects.exists())
        self.assertFalse(Company.objects.exists())

    @override_settings(ALLOW_REGISTRATION=True)
    def test_each_registered_company_admin_manages_only_own_policy_without_platform_privileges(self):
        for name in ('first-company', 'second-company'):
            self.client.logout()
            response = self.client.post(reverse('front:signup'), self.registration(name))
            self.assertEqual(response.status_code, 302)
            user = User.objects.get(username=name)
            self.assertFalse(user.is_superuser)
            self.assertTrue(user.is_staff)
            self.assertEqual(user.profile.role.name, 'Admin')
            simulator = self.client.get(reverse('front:policy_simulator'))
            self.assertEqual(simulator.status_code, 200)
            self.assertEqual(simulator.context['company'].name, name)
            self.assertTrue(simulator.context['can_manage_company_policy'])
            self.assertFalse(simulator.context['is_platform_operator'])


class CompanyPolicyPermissionTests(TestCase):
    def setUp(self):
        cache.clear()
        self.company = Company.objects.create(name='Company admin policy', ai_config={
            'version': 1, 'allow_empty_rules': True, 'local_sensitivity': 'internal',
            'destinations': {'internal': ['jev']}})
        self.role = Role.objects.create(name='Admin')
        self.admin = User.objects.create_user('company-policy-admin')
        Profile.objects.create(user=self.admin, company=self.company, role=self.role)
        self.client.force_login(self.admin)
        self.url = reverse('front:policy_simulator')
        self.activate = reverse('front:policy_simulator_activate')

    def test_company_admin_compares_and_activates_own_policy_with_audit(self):
        command = {'proposed_config': json.dumps(dict(self.company.ai_config, local_sensitivity='restricted')),
            'sample': 'Synthetic sample'}
        response = self.client.post(self.url, command)
        self.assertEqual(response.status_code, 200)
        command['activation_token'] = response.context['activation_token']
        activated = self.client.post(self.activate, command)
        self.assertEqual(activated.status_code, 200)
        self.company.refresh_from_db()
        self.assertEqual(self.company.ai_config['local_sensitivity'], 'restricted')
        self.assertEqual(AuditLog.objects.get(action='policy_activate').company_id, self.company.pk)

    def test_foreign_destinations_and_revoked_role_cannot_activate(self):
        foreign = Company.objects.create(name='Foreign policy')
        engine = Engine.objects.create(name='Foreign engine')
        linked = CompanyEngine.objects.create(company=foreign, engine=engine, api_key='synthetic')
        proposed = dict(self.company.ai_config, destinations={'internal': [f'engine:{linked.pk}']})
        self.assertEqual(self.client.post(self.url, {'proposed_config': json.dumps(proposed),
            'sample': 'Synthetic'}).status_code, 400)
        Profile.objects.filter(user=self.admin).update(role=None)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.post(self.activate, {}).status_code, 403)

    def test_legacy_superuser_with_profile_retains_company_policy_and_missing_profile_is_denied(self):
        bare = User.objects.create_user('bare-superuser', is_superuser=True, is_staff=True)
        Profile.objects.create(user=bare, company=self.company)
        self.client.force_login(bare)
        self.assertEqual(self.client.get(self.url).status_code, 200)
        orphan = User.objects.create_user('orphan-admin', is_superuser=True)
        self.client.force_login(orphan)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.admin.is_active = False
        self.admin.save(update_fields=['is_active'])
        self.client.force_login(self.admin)
        self.assertNotEqual(self.client.get(self.url).status_code, 200)

    def test_explicit_platform_operator_with_profile_can_manage_policy(self):
        self.admin.is_staff = True
        self.admin.is_superuser = True
        self.admin.save(update_fields=['is_superuser', 'is_staff'])
        Profile.objects.filter(user=self.admin).update(role=None)
        with override_settings(PLATFORM_ADMIN_USER_IDS=[self.admin.pk]):
            self.assertEqual(self.client.get(self.url).status_code, 200)
