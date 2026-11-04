#!/usr/bin/env python3
"""NeuralCrew Labs letterhead v5 — refined, thin rules via paragraph borders.
Eliminates heavy gold bars. Clean, executive, professional.
"""
import os, io
from PIL import Image
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn, nsdecls
from docx.oxml import parse_xml

GOLD = RGBColor(0xD4, 0xAF, 0x37)
BLACK = RGBColor(0x1A, 0x1A, 0x1A)
DGRAY = RGBColor(0x3A, 0x3A, 0x3A)
MGRAY = RGBColor(0x70, 0x70, 0x70)
FONT = "Calibri"

ICON = "/root/hermes-agent-legacy-docker/data/workspace/logo_icon.png"
OUT = "/root/hermes-agent-legacy-docker/data/workspace/NeuralCrew_Labs_Membrete_Oficial.docx"

doc = Document()
sec = doc.sections[0]
sec.page_width, sec.page_height = Cm(21.59), Cm(27.94)
sec.top_margin = Cm(1.7)
sec.bottom_margin = Cm(1.7)
sec.left_margin = Cm(2.2)
sec.right_margin = Cm(2.2)

normal = doc.styles['Normal']
normal.font.name = FONT
normal.font.size = Pt(10.5)
normal.font.color.rgb = BLACK

def gold_bottom_border(paragraph, sz=8):
    pPr = paragraph._p.get_or_add_pPr()
    pPr.append(parse_xml(
        f'<w:pBdr {nsdecls("w")}><w:bottom w:val="single" w:sz="{sz}" w:space="2" w:color="D4AF37"/></w:pBdr>'))

def clean(tbl):
    tblPr = tbl._tbl.tblPr
    tblPr.append(parse_xml(
        f'<w:tblBorders {nsdecls("w")}>'
        f'<w:top w:val="none" w:sz="0"/><w:left w:val="none" w:sz="0"/>'
        f'<w:bottom w:val="none" w:sz="0"/><w:right w:val="none" w:sz="0"/>'
        f'<w:insideH w:val="none" w:sz="0"/><w:insideV w:val="none" w:sz="0"/>'
        f'</w:tblBorders>'))

def cb(cell):
    cell._tc.get_or_add_tcPr().append(parse_xml(
        f'<w:tcBorders {nsdecls("w")}>'
        f'<w:top w:val="none" w:sz="0"/><w:left w:val="none" w:sz="0"/>'
        f'<w:bottom w:val="none" w:sz="0"/><w:right w:val="none" w:sz="0"/>'
        f'</w:tcBorders>'))

def t(rows, cols, widths=None, align_center=False):
    tbl = doc.add_table(rows=rows, cols=cols)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER if align_center else WD_TABLE_ALIGNMENT.LEFT
    # Force FIXED layout so column widths are respected (otherwise Word/Drive
    # auto-distributes by content and the wide wordmark wraps: "W" drops).
    try:
        tbl.autofit = False
    except Exception:
        pass
    tblPr = tbl._tbl.tblPr
    # remove any autofit element and set layout=fixed + total width
    tblPr.append(parse_xml(
        f'<w:tblLayout {nsdecls("w")} w:type="fixed"/>'))
    tblPr.append(parse_xml(
        f'<w:tblW {nsdecls("w")} w:w="{int(sum(widths)*567) if widths else 9900}" w:type="dxa"/>'))
    tblPr.append(parse_xml(
        f'<w:tblCellMar {nsdecls("w")}>'
        f'<w:top w:w="0" w:type="dxa"/><w:left w:w="0" w:type="dxa"/>'
        f'<w:bottom w:w="0" w:type="dxa"/><w:right w:w="0" w:type="dxa"/>'
        f'</w:tblCellMar>'))
    clean(tbl)
    for r in tbl.rows:
        for i, c in enumerate(r.cells):
            cb(c)
            if widths and i < len(widths):
                c.width = Cm(widths[i])
                # also set tcW directly
                tcPr = c._tc.get_or_add_tcPr()
                tcPr.append(parse_xml(
                    f'<w:tcW {nsdecls("w")} w:w="{int(widths[i]*567)}" w:type="dxa"/>'))
    return tbl

# ── TOP GOLD THIN RULE ─────────────────────────────────
ptop = doc.add_paragraph()
ptop.paragraph_format.space_after = Pt(2)
ptop.paragraph_format.space_before = Pt(0)
ptop._p.get_or_add_pPr().append(parse_xml(
    f'<w:pBdr {nsdecls("w")}><w:top w:val="single" w:sz="12" w:space="1" w:color="D4AF37"/></w:pBdr>'))

# ── HEADER: icon + wordmark ───────────────────────────
hdr = t(1, 2, [2.8, 13.4])
icon_cell, name_cell = hdr.rows[0].cells

p_icon = icon_cell.paragraphs[0]
p_icon.alignment = WD_ALIGN_PARAGRAPH.CENTER
p_icon.paragraph_format.space_before = Pt(0)
if os.path.exists(ICON):
    with Image.open(ICON) as im:
        im = im.convert("RGBA"); im.thumbnail((400,400), Image.Resampling.LANCZOS)
        buf = io.BytesIO(); im.save(buf, "PNG"); buf.seek(0)
        p_icon.add_run().add_picture(buf, height=Cm(2.1))

p_n1 = name_cell.paragraphs[0]
p_n1.paragraph_format.space_before = Pt(3)
p_n1.paragraph_format.space_after = Pt(0)
r = p_n1.add_run("NEURALCREW")
r.bold = True; r.font.size = Pt(22); r.font.color.rgb = BLACK; r.font.name = FONT

p_n2 = name_cell.add_paragraph()
p_n2.paragraph_format.space_before = Pt(0)
p_n2.paragraph_format.space_after = Pt(2)
r = p_n2.add_run("LABS")
r.bold = True; r.font.size = Pt(16); r.font.color.rgb = GOLD; r.font.name = FONT
gold_bottom_border(p_n2, 4)

p_tag = name_cell.add_paragraph()
p_tag.paragraph_format.space_before = Pt(3)
p_tag.paragraph_format.space_after = Pt(0)
r = p_tag.add_run("Inteligencia artificial aplicada a tu negocio")
r.italic = True; r.font.size = Pt(9); r.font.color.rgb = DGRAY; r.font.name = FONT

# ── metadata ──────────────────────────────────────────
def put(cell_label, cell_val, label, val):
    p0 = cell_label.paragraphs[0]; p0.paragraph_format.space_before = Pt(6)
    p0.paragraph_format.space_after = Pt(0)
    r0 = p0.add_run(label + ":"); r0.bold=True; r0.font.size=Pt(7.5); r0.font.color.rgb=MGRAY
    p1 = cell_val.paragraphs[0]; p1.paragraph_format.space_before = Pt(6)
    p1.paragraph_format.space_after = Pt(0)
    r1 = p1.add_run(val); r1.font.size=Pt(7.5); r1.font.color.rgb=BLACK

m1 = t(1, 4, [2.4, 5.6, 2.4, 3.4])
c0,c1,c2,c3 = m1.rows[0].cells
put(c0, c1, "CLIENTE", "")
put(c2, c3, "FECHA", "")

m2 = t(1, 4, [2.4, 5.6, 2.4, 5.4])
c0,c1,c2,c3 = m2.rows[0].cells
put(c0, c1, "ASUNTO", "")
put(c2, c3, "DOC. Nº", "NLC-0001")

# ── Title ────────────────────────────────────────────────
tp = doc.add_paragraph()
tp.alignment = WD_ALIGN_PARAGRAPH.CENTER
tp.paragraph_format.space_before = Pt(18)
tp.paragraph_format.space_after = Pt(10)
r = tp.add_run("[TÍTULO DEL DOCUMENTO]")
r.bold=True; r.font.size=Pt(19); r.font.color.rgb=BLACK; r.font.name=FONT
gold_bottom_border(tp, 8)

# ── body ─────────────────────────────────────────────────
def heading(txt):
    h = doc.add_paragraph()
    h.paragraph_format.space_before = Pt(14); h.paragraph_format.space_after = Pt(5)
    r1 = h.add_run(txt); r1.bold=True; r1.font.size=Pt(12.5); r1.font.color.rgb=BLACK; r1.font.name=FONT

def body(txt):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(8); p.paragraph_format.line_spacing = 1.2
    r = p.add_run(txt); r.font.size=Pt(10.5); r.font.color.rgb=DGRAY; r.font.name=FONT

heading("1.  Introducción")
body("Este documento fue elaborado por NeuralCrew Labs como parte de los servicios contratados. La información contenida es de carácter confidencial y de uso exclusivo para el cliente señalado en la cabecera.")

heading("2.  Alcance del servicio")
for it in ["Análisis de mercado y benchmarking competitivo",
           "Implementación y cronograma de trabajo",
           "Definición de métricas y KPIs de rendimiento",
           "Recomendaciones y plan de acción prioritario"]:
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(4); p.paragraph_format.left_indent = Cm(0.4)
    rb = p.add_run("•  "); rb.font.color.rgb=GOLD; rb.font.size=Pt(10); rb.bold=True
    rt = p.add_run(it); rt.font.size=Pt(10.5); rt.font.color.rgb=DGRAY

heading("3.  Aprobación")
body("Confirmado por el cliente, el presente alcance da inicio a la ejecución. Los entregables serán revisados y aprobados en cada fase del proceso.")

# ── footer ────────────────────────────────────────────────
f = sec.footer
fp = f.paragraphs[0]; fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
fp.paragraph_format.space_before = Pt(8)
r = fp.add_run("NeuralCrew Labs   ·   Bogotá   |   3166910728   ·   captain@neuralcrewlabs.com")
r.font.size=Pt(8); r.font.color.rgb=MGRAY; r.font.name=FONT

os.makedirs(os.path.dirname(OUT), exist_ok=True)
doc.save(OUT)
print("SAVED:", OUT, os.path.getsize(OUT))