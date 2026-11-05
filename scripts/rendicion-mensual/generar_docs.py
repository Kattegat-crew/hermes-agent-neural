#!/usr/bin/env python3
"""generar_docs.py — genera los DOCX+PDF de rendición del mes, editando IN-PLACE la
plantilla del mes anterior con python-docx y convirtiendo a PDF con LibreOffice,
igual que se hizo para octubre 2026 (plantilla sep -> entrega oct).

Reglas:
  - NUNCA inventa cifras: un campo sin_dato en facts se escribe como
    "sin dato (pendiente de consolidación)" y queda listado en el informe.
  - Con --dry-run no escribe nada: imprime el plan de reemplazos.
  - Los textos narrativos largos NO se regeneran automáticamente: se actualizan
    tokens de mes, tablas estructuradas y sustituciones valor->valor cuando se
    pasa --facts-prev; el informe lista los párrafos con cifras residuales del
    mes de la plantilla para revisión humana (gate Plon antes de entregar).

uso:
  python3 generar_docs.py --mes 2026-11 \
      --template-golden Rendicion_Oct2026_Golden_Game.docx \
      --template-lucky  Rendicion_Oct2026_Lucky_Brothers.docx \
      --facts-golden facts_golden.json --facts-lucky facts_lucky.json \
      [--facts-prev-golden ... --facts-prev-lucky ...] \
      --outdir DIR [--dry-run]

Requiere python-docx (venv: /opt/hermes-agent-data/cache/scratch/venv-docs) y soffice.
"""
import argparse
import copy
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import zoneinfo

BOGOTA = zoneinfo.ZoneInfo("America/Bogota")
VENV_PY = "/opt/hermes-agent-data/cache/scratch/venv-docs/bin/python"

MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto",
         "Septiembre", "Octubre", "Noviembre", "Diciembre"]


def fmt_cop(v):
    return "$" + f"{round(v):,}".replace(",", ".")


def fmt_pct(v):
    return f"{round(v, 1):.1f}".replace(".", ",") + "%"


def cif(F, cid):
    for c in F.get("cifras", []):
        if c["id"] == cid:
            return c
    return None


def valor_o_pendiente(F, cid, fmt=None):
    c = cif(F, cid)
    if c is None or c.get("sin_dato"):
        return "sin dato (pendiente de consolidación)"
    return fmt(c["valor"]) if fmt else c.get("display", str(c.get("valor")))


def token_map(mes, hoy):
    """Pares (viejo, nuevo) de tokens de mes entre la plantilla (mes-1) y el mes nuevo."""
    pm = mes.month - 1 or 12
    py = mes.year - 1 if mes.month == 1 else mes.year
    old, new = MESES[pm - 1], MESES[mes.month - 1]
    mapa = {}
    for o, n in ((old, new), (old.lower(), new.lower()), (old.upper(), new.upper())):
        mapa[o] = n
    mapa[f"{old[:3]}{py}"] = f"{new[:3]}{mes.year}"          # Sep2026 -> Oct2026
    mapa[f"{old[:3].lower()}{py}"] = f"{new[:3].lower()}{mes.year}"
    mapa[f"rend{old[:3].lower()}{py}"] = f"rend{new[:3].lower()}{mes.year}"  # NLC-rendsep2026
    mapa[f"{py}-{pm:02d}"] = f"{mes.year}-{mes.month:02d}"   # 2026-09 -> 2026-10
    # más largos primero para no partir tokens
    return sorted(mapa.items(), key=lambda kv: -len(kv[0]))


def replace_in_paragraph(para, pairs):
    hits = []
    for a, b in pairs:
        if a in para.text:
            hits.append(a)
            for run in para.runs:
                if a in run.text:
                    run.text = run.text.replace(a, b)
            if a in para.text:  # token partido entre runs: reemplazo grueso
                full = para.text.replace(a, b)
                if para.runs:
                    para.runs[0].text = full
                    for run in para.runs[1:]:
                        run.text = ""
    return hits


def set_cell(cell, text):
    para = cell.paragraphs[0]
    if para.runs:
        para.runs[0].text = text
        for run in para.runs[1:]:
            run.text = ""
    else:
        para.add_run(text)
    for extra in cell.paragraphs[1:]:
        for run in extra.runs:
            run.text = ""


def find_table(doc, headers):
    for tb in doc.tables:
        if len(tb.rows) < 1:
            continue
        h = [c.text.strip().lower() for c in tb.rows[0].cells]
        if all(any(hh in c for c in h) for hh in headers):
            return tb
    return None


def rebuild_sedes_table(tb, sedes, facts_incompleto):
    """Tabla 'Sede | Venta | Meta | Cumplimiento': reconstruye filas desde facts."""
    ncols = len(tb.columns)
    hdr = tb.rows[0]
    data_trs = [r._tr for r in tb.rows[1:]]
    tmpl_tr = data_trs[-1] if data_trs else None
    # recorto filas sobrantes
    while len(tb.rows) - 1 > len(sedes):
        tb._tbl.remove(tb.rows[-1]._tr)
    # añado filas faltantes clonando la última
    while len(tb.rows) - 1 < len(sedes):
        if tmpl_tr is None:
            break
        tb._tbl.append(copy.deepcopy(tmpl_tr))
    for i, s in enumerate(sedes):
        cells = tb.rows[i + 1].cells
        vals = [s["nombre"], fmt_cop(s["venta"])]
        if "meta" in s:
            vals += [fmt_cop(s["meta"]), fmt_pct(s["cumplimiento"])]
        else:
            vals += ["sin dato", "sin dato"]
        for j, v in enumerate(vals[:ncols]):
            set_cell(cells[j], v)


def parse_nota(nota):
    """Extrae pares tipo ('impresiones', 17536) del campo nota."""
    out = {}
    if not nota:
        return out
    m = re.search(r"([\d.,]+)\s*impresiones", nota)
    if m:
        out["impresiones"] = int(float(m.group(1).replace(".", "").replace(",", "")))
    m = re.search(r"([\d.,]+)\s*clics", nota)
    if m:
        out["clics"] = int(float(m.group(1).replace(".", "").replace(",", "")))
    m = re.search(r"CTR\s*([\d.,]+)%", nota)
    if m:
        out["ctr"] = m.group(1).replace(".", ",") + "%"
    m = re.search(r"([\d.,]+)\s*alcance", nota)
    if m:
        out["alcance"] = int(float(m.group(1).replace(".", "").replace(",", "")))
    return out


def update_value_tables(doc, F):
    """Actualiza tablas estructuradas cuyo primer encabezado identifica la tabla."""
    changed = []

    tb = find_table(doc, ["indicador"])
    if tb is not None:
        breb_c = cif(F, "breb_total")
        breb_val = valor_o_pendiente(F, "breb_total")
        rows = {
            "visibilidad": valor_o_pendiente(F, "facebook"),
            "alcance principal": valor_o_pendiente(F, "facebook"),
            "instagram": valor_o_pendiente(F, "instagram"),
            "inversión": valor_o_pendiente(F, "ads_total"),
            "bre-b": breb_val,
            "ventas del mes vs meta": (f"{valor_o_pendiente(F, 'ventas_netas', fmt_cop)} vs. "
                                       f"{valor_o_pendiente(F, 'meta_ventas', fmt_cop)}"),
            "ventas vs. meta": (f"{valor_o_pendiente(F, 'ventas_netas', fmt_cop)} vs. "
                                f"{valor_o_pendiente(F, 'meta_ventas', fmt_cop)}"),
            "horas automatizadas": valor_o_pendiente(F, "automatizacion_horas"),
            "tráfico orgánico": valor_o_pendiente(F, "organico"),
        }
        for r in tb.rows[1:]:
            label = r.cells[0].text.strip().lower()
            for k, v in rows.items():
                if k in label and v:
                    if r.cells[1].text.strip() != v:
                        set_cell(r.cells[1], v)
                        changed.append(f"resumen[{label}] -> {v[:40]}")
                    break

    tb = find_table(doc, ["sede", "venta"])
    if tb is not None:
        if F.get("sedes"):
            rebuild_sedes_table(tb, F["sedes"], F.get("incompleto", False))
            changed.append(f"tabla sedes reconstruida ({len(F['sedes'])} filas)")
        else:
            changed.append("tabla sedes SIN tocar (facts sin sedes)")

    tb = find_table(doc, ["totales del mes", "inversión"])
    if tb is not None:
        c = cif(F, "ads_total")
        n = parse_nota(c.get("nota", "") if c and not c.get("sin_dato") else "")
        if c and not c.get("sin_dato"):
            vals = [fmt_cop(c["valor"]), f"{n.get('impresiones', 'n/d'):,}".replace(",", ".") if isinstance(n.get("impresiones"), int) else "sin dato",
                    f"{n.get('clics', 'n/d'):,}".replace(",", ".") if isinstance(n.get("clics"), int) else "sin dato",
                    valor_o_pendiente(F, "ads_leads")]
            for j, v in enumerate(vals[:len(tb.columns)], start=1):
                if len(tb.rows) > 1 and tb.rows[1].cells[j].text.strip() != v:
                    set_cell(tb.rows[1].cells[j], v)
                    changed.append(f"tabla pauta col{j} -> {v}")
        else:
            changed.append("tabla pauta SIN tocar (ads sin_dato)")

    tb = find_table(doc, ["métrica", "valor"])
    if tb is not None:
        c = cif(F, "organico")
        n = parse_nota(c.get("nota", "") if c and not c.get("sin_dato") else "")
        imp = n.get("impresiones")
        if imp is None and c and not c.get("sin_dato"):
            imp = c["valor"]  # display '96 impresiones' -> el valor es el count
        clics = n.get("clics")
        if clics is None and c and not c.get("sin_dato"):
            m = re.search(r"(\d[\d.]*) clics", c.get("nota", ""))
            clics = int(m.group(1).replace(".", "")) if m else None
        rows = {"impresiones orgánicas": str(imp) if imp is not None else "sin dato",
                "clics": str(clics) if clics is not None else "sin dato",
                "ctr": n.get("ctr", "sin dato")}
        for r in tb.rows[1:]:
            label = r.cells[0].text.strip().lower()
            for k, v in rows.items():
                if k in label and v:
                    if r.cells[1].text.strip() != v:
                        set_cell(r.cells[1], v)
                        changed.append(f"tabla orgánico[{label}] -> {v}")
                    break

    tb = find_table(doc, ["tarea"])
    if tb is not None:
        # filas por agente (lucky) quedan intactas; en golden la fila del agente es el total
        agent_rows = [r for r in tb.rows[1:] if "agente" in r.cells[0].text.strip().lower()]
        skip_agents = len(agent_rows) > 1
        pairs = {"total": valor_o_pendiente(F, "agentes"),
                 "horas": valor_o_pendiente(F, "automatizacion_horas")}
        for r in tb.rows[1:]:
            label = r.cells[0].text.strip().lower()
            if skip_agents and "agente" in label:
                continue  # fila por agente: no se toca
            for k, v in pairs.items():
                if k in label and v:
                    if r.cells[1].text.strip() != v:
                        set_cell(r.cells[1], v)
                        changed.append(f"tabla tareas[{label}] -> {v}")
                    break
    return changed


def value_substitutions(doc, F_prev, F_new):
    """Sustituye valor_display viejo -> nuevo en párrafos narrativos (solo con --facts-prev)."""
    subs, residuales = [], []
    for c in F_new.get("cifras", []):
        if c.get("sin_dato") or "valor" not in c:
            continue
        pc = cif(F_prev, c["id"]) if F_prev else None
        if pc and not pc.get("sin_dato") and pc.get("display") != c["display"]:
            subs.append((pc["display"], c["display"]))
    for para in doc.paragraphs:
        for a, b in subs:
            if a in para.text:
                replace_in_paragraph(para, [(a, b)])
    # cifras residuales del mes anterior (informativo para revisión humana)
    pat = re.compile(r"\$[\d.,]+|\d+,\d%")
    for para in doc.paragraphs:
        t = para.text.strip()
        if t and pat.search(t) and len(t) > 40:
            residuales.append(t[:110])
    return subs, residuales


def process_brand(brand_label, template, facts_path, facts_prev_path, outdir, mes, dry_run, verbose):
    try:
        from docx import Document
    except ModuleNotFoundError:
        # re-ejecutar con el venv que tiene python-docx
        if os.path.exists(VENV_PY):
            os.execv(VENV_PY, [VENV_PY, os.path.abspath(__file__)] + sys.argv[1:])
        raise
    F = json.load(open(facts_path, encoding="utf-8"))
    F_prev = None
    if facts_prev_path and os.path.exists(facts_prev_path):
        F_prev = json.load(open(facts_prev_path, encoding="utf-8"))
    hoy = dt.datetime.now(BOGOTA).date()
    pairs = token_map(mes, hoy)

    doc = Document(template)
    log = [f"[{brand_label}] plantilla: {template}"]

    # 1) tokens de mes en cuerpo, tablas y pies
    n_tok = 0
    for para in doc.paragraphs:
        n_tok += len(replace_in_paragraph(para, pairs))
    for tb in doc.tables:
        for row in tb.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    n_tok += len(replace_in_paragraph(para, pairs))
    for sec in doc.sections:
        for cont in (sec.header, sec.footer):
            for para in cont.paragraphs:
                n_tok += len(replace_in_paragraph(para, pairs))
            for tb in cont.tables:
                for row in tb.rows:
                    for cell in row.cells:
                        for para in cell.paragraphs:
                            n_tok += len(replace_in_paragraph(para, pairs))
    log.append(f"  tokens de mes reemplazados: {n_tok}")

    # 2) FECHA del membrete
    for tb in doc.tables:
        for row in tb.rows:
            cells = row.cells
            for i, c in enumerate(cells):
                if c.text.strip().upper() == "FECHA:" and i + 1 < len(cells):
                    nueva = hoy.isoformat()
                    if not dry_run or cells[i + 1].text.strip() != nueva:
                        set_cell(cells[i + 1], nueva)
                    log.append(f"  FECHA membrete -> {nueva}")

    # 3) tablas estructuradas desde facts
    if not dry_run or True:
        changed = update_value_tables(doc, F)
        log += ["  " + c for c in changed]

    # 4) sustituciones valor->valor en narrativa (solo con facts del mes de la plantilla)
    residuales = []
    if facts_prev_path:
        subs, residuales = value_substitutions(doc, F_prev, F)
        log.append(f"  sustituciones valor->valor: {len(subs)}")
    else:
        log.append("  (sin --facts-prev: narrativa con cifras de la plantilla queda "
                   "para revisión humana)")
    # residuales SIEMPRE: párrafos narrativos con cifras que exigen revisión humana
    if not residuales:
        pat = re.compile(r"\$[\d.,]+|\d+,\d%")
        for para in doc.paragraphs:
            t = para.text.strip()
            if t and len(t) > 40 and pat.search(t):
                residuales.append(t[:110])

    # 5) guard: tokens viejos restantes
    leftovers = []
    full_text = "\n".join(p.text for p in doc.paragraphs)
    for tb in doc.tables:
        for row in tb.rows:
            for cell in row.cells:
                full_text += "\n" + cell.text
    for a, b in pairs:
        if a in full_text and a[:3].lower() != "2026":
            leftovers.append(a)
    if leftovers:
        log.append(f"  AVISO: tokens de mes sin reemplazar: {sorted(set(leftovers))}")

    sin_dato_ids = [c["id"] for c in F.get("cifras", []) if c.get("sin_dato")]
    if sin_dato_ids:
        log.append(f"  campos 'sin dato (pendiente)': {', '.join(sin_dato_ids)}")

    base = os.path.basename(template)
    newname = re.sub(r"(Sep|Oct|Nov|Dic|Ene|Feb|Mar|Abr|May|Jun|Jul|Ago)[_ ]?20\d\d",
                     f"{MESES[mes.month - 1][:3]}{mes.year}", base)
    out_docx = os.path.join(outdir, newname)
    if dry_run:
        log.append(f"  DRY-RUN: se escribiría {out_docx} (+PDF)")
        return log, residuales

    doc.save(out_docx)
    log.append(f"  DOCX: {out_docx}")
    r = subprocess.run(["soffice", "--headless", "--convert-to", "pdf", "--outdir", outdir,
                        out_docx], capture_output=True, text=True, timeout=300)
    pdf = os.path.splitext(out_docx)[0] + ".pdf"
    if os.path.exists(pdf):
        log.append(f"  PDF: {pdf}")
    else:
        log.append(f"  ERROR soffice: {r.stderr[-300:]}")
    return log, residuales


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mes", required=True, help="YYYY-MM del informe (del mes ANTERIOR sale la plantilla)")
    ap.add_argument("--template-golden", required=True)
    ap.add_argument("--template-lucky", required=True)
    ap.add_argument("--facts-golden", required=True)
    ap.add_argument("--facts-lucky", required=True)
    ap.add_argument("--facts-prev-golden", default=None)
    ap.add_argument("--facts-prev-lucky", default=None)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
    y, m = args.mes.split("-")
    mes = dt.date(int(y), int(m), 1)
    os.makedirs(args.outdir, exist_ok=True)

    all_residuales = []
    for label, tmpl, facts, prev in [
        ("golden", args.template_golden, args.facts_golden, args.facts_prev_golden),
        ("lucky", args.template_lucky, args.facts_lucky, args.facts_prev_lucky),
    ]:
        log, residuales = process_brand(label, tmpl, facts, prev, args.outdir, mes,
                                        args.dry_run, args.verbose)
        all_residuales += residuales
        print("\n".join(log))

    # informe de revisión humana
    rep = os.path.join(args.outdir, "revision_pendiente.md")
    if not args.dry_run:
        with open(rep, "w", encoding="utf-8") as fh:
            fh.write(f"# Revisión humana pendiente — rendición {args.mes}\n\n"
                     "Párrafos con cifras que el reemplazo automático no garantiza "
                     "(verificar contra facts antes de entregar):\n\n")
            for t in all_residuales:
                fh.write(f"- {t}\n")
        print(f"informe de revisión: {rep} ({len(all_residuales)} párrafos a revisar)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
