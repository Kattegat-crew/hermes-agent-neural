#!/usr/bin/env python3
"""Replay del guard `read-before-patch` sobre state.db (CA11, 02-design.md §2.5).

Herramienta de diagnóstico: SOLO LECTURA sobre la base (sqlite mode=ro).
Reconstruye, por sesión y en orden de id de mensaje, la secuencia de
read_file / write_file / patch / edit_file con las mismas reglas del guard
y reporta cuántos patch históricos habrían sido bloqueados.

Reglas del replay (idénticas al guard, sin huella de disco — no hay histórico
de mtime/size, así que "visto" = leído o escrito por el propio agente):
  - read_file(path) / write_file(path)  -> marca path como visto
  - patch/edit_file(path) sin path visto -> would_block
  - rutas absolutas se normalizan con os.path.realpath; las relativas no se
    pueden resolver (no hay cwd histórico): cuentan igual y se marcan aparte.
  - path_form_suspects: patch bloqueado cuyo basename fue leído/escrito antes
    en la misma sesión bajo OTRA forma de ruta (falso positivo probable).
"""

import argparse
import collections
import json
import os
import sqlite3
import sys
import time

DEFAULT_DB = "/opt/hermes-agent-data/state.db"
EDIT_TOOLS = {"patch", "edit_file"}
MARK_TOOLS = {"read_file", "write_file"}
WRITE_TOOLS = {"write_file", "patch", "edit_file"}


def extract_calls(tool_calls):
    """Devuelve [(tool_name, arguments_json_str)] de la celda tool_calls.

    Soporta el formato canónico [{'function': {'name', 'arguments'}}] y la
    variante con 'name'/'arguments' al nivel superior.
    """
    try:
        arr = json.loads(tool_calls)
    except (TypeError, ValueError):
        return []
    if isinstance(arr, dict):
        arr = [arr]
    if not isinstance(arr, list):
        return []
    out = []
    for c in arr:
        if not isinstance(c, dict):
            continue
        fn = c.get("function")
        if isinstance(fn, dict) and fn.get("name"):
            out.append((fn["name"], fn.get("arguments") or "{}"))
        elif c.get("name"):
            out.append((c["name"], c.get("arguments") or "{}"))
    return out


def get_path(arguments):
    try:
        a = json.loads(arguments)
    except (TypeError, ValueError):
        return None
    if not isinstance(a, dict):
        return None
    p = a.get("path")
    return p if isinstance(p, str) and p else None


def replay(db_path, last=None):
    con = sqlite3.connect("file:%s?mode=ro" % db_path, uri=True)
    try:
        if last:
            # últimas N sesiones con actividad (por su mensaje más reciente)
            subq = """
                SELECT session_id FROM messages
                WHERE active = 1 AND tool_calls IS NOT NULL AND tool_calls != ''
                GROUP BY session_id ORDER BY MAX(id) DESC LIMIT ?
            """
            rows = con.execute(
                """SELECT m.session_id, m.id, m.tool_calls FROM messages m
                   WHERE m.active = 1 AND m.tool_calls IS NOT NULL AND m.tool_calls != ''
                     AND m.session_id IN (%s)
                   ORDER BY m.session_id, m.id""" % subq,
                (last,),
            ).fetchall()
        else:
            rows = con.execute(
                """SELECT session_id, id, tool_calls FROM messages
                   WHERE active = 1 AND tool_calls IS NOT NULL AND tool_calls != ''
                   ORDER BY session_id, id"""
            ).fetchall()
    finally:
        con.close()

    sessions_any = set()          # sesiones con al menos un tool call
    sessions_write = set()        # sesiones con write_file/patch/edit_file con path
    per_sess_block = collections.Counter()
    state = {}                    # sid -> {'abs': set, 'rel': set, 'forms': {base: set}}

    patch_total = 0
    rel_patch_total = 0
    writes_total = 0
    would_block = 0
    rel_would_block = 0
    suspects = 0

    for sid, _mid, tc in rows:
        calls = extract_calls(tc)
        if calls:
            sessions_any.add(sid)
        st = state.setdefault(
            sid, {"abs": set(), "rel": set(), "forms": collections.defaultdict(set)}
        )
        for name, args in calls:
            p = get_path(args)
            if not p:
                continue
            is_rel = not os.path.isabs(p)
            real = None if is_rel else os.path.realpath(p)
            base = os.path.basename(p)
            form = ("rel", p) if is_rel else ("abs", real)

            if name in MARK_TOOLS:
                # visto: read_file o write_file de esa ruta en esta sesión
                (st["rel"] if is_rel else st["abs"]).add(p if is_rel else real)
                st["forms"][base].add(form)

            if name in WRITE_TOOLS:
                writes_total += 1
                sessions_write.add(sid)

            if name in EDIT_TOOLS:
                patch_total += 1
                if is_rel:
                    rel_patch_total += 1
                seen = (p in st["rel"]) if is_rel else (real in st["abs"])
                if not seen:
                    would_block += 1
                    if is_rel:
                        rel_would_block += 1
                    per_sess_block[sid] += 1
                    if any(f != form for f in st["forms"].get(base, ())):
                        suspects += 1
                # replay = guard (ronda 2): un patch/edit_file exitoso escribe la
                # ruta, así que el guard registra la huella posterior y un segundo
                # patch de la misma ruta NO se bloquea. Sin esto el replay infla
                # los bloqueos (cuenta reintentos idénticos que el guard permite).
                (st["rel"] if is_rel else st["abs"]).add(p if is_rel else real)
                st["forms"][base].add(form)

    pct = round(100.0 * would_block / writes_total, 1) if writes_total else 0.0
    return {
        "sessions_analyzed": len(set(r[0] for r in rows)),
        "sessions_with_activity": len(sessions_any),
        "patch_total": patch_total,
        "writes_total": writes_total,
        "would_block": would_block,
        "would_block_pct": pct,
        "sessions_affected": len(per_sess_block),
        "sessions_with_writes": len(sessions_write),
        "path_form_suspects": suspects,
        "relative_path_patches": rel_patch_total,
        "relative_path_would_block": rel_would_block,
        "top_sessions": [
            {"session_id": s, "would_block": n}
            for s, n in per_sess_block.most_common(10)
        ],
    }


def report(events):
    """Replay en memoria del guard sobre una lista de eventos (contrato CA11).

    events: [{'session_id', 'tool', 'path', 'ok'}] en orden cronológico, con
    tool ∈ {read_file, write_file, patch, edit_file} y ok=True (los ok falsy se
    descartan: solo lecturas/escrituras exitosas marcan rutas como vistas).

    Aplica las reglas del guard SIN huella de disco ("visto" = leído o escrito
    antes por la misma sesión), resolviendo la forma de la ruta con
    os.path.normpath (no hay cwd ni disco históricos para realpath):

    - patch_total: patch/edit_file considerados.
    - would_block: los que el guard habría bloqueado (ruta nunca vista, ya
      normalizada — coincide con la decisión real del hook).
    - path_form_suspects: lista de eventos de patch que sí vieron el archivo
      pero bajo OTRA forma de ruta (p. ej. '/b/./z.py' vs '/b/z.py'): frágiles,
      habrían sido falsos positivos de una comparación de cadena cruda.

    Devuelve dict con patch_total, would_block, would_block_pct (sobre
    patch_total), path_form_suspects y contadores auxiliares.
    """
    seen_forms = {}   # sid -> {norm: set(formas crudas vistas)}
    suspects = []
    per_sess_block = collections.Counter()
    patch_total = 0
    would_block = 0

    for ev in events or []:
        if not isinstance(ev, dict) or not ev.get("ok", True):
            continue
        sid = str(ev.get("session_id") or ev.get("sid") or "unknown")
        tool = str(ev.get("tool") or ev.get("tool_name") or "")
        p = ev.get("path")
        if not isinstance(p, str) or not p:
            continue
        norm = os.path.normpath(p)
        forms = seen_forms.setdefault(sid, collections.defaultdict(set))

        if tool in MARK_TOOLS:
            # read_file/write_file exitosos marcan la ruta como vista
            forms[norm].add(p)
            continue
        if tool not in EDIT_TOOLS:
            continue

        patch_total += 1
        if norm in forms:
            # ya visto (normalizado): permitido, igual que el guard con realpath
            if p not in forms[norm]:
                suspects.append({"session_id": sid, "path": p, "seen_as": sorted(forms[norm])})
        else:
            would_block += 1
            per_sess_block[sid] += 1
        # un patch exitoso marca su propia ruta (el agente sabe lo que escribió)
        forms[norm].add(p)

    return {
        "patch_total": patch_total,
        "would_block": would_block,
        "would_block_pct": (100.0 * would_block / patch_total) if patch_total else 0.0,
        "path_form_suspects": suspects,
        "sessions_affected": len(per_sess_block),
        "top_sessions": [
            {"session_id": s, "would_block": n} for s, n in per_sess_block.most_common(10)
        ],
    }


def print_table(d):
    print("Replay read-before-patch (CA11) — reglas idénticas al guard")
    print()
    print("  patch_total             %6d   (patch/edit_file con path)" % d["patch_total"])
    print("  writes_total            %6d   (write_file+patch+edit_file con path)" % d["writes_total"])
    print("  would_block             %6d" % d["would_block"])
    print("  would_block_pct         %5s%%   (sobre writes_total, convención de la spec)" % d["would_block_pct"])
    print("  sessions_affected       %6d   de %d con escrituras" % (d["sessions_affected"], d["sessions_with_writes"]))
    print("  sessions_with_writes    %6d   de %d con actividad" % (d["sessions_with_writes"], d["sessions_with_activity"]))
    print("  path_form_suspects      %6d   (mismo basename, otra forma de ruta)" % d["path_form_suspects"])
    print("  relative_path_patches   %6d   (%d serían bloqueados; sin cwd histórico no se resuelven)"
          % (d["relative_path_patches"], d["relative_path_would_block"]))
    if d["top_sessions"]:
        print()
        print("  Top 10 sesiones por bloqueos:")
        for i, t in enumerate(d["top_sessions"], 1):
            print("  %2d. %-28s %4d" % (i, t["session_id"], t["would_block"]))


def main():
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--db", default=DEFAULT_DB, help="ruta a state.db (default: %(default)s)")
    ap.add_argument("--last", type=int, default=None, help="solo las últimas N sesiones con actividad")
    ap.add_argument("--json", action="store_true", help="salida JSON en vez de tabla legible")
    ns = ap.parse_args()

    if not os.path.exists(ns.db):
        print("ERROR: no existe %s" % ns.db, file=sys.stderr)
        return 1

    t0 = time.monotonic()
    data = replay(ns.db, last=ns.last)
    elapsed = time.monotonic() - t0
    data["db"] = os.path.abspath(ns.db)
    data["elapsed_s"] = round(elapsed, 2)

    if ns.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print_table(data)
        print()
        print("  db: %s | elapsed: %.2fs" % (data["db"], data["elapsed_s"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
