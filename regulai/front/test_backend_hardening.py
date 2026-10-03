"""Backend security behavior at HTTP, command and persistent-state interfaces."""
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, Client, override_settings
from django.urls import reverse

from front.models import Alert, Company, Engine, EngineModel, Profile, Rule, RulesGroup


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
