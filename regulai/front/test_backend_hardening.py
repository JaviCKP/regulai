"""Backend security behavior at HTTP, command and persistent-state interfaces."""
from unittest.mock import patch
import io
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, Client, override_settings
from django.urls import reverse

from front.models import Alert, Company, Engine, EngineModel, Profile, Rule, RulesGroup
from PIL import Image


class BackendHardeningTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name='Security tenant A')
        self.other = Company.objects.create(name='Security tenant B')
        self.staff = User.objects.create_user('security-staff', is_staff=True)
        self.employee = User.objects.create_user('security-employee')
        self.operator = User.objects.create_user('security-operator', is_staff=True, is_superuser=True)
        self.admin = User.objects.create_user('security-admin', is_superuser=True)
        for user in (self.staff, self.employee, self.operator, self.admin):
            Profile.objects.create(user=user, company=self.company)
        self.group = RulesGroup.objects.create(name='Security rules A', company=self.company)
        self.rule = Rule.objects.create(name='LOCAL_SECURITY_RULE', rules_group=self.group,
            yara_rule='rule Local { condition: true }')
        group = RulesGroup.objects.create(name='Security rules B', company=self.other)
        self.foreign_rule = Rule.objects.create(name='FOREIGN_SECURITY_RULE', rules_group=group,
            yara_rule='rule Foreign { condition: true }')
        Alert.objects.create(company=self.company, rule=self.rule, description='LOCAL_ALERT')
        Alert.objects.create(company=self.other, rule=self.foreign_rule, description='FOREIGN_ALERT')
        self.client.force_login(self.staff)

    def test_notifications_show_only_company_alerts_to_security_staff(self):
        response = self.client.get('/chat/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['unresolved_alerts_count'], 1)
        self.assertContains(response, 'LOCAL_SECURITY_RULE')
        self.assertNotContains(response, 'FOREIGN_SECURITY_RULE')

    def test_employee_cannot_read_notifications_even_inside_own_company(self):
        self.client.force_login(self.employee)
        response = self.client.get('/chat/')
        self.assertEqual(response.context['unresolved_alerts_count'], 0)
        self.assertEqual(list(response.context['recent_unresolved_alerts']), [])
        self.assertNotContains(response, 'LOCAL_SECURITY_RULE')

    def test_global_model_mutations_require_post_and_csrf(self):
        engine = Engine.objects.create(name='Security global engine')
        model = EngineModel.objects.create(engine=engine, name='Security model', model_id='security-model')
        self.client.force_login(self.operator)
        secure = Client(enforce_csrf_checks=True)
        secure.force_login(self.operator)
        with override_settings(PLATFORM_ADMIN_USER_IDS=[self.operator.pk]):
            for action in ('model_toggle', 'model_delete'):
                with self.subTest(action=action):
                    url = reverse('front:' + action, args=[model.pk])
                    self.assertEqual(self.client.get(url).status_code, 405)
                    model.refresh_from_db()
                    self.assertTrue(model.active)
                    self.assertEqual(secure.post(url).status_code, 403)
            toggled = self.client.post(reverse('front:model_toggle', args=[model.pk]))
            self.assertEqual(toggled.status_code, 302)
            model.refresh_from_db()
            self.assertFalse(model.active)
            self.assertEqual(self.client.post(reverse('front:model_delete', args=[model.pk])).status_code, 302)
            self.assertFalse(EngineModel.objects.filter(pk=model.pk).exists())

    def test_community_sync_requires_platform_operator_and_post(self):
        self.client.force_login(self.admin)
        url = reverse('front:rules_community_sync')
        with patch('requests.get') as network:
            network.return_value.json.return_value = []
            self.assertEqual(self.client.post(url).status_code, 403)
            network.assert_not_called()
            self.client.force_login(self.operator)
            with override_settings(PLATFORM_ADMIN_USER_IDS=[self.operator.pk]):
                self.assertEqual(self.client.get(url).status_code, 405)
                network.assert_not_called()
                self.assertEqual(self.client.post(url).status_code, 200)
        self.assertEqual(network.call_count, 1)

    def test_yara_includes_are_disabled_for_creation_and_editing(self):
        with TemporaryDirectory() as directory:
            include = Path(directory) / 'synthetic.yar'
            include.write_text('rule Included { condition: true }', encoding='utf-8')
            source = f'include "{include.as_posix()}"\nrule Submitted {{ condition: true }}'
            data = {'name': 'Submitted', 'yara_rule': source, 'rules_group': self.group.pk}
            for url in (reverse('front:rule_create'), reverse('front:rule_edit', args=[self.rule.pk])):
                with self.subTest(url=url):
                    result = self.client.post(url, data)
                    self.assertEqual(result.status_code, 200)
                    self.assertEqual([str(message) for message in get_messages(result.wsgi_request)],
                        ['Invalid YARA rule; compilation failed.'])
            self.rule.refresh_from_db()
            self.assertNotIn('include', self.rule.yara_rule)
            self.assertFalse(Rule.objects.filter(name='Submitted').exists())

    def test_api_avatar_rejects_large_valid_images_and_accepts_small_ones(self):
        self.client.force_login(self.admin)
        profile = self.admin.profile
        image = io.BytesIO()
        Image.new('RGB', (1, 1)).save(image, format='PNG')
        with TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=directory):
            url = reverse('api:profile-detail', args=[profile.pk])
            from rest_framework.test import APIClient
            client = APIClient()
            client.force_login(self.admin)
            rejected = client.patch(url, {'avatar': SimpleUploadedFile('large.png',
                image.getvalue() + b'\0' * (5 * 1024 * 1024), content_type='image/png')}, format='multipart')
            self.assertEqual(rejected.status_code, 400)
            profile.refresh_from_db()
            self.assertFalse(profile.avatar)
            accepted = client.patch(url, {'avatar': SimpleUploadedFile('small.png', image.getvalue(),
                content_type='image/png')}, format='multipart')
            self.assertEqual(accepted.status_code, 200)
            self.assertTrue(accepted.data['avatar'])
