#!/usr/bin/env python3
"""Aplica un plan de compactación a la memoria nativa con gate de cero pérdida.

Orden de operaciones (si algo falla, el store original NO se toca):
  1. validar plan contra el fichero vivo (idx + sha1 + cobertura de cada entrada)
  2. backup de MEMORY.md y USER.md (copia + sha256 + tar.gz)
  3. escribir archivo verbatim (JSONL + Markdown legible) de TODAS las entradas retiradas
  4. releer el archivo y comprobar byte a byte que cada entrada está completa
  5. componer el nuevo store (keep en orden original + entrada puntero de recuperación)
  6. comprobar el tope de chars y escribir de forma atómica
  7. emitir recibo JSON con hashes y rutas

Uso:
  python3 memory_apply.py --plan plan.json --check-only
  python3 memory_apply.py --plan plan.json
  python3 memory_apply.py --plan plan.json --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import memlib as M  # noqa: E402

VALID_ACTIONS = ("keep", "move", "merge", "archive", "discard")
ARCHIVE_DIR = Path("/opt/data/brain/memoria-archivo")
RECALL = "/opt/data/skills/core/memory-compaction/scripts/mem_recall.py"


class Blocked(Exception):
    pass


def load_plan(path: str) -> dict:
    try:
        plan = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise Blocked(f"plan ilegible: {exc}") from exc
    if plan.get("schema") != "memory-compaction/plan@1":
        raise Blocked("schema inválido: se espera 'memory-compaction/plan@1'")
    if not isinstance(plan.get("entries"), list) or not plan["entries"]:
        raise Blocked("el plan no trae entradas")
    return plan


def index_plan(plan: dict) -> dict[int, dict]:
    out: dict[int, dict] = {}
    for item in plan["entries"]:
        try:
            idx = int(item["idx"])
        except (KeyError, TypeError, ValueError) as exc:
            raise Blocked(f"entrada de plan sin idx válido: {item!r}") from exc
        if idx in out:
            raise Blocked(f"idx duplicado en el plan: {idx}")
        action = str(item.get("action", "")).strip()
        if action not in VALID_ACTIONS:
            raise Blocked(f"#{idx}: acción inválida '{action}' (usa {VALID_ACTIONS})")
        out[idx] = item
    return out


def _engram_text(observation_id: int) -> str:
    import sqlite3
    db = Path("/opt/data/home/.engram/engram.db")
    if not db.is_file():
        raise Blocked(f"Engram no disponible en {db}")
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=5)
        row = con.execute("SELECT title, content FROM observations WHERE id=? AND deleted_at IS NULL",
                          (observation_id,)).fetchone()
        con.close()
    except sqlite3.Error as exc:
        raise Blocked(f"Engram inaccesible: {exc}") from exc
    if not row:
        raise Blocked(f"observación Engram #{observation_id} no existe")
    return f"{row[0]}\n{row[1]}"


def read_destination(dest: dict) -> tuple[str, str]:
    if not isinstance(dest, dict):
        raise Blocked("destino sin formato")
    kind = str(dest.get("kind") or "file")
    if kind == "engram" or dest.get("observation_id"):
        try:
            obs = int(dest.get("observation_id"))
        except (TypeError, ValueError) as exc:
            raise Blocked("destino engram sin 'observation_id' numérico") from exc
        return f"engram#{obs}", _engram_text(obs)
    if not dest.get("path"):
        raise Blocked("destino sin 'path'")
    path = Path(str(dest["path"])).expanduser()
    if not path.is_file():
        raise Blocked(f"destino inexistente: {path}")
    text = M.load_text(path, 4_000_000)
    if not text.strip():
        raise Blocked(f"destino vacío: {path}")
    anchor = str(dest.get("anchor") or "").strip()
    if anchor and anchor not in text:
        raise Blocked(f"ancla no encontrada en {path}: {anchor!r}")
    return str(path), text


def validate(entries: list[str], plan_by_idx: dict[int, dict], *, coverage_threshold: float,
             allow_discard: bool) -> tuple[list[dict], list[str]]:
    problems: list[str] = []
    kept: list[dict] = []
    if set(plan_by_idx) != set(range(1, len(entries) + 1)):
        missing = sorted(set(range(1, len(entries) + 1)) - set(plan_by_idx))
        extra = sorted(set(plan_by_idx) - set(range(1, len(entries) + 1)))
        if missing:
            problems.append(f"{len(missing)} entradas sin decisión en el plan (idx {missing[:12]})")
        if extra:
            problems.append(f"{len(extra)} idx del plan no existen en el fichero ({extra[:12]})")

    for idx, entry in enumerate(entries, 1):
        item = plan_by_idx.get(idx)
        if not item:
            continue
        if str(item.get("sha1", "")) != M.sha1(entry):
            problems.append(f"#{idx}: sha1 no coincide — el plan está desactualizado, re-ejecuta el inventario")
            continue
        action = item["action"]
        row = {"idx": idx, "sha1": M.sha1(entry), "chars": len(entry), "action": action,
               "reason": str(item.get("reason", ""))[:200], "destination": None, "merge_into": None,
               "coverage": None}
        if action == "keep":
            kept.append(row)
            continue
        toks = M.distinctive_tokens(entry)
        if action == "move":
            try:
                dest_label, dest_text = read_destination(item.get("destination"))
            except Blocked as exc:
                problems.append(f"#{idx}: {exc}")
                continue
            cov = M.coverage(toks, M.word_set(dest_text) | M.distinctive_tokens(dest_text))
            row["coverage"] = round(cov, 3)
            row["destination"] = dest_label
            if cov < coverage_threshold:
                problems.append(
                    f"#{idx}: el destino {dest_label} solo cubre {cov:.0%} de los tokens "
                    f"(mínimo {coverage_threshold:.0%}); pega la entrada verbatim, resume con sus datos clave, "
                    f"o marca action=archive si no merece nota")
        elif action == "merge":
            try:
                target = int(item.get("merge_into"))
            except (TypeError, ValueError):
                problems.append(f"#{idx}: merge sin 'merge_into' válido")
                continue
            if not (1 <= target <= len(entries)) or target == idx:
                problems.append(f"#{idx}: merge_into fuera de rango ({target})")
                continue
            target_entry = entries[target - 1]
            if plan_by_idx.get(target, {}).get("action") != "keep":
                problems.append(f"#{idx}: merge_into #{target} no está marcado keep (se perdería el contenido)")
                continue
            cov = M.coverage(toks, M.word_set(target_entry) | M.distinctive_tokens(target_entry))
            row["coverage"] = round(cov, 3)
            row["merge_into"] = target
            if cov < 0.5:
                problems.append(f"#{idx}: el destino de merge #{target} solo cubre {cov:.0%}; "
                                f"funde el contenido antes de retirar la entrada")
        elif action == "discard" and not allow_discard:
            problems.append(f"#{idx}: action=discard exige --allow-discard (y aun así queda en el archivo)")
        kept.append(row) if action == "keep" else None
    return kept, problems


def pointer_entry(counts: dict, total: int, archive_jsonl: Path, kept_n: int, target: str) -> str:
    store_name = "MEMORY.md" if target == "memory" else "USER.md"
    retiradas = total - kept_n
    kinds = ", ".join(f"{k}={v}" for k, v in sorted(counts.items()) if k != "keep" and v)
    return (
        f"Memoria nativa compactada {datetime.now(timezone.utc).strftime('%Y-%m-%d')}: "
        f"{store_name} pasó de {total} a {kept_n} entradas ({retiradas} retiradas: {kinds}); "
        f"todas están verbatim con su destino en {archive_jsonl} . "
        f"Antes de responder 'no sé' o de reconstruir algo, buscar ahí: "
        f"`python3 {RECALL} \"<tema o token>\"` (recorre archivo nativa + brain + PROJECT_MEMORY/AGENTS de repos + "
        f"skills + vault + Engram). Si un dato reaparece y cambia comportamiento en cada sesión, vuelve a MEMORY.md."
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Aplica un plan de compactación con gate de cero pérdida")
    ap.add_argument("--plan", required=True)
    ap.add_argument("--home", default=None)
    ap.add_argument("--profile", default=None)
    ap.add_argument("--target", default=None, choices=("memory", "user"))
    ap.add_argument("--archive-dir", default=str(ARCHIVE_DIR))
    ap.add_argument("--coverage-threshold", type=float, default=0.35)
    ap.add_argument("--max-fill", type=float, default=0.70, help="tope de ocupación tras compactar (0-1)")
    ap.add_argument("--allow-discard", action="store_true")
    ap.add_argument("--check-only", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--pointer-text", default=None)
    args = ap.parse_args()

    try:
        plan = load_plan(args.plan)
        profile = args.profile or plan.get("profile") or "default"
        target = args.target or plan.get("target") or "memory"
        store = M.resolve_store(args.home, profile)
        path = M.target_path(store, target)
        raw = M.load_text(path, 5_000_000)
        if not raw.strip():
            raise Blocked(f"store vacío o inexistente: {path}")
        entries = M.parse_entries(raw)
        plan_by_idx = index_plan(plan)
        kept, problems = validate(entries, plan_by_idx, coverage_threshold=args.coverage_threshold,
                                  allow_discard=args.allow_discard)
        if problems:
            raise Blocked("el plan NO cumple el gate de cero pérdida:\n  - " + "\n  - ".join(problems))

        counts: dict[str, int] = {}
        for item in plan_by_idx.values():
            counts[item["action"]] = counts.get(item["action"], 0) + 1
        kept_entries = [entries[i - 1] for i in sorted(item["idx"] for item in kept)]
        limits = M.read_limits(store["config"])
        limit = limits[target]

        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        archive_dir = Path(args.archive_dir)
        jsonl_path = archive_dir / f"nativa-{profile}-{target}-{ts}.jsonl"
        md_path = archive_dir / f"nativa-{profile}-{target}-{ts}.md"
        backup_dir = archive_dir / "backups" / f"{ts}-{profile}-{target}"

        pointer = args.pointer_text or pointer_entry(counts, len(entries), jsonl_path, len(kept_entries), target)
        new_entries = kept_entries + [pointer]
        new_text = M.join_entries(new_entries)
        projected = len(new_text)
        cap = int(limit * args.max_fill)

        print(f"store       : {path}")
        print(f"entradas    : {len(entries)} -> {len(new_entries)} (keep={len(kept_entries)}) · {counts}")
        print(f"chars       : {len(raw):,} -> {projected:,} (tope operativo {cap:,} = {args.max_fill:.0%} de {limit:,})")
        print(f"archivo     : {jsonl_path}")
        if projected > cap:
            raise Blocked(f"el resultado quedaría en {projected:,} chars, por encima del tope {cap:,}; "
                          f"retira más entradas o sube --max-fill con criterio")
        if args.check_only or args.dry_run:
            print("\nOK: el plan pasa el gate de cero pérdida (no se escribió nada).")
            return 0

        # 2. backup
        backup_dir.mkdir(parents=True, exist_ok=True)
        manifest = {"created_at": ts, "profile": profile, "target": target, "store_path": str(path), "files": {}}
        for src in (Path(store["memory"]), Path(store["user"])):
            if src.is_file():
                dst = backup_dir / src.name
                shutil.copy2(src, dst)
                manifest["files"][src.name] = {"backup": str(dst), "sha256": M.sha1(dst.read_text(encoding="utf-8", errors="ignore")),
                                               "bytes": dst.stat().st_size}
        tar_path = backup_dir / "store.tar.gz"
        with tarfile.open(tar_path, "w:gz") as tar:
            for src in (Path(store["memory"]), Path(store["user"])):
                if src.is_file():
                    tar.add(src, arcname=src.name)
        manifest["tarball"] = str(tar_path)
        (backup_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

        # 3. archivo verbatim
        archive_dir.mkdir(parents=True, exist_ok=True)
        retired = []
        for idx in range(1, len(entries) + 1):
            item = plan_by_idx[idx]
            if item["action"] == "keep":
                continue
            retired.append({
                "idx": idx, "sha1": M.sha1(entries[idx - 1]), "chars": len(entries[idx - 1]),
                "action": item["action"], "reason": item.get("reason", ""),
                "destination": (str((item.get("destination") or {}).get("path"))
                                if (item.get("destination") or {}).get("path")
                                else (f"engram#{(item.get('destination') or {}).get('observation_id')}"
                                      if (item.get("destination") or {}).get("observation_id") else None)),
                "merge_into": item.get("merge_into"), "summary": M.summarize(entries[idx - 1], 120),
                "text": entries[idx - 1],
            })
        with jsonl_path.open("w", encoding="utf-8") as fh:
            for row in retired:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        md_lines = [f"# Memoria nativa — archivo verbatim ({profile}/{target})", "",
                    f"Retiradas: {len(retired)} · origen `{path}` · {ts}", ""]
        for row in retired:
            md_lines += [f"## [#{row['idx']}] {row['summary']}", "",
                         f"- acción: `{row['action']}` · destino: `{row['destination'] or 'archivo (recall)'}` "
                         f"· sha1: `{row['sha1']}` · {row['chars']} chars",
                         f"- motivo: {row['reason']}", "", row["text"], ""]
        md_path.write_text("\n".join(md_lines), encoding="utf-8")

        # 4. verificación byte a byte del archivo
        back = {json.loads(line)["idx"]: json.loads(line) for line in jsonl_path.read_text(encoding="utf-8").splitlines() if line.strip()}
        for row in retired:
            got = back.get(row["idx"])
            if not got or got["text"] != entries[row["idx"] - 1] or got["sha1"] != row["sha1"]:
                raise Blocked(f"archivo verbatim corrupto en #{row['idx']}; el store NO se ha modificado")
        if len(back) != len(retired):
            raise Blocked("el archivo verbatim no contiene todas las entradas retiradas; abortado")

        # 5-6. escritura atómica
        tmp_fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".MEMORY.compact-")
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as fh:
                fh.write(new_text)
            os.chmod(tmp_name, path.stat().st_mode & 0o777)
            os.replace(tmp_name, path)
        except BaseException:
            with __import__("contextlib").suppress(OSError):
                os.unlink(tmp_name)
            raise

        # 7. recibo
        receipt = {
            "applied_at": ts, "profile": profile, "target": target, "store_path": str(path),
            "entries_before": len(entries), "entries_after": len(new_entries), "chars_before": len(raw),
            "chars_after": len(new_text), "limit": limit, "counts": counts,
            "archive_jsonl": str(jsonl_path), "archive_md": str(md_path), "backup_dir": str(backup_dir),
            "retired": [{k: r[k] for k in ("idx", "sha1", "action", "destination", "merge_into")} for r in retired],
            "rollback": f"cp {backup_dir}/{path.name} {path}",
        }
        receipt_path = archive_dir / f"recibo-{profile}-{target}-{ts}.json"
        receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nAPLICADO. {len(entries)} -> {len(new_entries)} entradas · {len(raw):,} -> {len(new_text):,} chars")
        print(f"archivo   : {jsonl_path} ({len(retired)} entradas verbatim)")
        print(f"backup    : {backup_dir}")
        print(f"recibo    : {receipt_path}")
        print(f"rollback  : {receipt['rollback']}")
        return 0
    except Blocked as exc:
        print(f"BLOQUEADO: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
