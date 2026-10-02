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

    def test_csv_dialects_preserve_cells_in_compact_rows(self):
        for separator in (",", ";", "\t", "|"):
            content = f'name{separator}note\nAda{separator}"first\nsecond"\n'.encode()
            with self.subTest(separator=separator):
                document = self.extract("sheet.csv", content)
                self.assertEqual(document.status, "complete")
                self.assertEqual(len(document.fragments), 2)
                self.assertEqual(document.fragments[1]["locator"], "row:2/cells:A2-B2")
                self.assertEqual(document.fragments[1]["text"], "A2: Ada\tB2: first\nsecond")
        document = self.extract("sheet.csv", "nombre;precio\nCafé;17 €\n".encode("cp1252"))
        self.assertEqual(document.status, "complete")
        self.assertIn("encoding_assumed", document.warnings)

    def test_text_groups_lines_without_losing_evidence_or_locations(self):
        content = ("ordinary text\n" * 1499 + "late evidence").encode()
        document = self.extract("large.txt", content)
        self.assertEqual(document.status, "complete")
        self.assertEqual(document.units_read, 1500)
        self.assertLess(len(document.fragments), 50)
        self.assertEqual(document.fragments[0]["locator"], "lines:1-40")
        self.assertEqual(document.fragments[-1]["locator"], "lines:1481-1500")
        self.assertTrue(document.text.endswith("late evidence"))
