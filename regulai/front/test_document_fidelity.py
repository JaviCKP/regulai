"""Public extraction regressions; fixtures contain synthetic content only."""
import io
import zipfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from docx import Document as WordDocument
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from PIL import Image

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

    def word_bytes(self, word):
        output = io.BytesIO()
        word.save(output)
        return output.getvalue()

    def test_word_accepts_changes_and_link_text_without_field_instructions(self):
        word = WordDocument()
        paragraph = word.add_paragraph()
        deleted = OxmlElement("w:del")
        run = OxmlElement("w:r")
        text = OxmlElement("w:delText")
        text.text = "30"
        run.append(text)
        deleted.append(run)
        paragraph._p.append(deleted)
        inserted = OxmlElement("w:ins")
        run = OxmlElement("w:r")
        text = OxmlElement("w:t")
        text.text = "17 days "
        run.append(text)
        inserted.append(run)
        paragraph._p.append(inserted)
        instruction = OxmlElement("w:instrText")
        instruction.text = "HYPERLINK mailto:private@example.invalid"
        paragraph._p.append(instruction)
        link = OxmlElement("w:hyperlink")
        link.set(qn("r:id"), word.part.relate_to("mailto:private@example.invalid",
            "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink", is_external=True))
        run = OxmlElement("w:r")
        text = OxmlElement("w:t")
        text.text = "Contact"
        run.append(text)
        link.append(run)
        paragraph._p.append(link)
        document = self.extract("changes.docx", self.word_bytes(word))
        self.assertEqual(document.status, "complete")
        self.assertEqual(document.text, "17 days Contact")
        self.assertEqual(document.disclosures, [{"code": "tracked_changes_present", "count": 2,
            "locators": ["word/document.xml/paragraph:1"]}])

    def test_word_discloses_header_images_attachments_equations_and_symbols(self):
        word = WordDocument()
        paragraph = word.add_paragraph("Readable body")
        symbol = OxmlElement("w:sym")
        symbol.set(qn("w:char"), "F0A7")
        paragraph._p.append(symbol)
        paragraph._p.append(OxmlElement("m:oMath"))
        bitmap = io.BytesIO()
        Image.new("RGB", (2, 2), "white").save(bitmap, "PNG")
        bitmap.seek(0)
        word.sections[0].header.paragraphs[0].add_run().add_picture(bitmap)
        with zipfile.ZipFile(io.BytesIO(self.word_bytes(word))) as source:
            files = {name: source.read(name) for name in source.namelist()}
        files["word/embeddings/object1.bin"] = b"synthetic attachment"
        document = self.extract("visual.docx", self.archive(files))
        self.assertEqual(document.status, "complete_text_only")
        disclosures = {item["code"]: item for item in document.disclosures}
        for code in ("images_unread", "attachments_unread", "equations_unread", "symbols_unread"):
            self.assertEqual(disclosures[code]["count"], 1)
            self.assertTrue(disclosures[code]["locators"])
        self.assertIn("Readable body", document.text)
        self.assertNotIn("synthetic attachment", document.text)

    def test_word_renders_decimal_multilevel_numbering_and_declares_other_formats(self):
        word = WordDocument()
        definition = OxmlElement("w:abstractNum")
        definition.set(qn("w:abstractNumId"), "42")
        for level in range(3):
            node = OxmlElement("w:lvl")
            node.set(qn("w:ilvl"), str(level))
            for name, value in (("start", "1"), ("numFmt", "decimal" if level < 2 else "lowerRoman"),
                                ("lvlText", "%1." if level == 0 else "%1.%2.")):
                child = OxmlElement("w:" + name)
                child.set(qn("w:val"), value)
                node.append(child)
            definition.append(node)
        word.part.numbering_part.element.append(definition)
        numbering = OxmlElement("w:num")
        numbering.set(qn("w:numId"), "42")
        abstract = OxmlElement("w:abstractNumId")
        abstract.set(qn("w:val"), "42")
        numbering.append(abstract)
        word.part.numbering_part.element.append(numbering)
        for level, text in ((0, "First"), (1, "Child"), (1, "Next child"), (0, "Second"), (1, "Reset child"), (2, "Roman")):
            paragraph = word.add_paragraph(text)
            properties = paragraph._p.get_or_add_pPr().get_or_add_numPr()
            properties.get_or_add_numId().val = 42
            properties.get_or_add_ilvl().val = level
        document = self.extract("numbered.docx", self.word_bytes(word))
        self.assertEqual(document.status, "complete_text_only")
        self.assertEqual(document.text, "1. First\n1.1. Child\n1.2. Next child\n2. Second\n2.1. Reset child\nRoman")
        self.assertEqual(document.disclosures, [{"code": "numbering_unsupported", "count": 1,
            "locators": ["word/document.xml/paragraph:6"]}])
