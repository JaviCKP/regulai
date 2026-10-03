"""Real installed CPU detector; no provider or downloaded test-time models."""
from concurrent.futures import ThreadPoolExecutor
import json
from unittest.mock import patch

from django.test import SimpleTestCase

from . import local_masking


class LocalMaskingTests(SimpleTestCase):
    def test_real_cpu_masks_structured_personal_data_and_secrets_without_network(self):
        samples = ['Correo: ana.perez@example.test', 'DNI: 12345678Z', 'NIE: X1234567L',
            'Cuenta: ES91 2100 0418 4502 0005 1332', 'Teléfono: +34 612 345 678',
            'Tarjeta: 4111 1111 1111 1111', 'api_key=sk_test_abcdefghijk123',
            'Bearer abcdefghijklmnop.123456789', 'Mi nombre es María García y vivo en Madrid.',
            'John Smith lives in London.']
        forbidden = ['ana.perez@example.test', '12345678Z', 'X1234567L', 'ES91 2100 0418 4502 0005 1332',
            '+34 612 345 678', '4111 1111 1111 1111', 'sk_test_abcdefghijk123',
            'abcdefghijklmnop.123456789', 'María García', 'John Smith']
        with patch('socket.socket.connect', side_effect=AssertionError('No local detector network')) as network:
            result = local_masking.mask_local_texts(samples, timeout=30)
        self.assertEqual(len(result), len(samples))
        for original, masked in zip(forbidden, result):
            with self.subTest(value=original):
                self.assertNotIn(original, masked)
                self.assertIn('[[REGULAI_', masked)
        network.assert_not_called()

    def test_json_structure_numbers_aliases_and_duplicate_keys_are_preserved(self):
        value = '{"claims":[{"text":"Email ana@example.test","citations":[{"source_id":"F1","quote":"Email ana@example.test"}]}],"n":1.234567890123456789,"n":2,"password":123456}'
        masked = local_masking.mask_local_texts([value], timeout=30)[0]
        payload = json.loads(masked)
        self.assertEqual(payload['claims'][0]['citations'][0]['source_id'], 'F1')
        self.assertEqual(payload['claims'][0]['text'], payload['claims'][0]['citations'][0]['quote'])
        self.assertNotIn('ana@example.test', masked)
        self.assertEqual(payload['password'], '[[REGULAI_SECRET]]')
        self.assertIn('1.234567890123456789', masked)
        self.assertEqual(masked.count('"n":'), 2)
        actual = '{"claims":[{"text":"Email ana@example.test","citations":[{"id":"S1","quote":"Email ana@example.test"}]}]}'
        actual_result = json.loads(local_masking.mask_local_texts([actual], timeout=30)[0])
        self.assertEqual(actual_result['claims'][0]['citations'][0]['id'], 'S1')
        untrusted = '{"source_id":"ana@example.test","alias":"12345678Z","maria@example.test":"value"}'
        transformed = local_masking.mask_local_texts([untrusted], timeout=30)[0]
        for sensitive in ('ana@example.test', '12345678Z', 'maria@example.test'):
            self.assertNotIn(sensitive, transformed)

    def test_known_field_label_is_preserved_while_its_value_is_masked(self):
        result = local_masking.mask_local_texts(['Tarjeta: 4111 1111 1111 1111'], timeout=30)[0]
        self.assertTrue(result.startswith('Tarjeta: '))
        self.assertNotIn('4111', result)

    def test_model_unavailable_changed_or_failed_never_returns_original(self):
        for error in (RuntimeError('Missing model'), OSError('Unreadable model')):
            with self.subTest(error=type(error).__name__), patch.object(local_masking, '_load_model', side_effect=error):
                with self.assertRaises(type(error)):
                    local_masking.mask_local_texts(['ana@example.test'])
        nlp, identity = local_masking._load_model()
        with patch.object(local_masking, 'detector_metadata', return_value={**identity, 'model_files_sha256': 'changed'}):
            with self.assertRaises(RuntimeError):
                local_masking.mask_local_texts(['ana@example.test'])

    def test_limits_language_timeout_and_idempotence(self):
        for values in ([], ['ok', None], ['x' * (local_masking.MAX_BATCH_BYTES + 1)]):
            with self.subTest(values_type=type(values).__name__), self.assertRaises(ValueError):
                local_masking.mask_local_texts(values)
        with self.assertRaises(ValueError):
            local_masking.mask_local_texts(['bonjour'], language='fr')
        with self.assertRaises(TimeoutError):
            local_masking.mask_local_texts(['hola'], timeout=0)
        once = local_masking.mask_local_texts(['Correo ana@example.test y DNI 12345678Z'], timeout=30)
        self.assertEqual(local_masking.mask_local_texts(once, timeout=30), once)

    def test_concurrent_batches_do_not_retain_or_share_personal_values(self):
        with ThreadPoolExecutor(max_workers=3) as executor:
            results = list(executor.map(lambda text: local_masking.mask_local_texts([text], timeout=30),
                ['alpha@example.test', 'beta@example.test', 'gamma@example.test']))
        for result in results:
            self.assertEqual(result, ['[[REGULAI_EMAIL]]'])
