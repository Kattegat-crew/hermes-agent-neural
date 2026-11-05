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
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import memlib as M  # noqa: E402

BRAIN = Path("/opt/data/brain")
ACTIONS = ("keep", "move", "merge", "archive", "discard")

CLIENT_HINTS = ("golden", "lucky", "paradise", "casino", "cliente", "digital expressions", "bendabal",
                "guaya", "kassiuss", "helmer", "yulieth", "jacqueline", "ivan", "alejandro")


def slugify(text: str, max_len: int = 40) -> str:
    import re
    s = re.sub(r"[^a-z0-9]+", "-", text.lower())
    return (s.strip("-")[:max_len] or "nota").strip("-")


def value_score(chars: int, cov_best: float, signals: dict) -> float:
    """Prioridad para quedarse cargada en cada sesión (no es una métrica de calidad)."""
    score = 0.0
    if signals["invariante"]:
        score += 45
    if signals["procedimiento"]:
        score += 18
    if signals["cliente"]:
        score += 8
    score += 35 * (1 - min(cov_best, 1.0))
    score += max(0.0, 25 - chars / 60)
    if signals["fecha"]:
        score -= 12
    return round(score, 1)


def route_non_keep(row: dict) -> tuple[str, str, str]:
    """(acción, kind, motivo) para una entrada que sale del bloque always-on."""
    cov, chars = row["coverage"], row["chars"]
    best = max(cov, key=cov.get)
    if cov[best] >= 0.75 and chars > 250:
        return "archive", "archive", f"ya cubierto en {best} ({cov[best]:.0%})"
    if row["paths"] and cov["repo"] >= cov["brain"] and chars > 350:
        return "move", "repo", "detalle operativo: se lee al trabajar en el repo"
    if row["signals"]["procedimiento"] and chars > 600:
        return "move", "skill", "procedimiento reutilizable: pertenece a una skill"
    if row["signals"]["cliente"] and chars > 500:
        return "move", "brain", "conocimiento de cliente/negocio de largo plazo"
    if row["signals"]["fecha"]:
        return "move", "engram", "episódico con fecha: recall por búsqueda (Engram)"
    return "archive", "archive", "bajo valor always-on: archivo verbatim + recall por token"


def build(args) -> dict:
    store = M.resolve_store(args.home, args.profile)
    path = M.target_path(store, args.target)
    raw = M.load_text(path, 5_000_000)
    entries = M.parse_entries(raw)
    limits = M.read_limits(store["config"])

    corpus = M.build_corpus(M.default_corpus_globs(Path(args.brain)), max_bytes=args.corpus_max_bytes)
    entry_tokens = [M.distinctive_tokens(e) for e in entries]
    entry_words = [M.word_set(e) for e in entries]

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

    rows = []
    for idx, entry in enumerate(entries, 1):
        toks = entry_tokens[idx - 1]
        cov = {k: round(M.coverage(toks, corpus[k]["tokens"]), 3) for k in corpus}
        best_kind = max(cov, key=cov.get) if cov else "brain"
        paths = sorted(set(M.PATH_RE.findall(entry)))[:4]
        signals = {
            "fecha": bool(M.DATE_RE.search(entry)),
            "procedimiento": bool(M.PROC_RE.search(entry)),
            "invariante": bool(M.INVARIANT_RE.search(entry)),
            "cliente": any(h in entry.lower() for h in CLIENT_HINTS),
        }
        row = {
            "idx": idx, "chars": len(entry), "sha1": M.sha1(entry), "summary": M.summarize(entry),
            "tokens": len(toks), "coverage": cov, "best_corpus": best_kind, "paths": paths,
            "signals": signals, "duplicates": dup_of.get(idx, []),
            "score": value_score(len(entry), cov[best_kind] if cov else 0.0, signals),
            "proposed": {"action": "archive", "destination_kind": "archive", "reason": ""},
        }
        rows.append(row)

    # presupuesto de memoria always-on: se conserva lo de mayor valor hasta llenar el cupo
    budget = int(limits[args.target] * args.keep_budget)
    for row in rows:
        if row["duplicates"]:
            target = row["duplicates"][0]["other"]
            row["proposed"] = {"action": "merge", "destination_kind": "memory",
                               "reason": f"duplicado/supersedido de #{target}"}
    keep_rows = [r for r in rows if not r["duplicates"]]
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
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "host": "DEV", "profile": store["profile"], "target": args.target,
        "store_path": str(path), "config_path": str(store["config"]),
        "warnings": store["warnings"],
        "limits": limits,
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
    out += ["| # | chars | propuesta | destino | cobertura b/r/s/v | resumen |", "|---|---|---|---|---|---|"]
    for r in res["entries"]:
        c = r["coverage"]
        out.append(f"| {r['idx']} | {r['chars']} | {r['proposed']['action']} | {r['proposed']['destination_kind']} | "
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
                "action": r["proposed"]["action"] if r["proposed"]["action"] in ("keep", "archive") else "move",
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
    for w in res["warnings"]:
        print(f"AVISO      : {w}")
    print("\nentradas más pesadas:")
    for r in sorted(res["entries"], key=lambda x: -x["chars"])[: args.top]:
        print(f"  #{r['idx']:<3} {r['chars']:>6} chars  {r['proposed']['action']:<8} "
              f"{r['proposed']['destination_kind']:<8} {r['summary'][:70]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
