import json

from django.test import SimpleTestCase

from .verification import normalize_finish_reason, verify_response


class VerificationTests(SimpleTestCase):
    fragments = [{"id": "current-document:1", "locator": "paragraph:1",
                  "text": "The contract states: revenue is 10 euros.\nNo refund is available."}]

    def document(self, text="Revenue is 10 euros.", identifier="current-document:1",
                 quote="revenue is 10 euros."):
        return json.dumps({"claims": [{"text": text,
                                      "citations": [{"id": identifier, "quote": quote}]}]})

    def test_local_checks_never_claim_semantic_truth(self):
        result = verify_response("A plausible answer.", "stop")
        self.assertEqual(result["local_status"], "passed")
        self.assertEqual(result["status"], "not_verified")
        self.assertEqual(result["checks"][-1], {"code": "semantic", "status": "not_verified"})

    def test_completion_reasons_and_empty_content_fail_before_any_judgment(self):
        for content, reason, expected in [("answer", "length", "truncated"),
                                           ("answer", "max_tokens", "truncated"),
                                           ("answer", "content_filter", "refused"),
                                           ("answer", "new_finish_reason", "unknown"),
                                           ("", "stop", "complete")]:
            with self.subTest(reason=reason):
                result = verify_response(content, reason, require_semantic=False)
                self.assertEqual(result["status"], "failed")
                self.assertEqual(result["finish_reason"], expected)
        self.assertEqual(normalize_finish_reason("end_turn"), "complete")

    def test_literal_citation_resolves_server_evidence_but_does_not_prove_claim(self):
        result = verify_response(self.document(text="Revenue is 900 euros."), "stop",
                                 fragments=self.fragments)
        self.assertEqual(result["local_status"], "passed")
        self.assertEqual(result["status"], "not_verified")
        self.assertEqual(result["evidence"], [{"claim_index": 0, "id": "current-document:1",
                                              "locator": "paragraph:1",
                                              "excerpt": "revenue is 10 euros."}])

    def test_forged_external_and_previous_document_ids_are_not_sources(self):
        for identifier in ["previous-document:1", "https://example.test/source",
                           "C:/private.txt", "<img src=x onerror=alert(1)>"]:
            with self.subTest(identifier=identifier):
                result = verify_response(self.document(identifier=identifier), "stop",
                                         fragments=self.fragments)
                self.assertEqual(result["status"], "failed")
                self.assertEqual(result["checks"][-2]["reason"], "unknown_citation")
                self.assertEqual(result["evidence"], [])

    def test_literal_normalization_only_allows_whitespace_changes(self):
        whitespace = verify_response(self.document(quote="revenue\n is  10 euros."), "stop",
                                     fragments=self.fragments)
        self.assertEqual(whitespace["local_status"], "passed")
        for quote in ["Revenue is 10 euros.", "revenue is 10 euros!", "revenue is 100 euros."]:
            with self.subTest(quote=quote):
                result = verify_response(self.document(quote=quote), "stop", fragments=self.fragments)
                self.assertEqual(result["status"], "failed")
                self.assertEqual(result["checks"][-2]["reason"], "quote_not_found")

    def test_invalid_json_missing_citations_and_forged_locator_fail(self):
        forged = json.loads(self.document())
        forged["claims"][0]["citations"][0]["locator"] = "page:999"
        for content in ["```json\n{}\n```", '{"claims": []}',
                        '{"claims": [{"text": "claim", "citations": []}]}', json.dumps(forged)]:
            with self.subTest(content=content):
                result = verify_response(content, "stop", fragments=self.fragments)
                self.assertEqual(result["status"], "failed")
                self.assertEqual(result["evidence"], [])

    def test_html_in_current_source_is_plain_evidence_text(self):
        literal = "<script>alert('not executed')</script>"
        result = verify_response(self.document(quote=literal), "stop",
                                 fragments=[{**self.fragments[0], "text": literal}])
        self.assertEqual(result["status"], "not_verified")
        self.assertEqual(result["evidence"][0]["excerpt"], literal)

    def test_evidence_is_bounded_and_never_copies_full_document(self):
        long_source = [{**self.fragments[0], "text": "x" * 10000 + "revenue is 10 euros." + "z" * 10000}]
        result = verify_response(self.document(), "stop", fragments=long_source)
        self.assertEqual(result["evidence"][0]["excerpt"], "revenue is 10 euros.")
        overlong = verify_response(self.document(quote="x" * 1601), "stop", fragments=long_source)
        self.assertEqual(overlong["status"], "failed")
        self.assertEqual(overlong["checks"][-2]["reason"], "invalid_quote")

    def test_document_citations_always_need_semantic_judgment(self):
        result = verify_response(self.document(), "stop", fragments=self.fragments,
                                 require_semantic=False)
        self.assertEqual(result["status"], "not_verified")

    def test_invalid_unicode_and_duplicate_json_fields_fail_safely(self):
        invalid_unicode = verify_response("\ud800", "stop")
        self.assertEqual(invalid_unicode["status"], "failed")
        duplicate = self.document().replace('"claims":', '"claims": [], "claims":')
        result = verify_response(duplicate, "stop", fragments=self.fragments)
        self.assertEqual(result["status"], "failed")
