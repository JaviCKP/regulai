"""Exercise the chosen team rules at each existing send boundary, offline."""
import yara

from front.models import Rule
from front.security_presets import TEAM_RULES, PRIVACY_SAMPLE
from front.test_chat_flow import ChatFixture


class TeamRulesTests(ChatFixture):
    def setUp(self):
        super().setUp()
        self.rule.delete()
        for item in TEAM_RULES:
            row = Rule(rules_group=self.group, applies_to='both', active=True, **item)
            row.full_clean()
            row.save()

    def test_blocks_and_consent_precede_all_provider_calls(self):
        samples = (
            ('-----BEGIN PRIVATE KEY-----\nDEMO_SIN_CLAVE_REAL', 'blocked'),
            ('api_key = DEMO_NO_VALID_KEY_1234567890', 'blocked'),
            ('SOLO USO INTERNO\nPlan comercial de la empresa de ejemplo.', 'blocked'),
            ('Listado de personal\nLucia Romero: salario de ejemplo 32000 EUR.', 'pending_consent'),
        )
        for path in ('/chat/send/', '/api/chat/send/', '/chat/'):
            for text, expected in samples:
                with self.subTest(path=path, expected=expected):
                    response = self.send(path, text)
                    self.assertEqual(response.json()['status'], expected, response.content)
                    self.provider.assert_not_called()
                    self.http.assert_not_called()

    def test_normal_questions_and_personal_data_are_not_blanket_blocked(self):
        rules = yara.compile(sources={str(i): row['yara_rule'] for i, row in enumerate(TEAM_RULES)})
        for text in (PRIVACY_SAMPLE, '¿Cómo cambio mi password?', 'Explica qué significa confidencial.',
                     'Explica cómo se calcula un salario.', 'api_key = ejemplo', 'Listado de personal: horarios de oficina.'):
            with self.subTest(text=text):
                self.assertEqual(rules.match(data=text.encode()), [])
