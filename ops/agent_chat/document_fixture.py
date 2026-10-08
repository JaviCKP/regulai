"""Synthetic corporate template for the task-51 engine acceptance experiment."""
from pathlib import Path
from docx import Document
from docx.enum.section import WD_SECTION
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


def create_template(path):
    doc = Document()
    for name in ('Normal', 'Title', 'Subtitle', 'Heading 1', 'Heading 2', 'List Number'):
        style = doc.styles[name]
        style.font.name = 'Liberation Sans'
        style.font.color.rgb = RGBColor.from_string('17365D' if name != 'Normal' else '222222')
    doc.styles['Normal'].font.size = Pt(11)
    for section in doc.sections:
        section.page_width, section.page_height = Inches(8.27), Inches(11.69)
        section.top_margin = section.bottom_margin = Inches(0.8)
        section.left_margin = section.right_margin = Inches(0.85)
    doc.sections[0].header.paragraphs[0].text = 'REGULAY · ÁREA TÉCNICA'
    footer = doc.sections[0].footer.paragraphs[0]
    footer.add_run('Página ')
    field = OxmlElement('w:fldSimple')
    field.set(qn('w:instr'), 'PAGE')
    footer._p.append(field)
    footer.add_run(' · Informe interno')
    doc.add_paragraph('{{TITLE}}', 'Title')
    doc.add_paragraph('España · Informe económico', 'Subtitle')
    doc.add_section(WD_SECTION.NEW_PAGE)
    doc.add_heading('Resumen ejecutivo', 1)
    doc.add_paragraph('{{SUMMARY}}')
    doc.add_paragraph('Comprobar los importes originales.', 'List Number')
    doc.add_paragraph('Conservar la trazabilidad de las revisiones.', 'List Number')
    doc.add_heading('Detalle de importes', 1)
    table = doc.add_table(rows=2, cols=2)
    table.style = 'Light Shading Accent 1'
    table.cell(0, 0).text, table.cell(0, 1).text = 'Concepto', 'Importe (€)'
    table.cell(1, 0).text, table.cell(1, 1).text = '{{ITEM}}', '{{AMOUNT}}'
    repeat = OxmlElement('w:tblHeader')
    table.rows[0]._tr.get_or_add_trPr().append(repeat)
    doc.add_section(WD_SECTION.NEW_PAGE)
    doc.add_heading('Notas de revisión', 1)
    doc.add_paragraph('Los importes se expresan en euros. Año 2026; revisión técnica.')
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(path)
    return path


if __name__ == '__main__':
    import sys
    create_template(sys.argv[1])
