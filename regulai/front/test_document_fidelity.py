"""Public extraction regressions; fixtures contain synthetic content only."""
import io
import zipfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase

from front.documents import extract_document


class FidelityTests(SimpleTestCase):
    def extract(self, name, content):
        return extract_document(SimpleUploadedFile(name, content))

    def archive(self, files):
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, content in files.items():
                archive.writestr(name, content)
        return output.getvalue()

    def test_text_encodings_formfeed_and_bm_are_not_binary(self):
        for content in ("BM invoice\fPrice: 17 €".encode("utf-8"),
                        "Price: 17 €".encode("utf-16"), "Price: 17 €".encode("cp1252")):
            with self.subTest(content=content):
                document = self.extract("invoice.txt", content)
                self.assertEqual(document.status, "complete")
                self.assertIn("Price: 17 €", document.text)
        assumed = self.extract("invoice.txt", "Price: 17 €".encode("cp1252"))
        self.assertEqual(assumed.metadata()["disclosures"], [
            {"code": "encoding_assumed", "count": 1, "locators": ["document"]}])
        self.assertEqual(self.extract("invalid.txt", b"x\x81").status, "unreadable")

