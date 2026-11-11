#!/usr/bin/env python3
"""Inventario y propuesta de reparto de la memoria nativa (SOLO LECTURA).

Uso:
  python3 memory_inventory.py --profile default [--json out.json] [--md out.md] [--emit-plan plan.json]

Salida: estadísticas del store, tabla de entradas con cobertura por destino,
detección de duplicados y una propuesta de acción por entrada. Nunca escribe
MEMORY.md/USER.md; ``--emit-plan`` produce el esqueleto que el agente edita.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import memlib as M  # noqa: E402

BRAIN = Path("/opt/data/brain")
ARCHIVE_DIR = Path("/opt/data/brain/memoria-archivo")
STATE_DB = Path("/opt/hermes-agent-data/state.db")
ACTIONS = ("keep", "move", "merge", "archive", "discard")
JUNK_MIN_CHARS = 40
POINTER_MARK = "memoria nativa compactada"

CLIENT_HINTS = ("golden", "lucky", "paradise", "casino", "cliente", "digital expressions", "bendabal",
                "guaya", "kassiuss", "helmer", "yulieth", "jacqueline", "ivan", "alejandro")
# Entradas que narran algo ya ocurrido: son postmortem, no regla operativa.
EVENT_RE = re.compile(r"\b(cierre|cerrad[oa]s?|hecho|ejecutad[oa]|desplegad[oa]|completad[oa]|entregad[oa]|"
                      r"ok admin|verificado el|resuelt[oa]|postmortem|incidente|auditor[ií]a|"
                      r"reorganizaci[oó]n|plan de mantenimiento|migrad[oa])\b", re.I)


def classify(entry: str) -> dict:
    """Señales de la entrada. Un postmortem largo no se vuelve invariante por decir 'nunca' al final."""
    head = entry[:200]
    inv = bool(M.INVARIANT_RE.search(entry))
    if inv and len(entry) > 700 and not M.INVARIANT_RE.search(head):
        inv = False
    return {
        "fecha": bool(M.DATE_RE.search(entry)),
        "procedimiento": bool(M.PROC_RE.search(entry)),
        "invariante": inv,
        "cliente": any(h in entry.lower() for h in CLIENT_HINTS),
        "evento": bool(EVENT_RE.search(head)),
    }


def slugify(text: str, max_len: int = 40) -> str:
    import re
    s = re.sub(r"[^a-z0-9]+", "-", text.lower())
    return (s.strip("-")[:max_len] or "nota").strip("-")


def is_junk(entry: str) -> bool:
    """Restos de prueba o fragmentos sin contenido útil."""
    t = entry.strip()
    if len(t) < JUNK_MIN_CHARS:
        return True
    return t.lower().strip(" .") in ("test entry", "test", "prueba", "pendiente")


def is_log_entry(entry: str) -> bool:
    """Recibos de consolidación anteriores: son log, no conocimiento."""
    return entry.strip().lower().startswith(POINTER_MARK)


def value_score(chars: int, cov_best: float, signals: dict, reuse: float = 0.0) -> float:
    """Prioridad para quedarse cargada en cada sesión (no es una métrica de calidad).

    ``reuse`` = fracción de sus datos duros que volvieron a aparecer en las sesiones
    posteriores a la última consolidación. Un invariante manda sobre la cobertura:
    que el dato esté 'cubierto' en el brain no lo hace prescindible en el prompt,
    porque el brain solo se consulta si alguien decide consultarlo.
    """
    score = 0.0
    if signals["invariante"]:
        score += 60
        score += 10 * (1 - min(cov_best, 1.0))
    else:
        score += 35 * (1 - min(cov_best, 1.0))
    if signals["procedimiento"]:
        score += 18
    if signals["cliente"]:
        score += 8
    score += max(0.0, 25 - chars / 60)
    if signals["fecha"]:
        score -= 12
    if signals.get("evento") and reuse < 0.25:
        # Postmortem cerrado que nadie volvió a usar: no debe ocupar el prompt.
        score -= 35
    # Reuso medido: si sus datos duros se usaron esta semana, es contexto vivo, no archivo.
    score += 45 * min(reuse, 1.0)
    if reuse >= 0.5:
        score += 25
    return round(score, 1)


def route_non_keep(row: dict) -> tuple[str, str, str]:
    """(acción, kind, motivo) para una entrada que sale del bloque always-on."""
    cov, chars = row["coverage"], row["chars"]
    entry = row.get("_text") or row.get("text") or ""
    best = max(cov, key=cov.get)
    if is_junk(entry):
        return "discard", "archive", "ruido: entrada de prueba o fragmento sin contenido"
    if is_log_entry(entry):
        return "discard", "archive", "log de consolidación anterior: vive en el recibo, no en el prompt"
    if row["signals"]["invariante"]:
        # Regla dura: un invariante NO se archiva aunque el brain lo mencione.
        kind = "skill" if row["signals"]["procedimiento"] else "vault"
        return "move", kind, "invariante de comportamiento: se lee antes de actuar, nunca se archiva"
    if cov[best] >= 0.75 and chars > 250:
        hc = (row.get("hard_coverage") or {}).get(best, 0.0)
        if hc >= 0.45:
            return "archive", "archive", f"cubierto en {best} ({cov[best]:.0%} léxico, {hc:.0%} datos duros)"
        return "archive", "archive", (f"parecido a {best} ({cov[best]:.0%}) pero SIN sus datos duros "
                                      f"({hc:.0%}): no es duplicado real — queda verbatim en el archivo")
    if row["paths"] and cov["repo"] >= cov["brain"] and chars > 350:
        return "move", "repo", "detalle operativo: se lee al trabajar en el repo"
    if row["signals"]["procedimiento"] and chars > 600:
        return "move", "skill", "procedimiento reutilizable: pertenece a una skill"
    if row["signals"]["cliente"] and chars > 500:
        return "move", "brain", "conocimiento de cliente/negocio de largo plazo"
    if row["signals"]["fecha"]:
        return "move", "engram", "episódico con fecha: recall por búsqueda (Engram)"
    return "archive", "archive", "bajo valor always-on: archivo verbatim + recall por token"


def audit_previous(target: str = "memory", live_chars: int | None = None) -> dict:
    """Audita la consolidación anterior contra las sesiones posteriores.

    Devuelve los datos duros de cada entrada archivada que volvieron a usarse después
    y el contador de datos duros del corpus de sesiones, para puntuar el reuso actual.
    """
    import re
    import sqlite3
    from collections import Counter

    receipts = sorted(ARCHIVE_DIR.glob(f"recibo-*-{target}-*.json"))
    if live_chars:
        # ignora recibos que describen el store que está en disco ahora (p.ej. tras un rollback):
        # comparar contra ellos da una ventana de minutos y ninguna señal.
        receipts = [p for p in receipts if not _receipt_matches_store(p, live_chars)] or receipts
    if not receipts:
        return {"receipt": None, "returned": [], "window_tokens": Counter(), "window_messages": 0}
    receipt_path = receipts[-1]
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"receipt": str(receipt_path), "returned": [], "window_tokens": Counter(), "window_messages": 0}

    since = None
    if receipt.get("applied_at"):
        try:
            since = datetime.strptime(receipt["applied_at"], "%Y%m%dT%H%M%SZ").replace(
                tzinfo=timezone.utc).timestamp()
        except ValueError:
            since = None

    window_tokens: Counter = Counter()
    messages = 0
    if STATE_DB.is_file():
        try:
            con = sqlite3.connect(f"file:{STATE_DB}?mode=ro", uri=True, timeout=5)
            sql = ("SELECT content FROM messages WHERE role IN ('user','assistant') AND active=1 "
                   "AND content IS NOT NULL AND length(content) > 40")
            params: tuple = ()
            if since:
                sql += " AND timestamp >= ?"
                params = (since,)
            for (content,) in con.execute(sql, params):
                messages += 1
                window_tokens.update(M.hard_tokens(content))
            con.close()
        except sqlite3.Error:
            pass

    archived: dict[int, str] = {}
    jsonl = receipt.get("archive_jsonl")
    if jsonl and Path(jsonl).is_file():
        for line in Path(jsonl).read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                archived[int(row["idx"])] = row.get("text", "")

    returned = []
    for idx, text in archived.items():
        toks = M.hard_tokens(text)
        hits = sorted({t for t in toks if window_tokens.get(t, 0) >= 2 and len(t) >= 6})
        if len(hits) >= 3:
            returned.append({"idx": idx, "hits": hits[:8], "summary": M.summarize(text, 110)})
    returned.sort(key=lambda r: -len(r["hits"]))
    return {"receipt": str(receipt_path), "since": receipt.get("applied_at"),
            "returned": returned, "window_tokens": window_tokens, "window_messages": messages}


def _receipt_matches_store(path: Path, live_chars: int) -> bool:
    try:
        rec = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    after, before = rec.get("chars_after"), rec.get("chars_before")
    # coincide si el store vivo es su resultado (chars_after) o su origen (chars_before,
    # p. ej. se aplicó y se revirtió): en ambos casos la ventana de sesiones no dice nada.
    return any(isinstance(v, int) and abs(v - live_chars) <= 80 for v in (after, before))


def reuse_ratio(entry: str, window_tokens) -> float:
    toks = M.hard_tokens(entry)
    if not toks or not window_tokens:
        return 0.0
    used = sum(1 for t in toks if window_tokens.get(t, 0) >= 2)
    return used / len(toks)


def build(args) -> dict:
    store = M.resolve_store(args.home, args.profile)
    path = M.target_path(store, args.target)
    raw = M.load_text(path, 5_000_000)
    entries = M.parse_entries(raw)
    limits = M.read_limits(store["config"])

    corpus = M.build_corpus(M.default_corpus_globs(Path(args.brain)), max_bytes=args.corpus_max_bytes)
    # cobertura léxica delata parecido; los datos duros delatan duplicado REAL.
    corpus_hard = {}
    for k, v in corpus.items():
        hs: set[str] = set()
        for t in v["texts"]:
            hs |= M.hard_tokens(t)
        corpus_hard[k] = hs
    entry_tokens = [M.distinctive_tokens(e) for e in entries]
    entry_words = [M.word_set(e) for e in entries]

    # auditoría de la consolidación anterior: qué datos duros volvieron a usarse después
    audit = audit_previous(args.target, len(raw)) if getattr(args, "audit", True) else {
        "receipt": None, "returned": [], "window_tokens": {}, "window_messages": 0}
    window = audit.get("window_tokens") or {}
    reuse = [reuse_ratio(e, window) for e in entries]

    # duplicados / supersedidos
    dup_of: dict[int, list[dict]] = {}
    for i in range(len(entries)):
        for j in range(i + 1, len(entries)):
            if min(len(entries[i]), len(entries[j])) < 80:
                continue
            ratio = min(len(entries[i]), len(entries[j])) / max(len(entries[i]), len(entries[j]))
            jac = M.jaccard(entry_words[i], entry_words[j])
            if jac >= 0.55 or (ratio >= 0.8 and jac >= 0.4):
                dup_of.setdefault(i + 1, []).append({"other": j + 1, "jaccard": round(jac, 2)})
                dup_of.setdefault(j + 1, []).append({"other": i + 1, "jaccard": round(jac, 2)})

    # mismo hecho contado dos veces: comparten >=2 datos duros (IDs, rutas, ficheros, cifras)
    hard = [M.hard_tokens(e) for e in entries]
    near_dup: dict[int, list[dict]] = {}
    for i in range(len(entries)):
        for j in range(i + 1, len(entries)):
            if min(len(entries[i]), len(entries[j])) < 150:
                continue
            shared = hard[i] & hard[j]
            if len(shared) < 2:
                continue
            jac = M.jaccard(entry_words[i], entry_words[j])
            if jac >= 0.35:
                dup_of.setdefault(i + 1, []).append(
                    {"other": j + 1, "jaccard": round(jac, 2), "shared_tokens": sorted(shared)[:4]})
                dup_of.setdefault(j + 1, []).append(
                    {"other": i + 1, "jaccard": round(jac, 2), "shared_tokens": sorted(shared)[:4]})
            else:
                near_dup.setdefault(i + 1, []).append(
                    {"other": j + 1, "shared_tokens": sorted(shared)[:4]})
                near_dup.setdefault(j + 1, []).append(
                    {"other": i + 1, "shared_tokens": sorted(shared)[:4]})

    rows = []
    for idx, entry in enumerate(entries, 1):
        toks = entry_tokens[idx - 1]
        cov = {k: round(M.coverage(toks, corpus[k]["tokens"]), 3) for k in corpus}
        hts = hard[idx - 1]
        hard_cov = {k: round(len(hts & corpus_hard[k]) / len(hts), 3) if hts else 0.0 for k in corpus}
        best_kind = max(cov, key=cov.get) if cov else "brain"
        paths = sorted(set(M.PATH_RE.findall(entry)))[:4]
        signals = classify(entry)
        row = {
            "idx": idx, "chars": len(entry), "sha1": M.sha1(entry), "summary": M.summarize(entry),
            "tokens": len(toks), "coverage": cov, "hard_coverage": hard_cov,
            "best_corpus": best_kind, "paths": paths,
            "signals": signals, "duplicates": dup_of.get(idx, []),
            "near_duplicates": near_dup.get(idx, []),
            "reuse": round(reuse[idx - 1], 2),
            "score": value_score(len(entry), cov[best_kind] if cov else 0.0, signals, reuse[idx - 1]),
            "proposed": {"action": "archive", "destination_kind": "archive", "reason": ""},
            "_text": entry,
        }
        rows.append(row)

    # presupuesto de memoria always-on: se conserva lo de mayor valor hasta llenar el cupo
    budget = int(limits[args.target] * args.keep_budget)
    for row in rows:
        if row["duplicates"]:
            target = row["duplicates"][0]["other"]
            row["proposed"] = {"action": "merge", "destination_kind": "memory",
                               "reason": f"duplicado/supersedido de #{target}"}
        elif is_junk(row["_text"]) or is_log_entry(row["_text"]):
            action, kind, reason = route_non_keep(row)
            row["proposed"] = {"action": action, "destination_kind": kind, "reason": reason}
    keep_rows = [r for r in rows if not r["duplicates"]
                 and not is_junk(r["_text"]) and not is_log_entry(r["_text"])]
    keep_rows.sort(key=lambda r: -r["score"])
    used, kept_idx = 0, set()
    for row in keep_rows:
        if used + row["chars"] <= budget:
            used += row["chars"]
            kept_idx.add(row["idx"])
            row["proposed"] = {"action": "keep", "destination_kind": "memory",
                               "reason": f"valor always-on alto (score {row['score']}) dentro del cupo"}
        else:
            action, kind, reason = route_non_keep(row)
            row["proposed"] = {"action": action, "destination_kind": kind, "reason": reason}
    rows.sort(key=lambda r: r["idx"])
    for row in rows:
        if row["proposed"]["reason"] == "":
            action, kind, reason = route_non_keep(row)
            row["proposed"] = {"action": action, "destination_kind": kind, "reason": reason}

    counts = {a: sum(1 for r in rows if r["proposed"]["action"] == a) for a in ACTIONS}
    keep_chars = sum(r["chars"] for r in rows if r["proposed"]["action"] in ("keep", "merge"))
    ctx = {
        "audit": {"receipt": audit.get("receipt"), "since": audit.get("since"),
                  "window_messages": audit.get("window_messages"),
                  "returned": audit.get("returned", [])},
        "format_defects": M.separator_defects(raw),
    }
    for row in rows:
        row.pop("_text", None)
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "host": "DEV", "profile": store["profile"], "target": args.target,
        "store_path": str(path), "config_path": str(store["config"]),
        "warnings": store["warnings"],
        "limits": limits,
        "audit": ctx["audit"], "format_defects": ctx["format_defects"],
        "stats": {
            "entries": len(rows), "chars": len(raw), "limit": limits[args.target],
            "pct": round(100 * len(raw) / limits[args.target], 1) if limits[args.target] else 0,
            "keep_budget": budget, "keep_chars": keep_chars,
            "projected_chars": keep_chars, "counts": counts,
            "corpus_files": {k: len(v["texts"]) for k, v in corpus.items()},
        },
        "entries": rows,
    }
    return result


def to_markdown(res: dict) -> str:
    s = res["stats"]
    out = [
        f"# Inventario de memoria nativa — {res['profile']} ({res['target']})",
        "",
        f"- Generado: {res['generated_at']}",
        f"- Store: `{res['store_path']}`",
        f"- Ocupación: **{s['chars']:,}/{s['limit']:,} chars ({s['pct']}%)** · {s['entries']} entradas",
        f"- Corpus indexado: " + " · ".join(f"{k}={v}" for k, v in s["corpus_files"].items()),
        f"- Proyección si se aplica la propuesta: **~{s['projected_chars']:,} chars** "
        f"(cupo always-on {s['keep_budget']:,}; {', '.join(f'{a}={n}' for a, n in s['counts'].items())})",
        "",
    ]
    if res["warnings"]:
        out += ["## Avisos", ""] + [f"- {w}" for w in res["warnings"]] + [""]
    aud = res.get("audit") or {}
    if aud.get("returned"):
        out += ["## Auditoría de la consolidación anterior", "",
                f"Recibo `{aud.get('receipt')}` aplicado {aud.get('since')}; "
                f"{aud.get('window_messages')} mensajes posteriores analizados.", "",
                "Entradas que se archivaron y cuyos datos duros **volvieron a usarse** después "
                "(si reaparecen, el archivado fue prematuro):", ""]
        for r in aud["returned"]:
            out.append(f"- #{r['idx']} · {r['summary']} · `{', '.join(r['hits'][:5])}`")
        out.append("")
    if res.get("format_defects"):
        out += [f"> Defecto de formato: {res['format_defects']} separador(es) `§` huérfano(s). "
                "`parse_entries` los normaliza al aplicar.", ""]
    out += ["| # | chars | propuesta | destino | reuso | cobertura b/r/s/v | resumen |",
            "|---|---|---|---|---|---|---|"]
    for r in res["entries"]:
        c = r["coverage"]
        out.append(f"| {r['idx']} | {r['chars']} | {r['proposed']['action']} | {r['proposed']['destination_kind']} | "
                   f"{r.get('reuse', 0):.2f} | "
                   f"{c['brain']:.2f}/{c['repo']:.2f}/{c['skill']:.2f}/{c['vault']:.2f} | {r['summary']} |")
    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="Inventario de la memoria nativa (solo lectura)")
    ap.add_argument("--home", default=None)
    ap.add_argument("--profile", default="default")
    ap.add_argument("--target", default="memory", choices=("memory", "user"))
    ap.add_argument("--json", dest="json_out", default=None)
    ap.add_argument("--md", dest="md_out", default=None)
    ap.add_argument("--emit-plan", default=None)
    ap.add_argument("--brain", default=str(BRAIN), help="raíz del brain a indexar como corpus")
    ap.add_argument("--keep-budget", type=float, default=0.45,
                    help="fracción del límite que se reserva al bloque always-on (0-1)")
    ap.add_argument("--corpus-max-bytes", type=int, default=1_500_000)
    ap.add_argument("--top", type=int, default=12, help="filas más pesadas a imprimir en stdout")
    ap.add_argument("--audit", dest="audit", action="store_true", default=True,
                    help="audita la consolidación anterior contra las sesiones posteriores (por defecto sí)")
    ap.add_argument("--no-audit", dest="audit", action="store_false")
    args = ap.parse_args()

    res = build(args)
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.md_out:
        Path(args.md_out).write_text(to_markdown(res), encoding="utf-8")
    if args.emit_plan:
        plan = {
            "schema": "memory-compaction/plan@1",
            "generated_at": res["generated_at"], "profile": res["profile"], "target": args.target,
            "store_path": res["store_path"],
            "entries": [{
                "idx": r["idx"], "sha1": r["sha1"], "chars": r["chars"], "summary": r["summary"],
                "action": r["proposed"]["action"],
                "destination": (
                    {"kind": r["proposed"]["destination_kind"], "path": "", "anchor": ""}
                    if r["proposed"]["action"] == "move" and r["proposed"]["destination_kind"] != "engram"
                    else ({"kind": "engram", "observation_id": None}
                          if r["proposed"]["destination_kind"] == "engram" and r["proposed"]["action"] == "move"
                          else None)),
                "merge_into": (r["duplicates"][0]["other"] if r["duplicates"] else None),
                "reason": r["proposed"]["reason"],
            } for r in res["entries"]],
        }
        Path(args.emit_plan).write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    s = res["stats"]
    print(f"store      : {res['store_path']}")
    print(f"ocupación  : {s['chars']:,}/{s['limit']:,} chars ({s['pct']}%) · {s['entries']} entradas")
    print(f"corpus     : {s['corpus_files']}")
    print(f"propuesta  : {s['counts']} -> proyectado {s['projected_chars']:,} chars")
    if res.get("format_defects"):
        print(f"AVISO      : {res['format_defects']} separador(es) § huérfano(s) (H4) — se normalizan al aplicar")
    aud = res.get("audit") or {}
    if aud.get("receipt"):
        print(f"auditoría  : {aud['since']} · {aud['window_messages']} mensajes posteriores · "
              f"{len(aud.get('returned') or [])} entradas archivadas que volvieron a usarse")
        for r in (aud.get("returned") or [])[:8]:
            print(f"   ↩ #{r['idx']:<3} {r['summary'][:70]} | {', '.join(r['hits'][:4])}")
    for w in res["warnings"]:
        print(f"AVISO      : {w}")
    print("\nentradas más pesadas:")
    for r in sorted(res["entries"], key=lambda x: -x["chars"])[: args.top]:
        print(f"  #{r['idx']:<3} {r['chars']:>6} chars  {r['proposed']['action']:<8} "
              f"{r['proposed']['destination_kind']:<8} reuso={r['reuse']:.2f} {r['summary'][:60]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
