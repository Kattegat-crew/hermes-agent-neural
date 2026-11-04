#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""markdown → docx sin pandoc. Uso: python3 md2docx.py entrada.md salida.docx
Soporta: #/##/###/#### encabezados, tablas markdown (| ... |), listas -/* y 1.,
bloques ```, negritas, hr. Probado en 26/08/2026 (python-docx 1.2.0).
"""
import re, sys
from docx import Document
from docx.shared import Pt


def render_table(doc, rows):
    ncol = max(len(r) for r in rows)
    table = doc.add_table(rows=len(rows), cols=ncol)
    table.style = "Light Grid Accent 1"
    for i, r in enumerate(rows):
        for j in range(ncol):
            val = r[j] if j < len(r) else ""
            cell = table.cell(i, j)
            cell.text = val
            for par in cell.paragraphs:
                for run in par.runs:
                    run.font.size = Pt(8.5)
                    if i == 0:
                        run.bold = True


def convert(src, out):
    doc = Document()
    lines = open(src, encoding="utf-8").read().split("\n")
    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln.strip().startswith("```"):
            buf = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            p = doc.add_paragraph()
            r = p.add_run("\n".join(buf))
            r.font.name = "Consolas"
            r.font.size = Pt(8)
            continue
        if ln.strip().startswith("|") and i + 1 < len(lines) and re.match(
            r"^\|[\s:\-|]+\|?$", lines[i + 1].strip()
        ):
            rows = [[c.strip() for c in ln.strip().strip("|").split("|")]]
            j = i + 2
            while j < len(lines) and lines[j].strip().startswith("|"):
                rows.append([c.strip() for c in lines[j].strip().strip("|").split("|")])
                j += 1
            render_table(doc, rows)
            i = j
            continue
        done = False
        for level, prefix in ((1, "# "), (2, "## "), (3, "### "), (4, "#### ")):
            if ln.startswith(prefix):
                doc.add_heading(ln[len(prefix):], level=level)
                done = True
                break
        if done:
            i += 1
            continue
        m = re.match(r"\s*[-*] (.+)", ln)
        if m and not ln.strip().startswith("<!--"):
            doc.add_paragraph(m.group(1), style="List Bullet")
        elif re.match(r"^\s*\d+\.\s+(.+)$", ln):
            doc.add_paragraph(re.match(r"^\s*\d+\.\s+(.+)$", ln).group(1), style="List Number")
        elif re.match(r"^\s*-{3,}\s*$", ln) or not ln.strip():
            pass
        else:
            p = doc.add_paragraph(re.sub(r"\*\*(.+?)\*\*", r"\1", ln))
            for run in p.runs:
                run.font.size = Pt(10.5)
        i += 1
    doc.save(out)
    print("OK ->", out)


if __name__ == "__main__":
    convert(sys.argv[1], sys.argv[2])