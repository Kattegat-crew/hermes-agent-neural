#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Helpers de edicion quirurgica de .docx conservando formato.

Uso como modulo:
    from docx_surgical import open_doc, set_text, clone_after, rep, check

Uso por CLI (verificacion rapida de un entregable):
    python3 docx_surgical.py check out.docx \
        --forbid "Completar,bogotá,TODO" \
        --expect "Edetania. Estudios y Propuestas Socioeducativas"
"""
import argparse
import copy
import re
import sys

import docx
from docx.text.paragraph import Paragraph


def open_doc(path):
    return docx.Document(path)


def set_text(p, text):
    """Reemplaza el texto conservando pPr y el rPr del primer run.

    Solo es seguro cuando el parrafo tiene formato homogeneo. Para
    parrafos de referencia (normal + italica) reconstruir los runs a
    mano: p.add_run('. '), run en cursiva, run normal con el resto.
    """
    runs = p.runs
    if not runs:
        p.add_run(text)
        return p
    first = runs[0]
    for r in runs[1:]:
        r._element.getparent().remove(r._element)
    first.text = text
    return p


def clone_after(p, text):
    """Clona el parrafo completo (estilo, alineacion, sangria) y lo
    inserta justo despues: la forma correcta de partir un parrafo."""
    new_el = copy.deepcopy(p._p)
    p._p.addnext(new_el)
    new_p = Paragraph(new_el, p._parent)
    set_text(new_p, text)
    return new_p


def rep(p, old, new):
    """Reemplazo dentro de un run. Falla ruidosamente si no hay match,
    para que ningun cambio se pierda en silencio."""
    for r in p.runs:
        if old in r.text:
            r.text = r.text.replace(old, new)
            return p
    raise SystemExit(f"NO MATCH en {p.text[:70]!r}: {old[:60]!r}")


def para_text(doc):
    return "\n".join(p.text for p in doc.paragraphs)


def check(path, forbid=(), expect=(), cite_scan=True):
    """Verificacion de entregable: placeholders prohibidos, textos
    esperados y citas con/sin entrada en referencias."""
    d = docx.Document(path)
    t = para_text(d)
    lines, ok = [], True

    lines.append(f"parrafos={len(d.paragraphs)} palabras={len(t.split())}")

    for bad in forbid:
        hit = bad in t
        lines.append(f"  prohibido {bad!r}: {'PRESENTE' if hit else 'ausente'}")
        ok = ok and not hit

    for good in expect:
        hit = good in t
        lines.append(f"  esperado {good[:40]!r}: {'ok' if hit else 'FALTA'}")
        ok = ok and hit

    if cite_scan:
        refs = t.split("Referencias")[-1] if "Referencias" in t else t
        pat = r"\(([A-ZÁÉÍÓÚÑ][^()]{2,40}?),\s*(?:19|20)\d{2}"
        intext = sorted({m.strip() for m in re.findall(pat, t)})
        lines.append(f"  autores citados en texto: {len(intext)}")
        for a in intext[:25]:
            surname = a.split(" y ")[0].split(" et al")[0].strip()
            if surname and surname not in refs:
                lines.append(f"    revisar entrada de referencia: {a}")

    return ok, lines


def main(argv=None):
    ap = argparse.ArgumentParser(description="Edicion/verificacion quirurgica de .docx")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="verifica un entregable")
    c.add_argument("path")
    c.add_argument("--forbid", default="", help="textos separados por coma que NO deben aparecer")
    c.add_argument("--expect", default="", help="textos separados por coma que SI deben aparecer")
    c.add_argument("--no-cites", action="store_true", help="omite el escaneo de citas")
    args = ap.parse_args(argv)

    if args.cmd == "check":
        forbid = tuple(x.strip() for x in args.forbid.split(",") if x.strip())
        expect = tuple(x.strip() for x in args.expect.split(",") if x.strip())
        ok, lines = check(args.path, forbid, expect, cite_scan=not args.no_cites)
        print("\n".join(lines))
        print("RESULTADO:", "OK" if ok else "REVISAR")
        return 0 if ok else 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
