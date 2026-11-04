#!/usr/bin/env python3
"""docx_inplace.py - edicion quirurgica de un .docx existente conservando formato.

Requiere python-docx. No renderiza PDF: para eso usar soffice (ver SKILL.md).

Uso:
  python3 docx_inplace.py dump DOC.docx                 # indice | estilo | negrita | largo | inicio
  python3 docx_inplace.py dump DOC.docx --find "ancla"  # parrafos que contienen el ancla
  python3 docx_inplace.py apply DOC.docx plan.json -o OUT.docx

plan.json: lista de operaciones aplicadas en orden. Cada una referencia su parrafo por
'anchor' (cadena unica de su texto). Falla si el ancla tiene 0 o 2 coincidencias.

  {"op": "replace_text", "anchor": "...", "text": "..."}
  {"op": "replace_span", "anchor": "...", "find": "...", "replace": "...", "expect": 1}
  {"op": "split_after",  "anchor": "...", "marker": "...", "text": "..."}
  {"op": "append",       "anchor": "...", "text": "..."}
  {"op": "append_italic","anchor": "...", "text": "..."}
  {"op": "remove_runs_from", "anchor": "...", "index": 2}
"""
import copy
import json
import sys

try:
    import docx
    from docx.text.paragraph import Paragraph
except ImportError:
    sys.exit("Falta python-docx: uv run --with python-docx python3 docx_inplace.py ...")


def find_para(doc, anchor):
    hits = [p for p in doc.paragraphs if anchor in p.text]
    if len(hits) != 1:
        raise SystemExit(f"ancla {anchor!r}: {len(hits)} coincidencias (se exige 1)")
    return hits[0]


def set_text(p, text):
    if not p.runs:
        p.add_run(text)
        return
    first = p.runs[0]
    for r in p.runs[1:]:
        r._element.getparent().remove(r._element)
    first.text = text


def add_run_like(p, text, italic=False):
    run = p.add_run(text)
    if italic:
        run.italic = True
    if p.runs and p.runs[0]._element.rPr is not None and run._element.rPr is None:
        run._element.insert(0, copy.deepcopy(p.runs[0]._element.rPr))
        if italic:
            run.italic = True
    return run


def apply_op(doc, op):
    kind = op["op"]
    p = find_para(doc, op["anchor"])

    if kind == "replace_text":
        set_text(p, op["text"])

    elif kind == "replace_span":
        old, new = op["find"], op["replace"]
        expect = int(op.get("expect", 1))
        hit = 0
        for r in p.runs:
            if old in r.text:
                r.text = r.text.replace(old, new)
                hit += r.text.count(new) if old == new else 1
        if hit != expect:
            raise SystemExit(
                f"replace_span {old!r}: {hit} reemplazos (se esperaban {expect}). "
                "Si es 0, el texto esta partido entre runs: normalizar primero."
            )

    elif kind == "split_after":
        marker = op["marker"]
        text = p.text
        idx = text.find(marker)
        if idx < 0:
            raise SystemExit(f"split_after: marcador {marker!r} ausente del parrafo")
        cut = idx + len(marker)
        head, tail = text[:cut].strip(), text[cut:].strip()
        set_text(p, head)
        el = copy.deepcopy(p._p)
        p._p.addnext(el)
        q = Paragraph(el, p._parent)
        set_text(q, op.get("text") or tail)

    elif kind == "append":
        add_run_like(p, op["text"])

    elif kind == "append_italic":
        add_run_like(p, op["text"], italic=True)

    elif kind == "remove_runs_from":
        idx = int(op["index"])
        for r in p.runs[idx:]:
            r._element.getparent().remove(r._element)

    else:
        raise SystemExit(f"operacion desconocida: {kind}")

    return kind


def main(argv):
    if len(argv) < 3:
        sys.exit(__doc__)
    cmd, src = argv[1], argv[2]

    if cmd == "dump":
        doc = docx.Document(src)
        needle = None
        if "--find" in argv:
            needle = argv[argv.index("--find") + 1]
        for i, p in enumerate(doc.paragraphs):
            if needle and needle not in p.text:
                continue
            bold = bool(p.runs and p.runs[0].bold)
            print(f"{i:3d} | {p.style.name:12.12} | b={int(bold)} | {len(p.text):5d} | {p.text[:80]!r}")
        return

    if cmd == "apply":
        plan_path = argv[3]
        out = None
        if "-o" in argv:
            out = argv[argv.index("-o") + 1]
        doc = docx.Document(src)
        with open(plan_path, encoding="utf-8") as fh:
            plan = json.load(fh)
        done = [apply_op(doc, op) for op in plan]
        doc.save(out or src)
        print(json.dumps({"ok": True, "ops": done, "out": out or src}, ensure_ascii=False))
        return

    sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv)
