"""Security follow-up: duplicate JSON fields must not hide a retained credential."""
from unittest.mock import patch

from django.test import SimpleTestCase

from security_probes_final import CredentialCaptureProbes


def duplicated_field(value):
    encoded = ''.join('\\u%04x' % ord(char) for char in value)
    return ('{"error":"' + encoded + '","error":"public-synthetic-message"}').encode()


class DuplicateFieldCredentialProbes(SimpleTestCase):
    def test_duplicate_httpx_response_field_does_not_hide_reflected_credential(self):
        with patch('security_probes_final.escaped_json', duplicated_field):
            CredentialCaptureProbes.test_httpx_unicode_escaped_reflection_is_not_persisted(self)

    def test_duplicate_requests_response_field_does_not_hide_reflected_credential(self):
        with patch('security_probes_final.escaped_json', duplicated_field):
            CredentialCaptureProbes.test_requests_unicode_escaped_reflection_is_not_persisted(self)
