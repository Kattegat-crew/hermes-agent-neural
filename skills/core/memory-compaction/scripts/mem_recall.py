#!/usr/bin/env python3
"""Recall unificado: busca en todo lo que ya no vive en la memoria nativa.

Fuentes (en este orden): archivo verbatim de memoria nativa, brain curado,
memoria de repos (PROJECT_MEMORY/AGENTS/ARCHITECTURE/.agents/rules), skills,
vault y Engram (FTS de observaciones).

Uso:
  python3 mem_recall.py "clave del banco lucky"
  python3 mem_recall.py FZY552 --limit 5
  python3 mem_recall.py "gate de gasto" --no-engram --json
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import memlib as M  # noqa: E402

ARCHIVE_DIR = Path("/opt/data/brain/memoria-archivo")
BRAIN = Path("/opt/data/brain")
ENGRAM_DB = Path("/opt/data/home/.engram/engram.db")
MAX_FILE_BYTES = 1_500_000


def terms_of(query: str) -> list[str]:
    return [t for t in re.findall(r"[0-9a-zA-Záéíóúñü_@/.:#-]{2,}", query.lower()) if t not in M.STOPWORDS]


def score_text(text: str, terms: list[str], phrase: str) -> int:
    low = text.lower()
    score = sum(min(low.count(t), 3) for t in terms)
    if phrase and phrase in low:
        score += 5
    return score


def snippet(text: str, terms: list[str], width: int = 220) -> str:
    low = text.lower()
    pos = min((low.find(t) for t in terms if low.find(t) >= 0), default=-1)
    if pos < 0:
        return " ".join(text.split())[:width]
    start = max(0, pos - width // 3)
    out = " ".join(text[start:start + width].split())
    return ("..." if start else "") + out + "..."


def gather_docs(include_brain: bool = True, include_repos: bool = True,
                archive_dir: Path | None = None, include_skills: bool = True) -> list[dict]:
    docs: list[dict] = []
    archive_dir = archive_dir or ARCHIVE_DIR
    if archive_dir.is_dir():
        for f in sorted(archive_dir.glob("*.jsonl")):
            for line in f.read_text(encoding="utf-8", errors="ignore").splitlines():
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                docs.append({"kind": "archivo-memoria", "ref": f"{f.name}#{row.get('idx')}",
                             "title": row.get("summary", ""), "text": row.get("text", ""),
                             "destination": row.get("destination")})
    if include_brain:
        for sub in ("", "entities", "concepts", "ops", "analysis", "campaigns", "plans", "projects", "decisions"):
            d = BRAIN / sub if sub else BRAIN
            if not d.is_dir():
                continue
            for f in sorted(d.glob("*.md")):
                text = M.load_text(f, MAX_FILE_BYTES)
                if text:
                    docs.append({"kind": "brain", "ref": str(f), "title": f.stem, "text": text})
    globs = M.default_corpus_globs(BRAIN)
    if include_repos:
        for f in globs["repo"]:
            text = M.load_text(f, MAX_FILE_BYTES)
            if text:
                docs.append({"kind": "repo", "ref": str(f), "title": f.parent.name, "text": text})
    for f in globs["skill"] if include_skills else []:
        text = M.load_text(f, MAX_FILE_BYTES)
        if text:
            docs.append({"kind": "skill", "ref": str(f), "title": f.parent.name, "text": text})
    for f in globs["vault"] if include_skills else []:
        text = M.load_text(f, MAX_FILE_BYTES)
        if text:
            docs.append({"kind": "vault", "ref": str(f), "title": f.stem, "text": text})
    return docs


def search_engram(terms: list[str], limit: int) -> list[dict]:
    if not ENGRAM_DB.is_file():
        return []
    safe = [t for t in terms if re.fullmatch(r"[0-9a-záéíóúñü_]+", t)]
    if not safe:
        return []
    match = " OR ".join(f'"{t}"' for t in safe[:8])
    out: list[dict] = []
    try:
        con = sqlite3.connect(f"file:{ENGRAM_DB}?mode=ro", uri=True, timeout=5)
        con.row_factory = sqlite3.Row
        try:
            rows = con.execute(
                "SELECT o.id, o.project, o.type, o.title, substr(o.content,1,1200) AS body "
                "FROM observations_fts f JOIN observations o ON o.id = f.rowid "
                "WHERE observations_fts MATCH ? AND o.deleted_at IS NULL ORDER BY rank LIMIT ?",
                (match, limit)).fetchall()
        except sqlite3.Error:
            like = f"%{safe[0]}%"
            rows = con.execute(
                "SELECT id, project, type, title, substr(content,1,1200) AS body FROM observations "
                "WHERE deleted_at IS NULL AND (title LIKE ? OR content LIKE ?) ORDER BY id DESC LIMIT ?",
                (like, like, limit)).fetchall()
        for r in rows:
            out.append({"kind": "engram", "ref": f"engram#{r['id']}", "title": r["title"],
                        "text": r["body"] or "", "project": r["project"], "type": r["type"]})
        con.close()
    except sqlite3.Error:
        return []
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Recall unificado de memoria archivada y distribuida")
    ap.add_argument("query", nargs="+")
    ap.add_argument("--limit", type=int, default=8)
    ap.add_argument("--no-engram", action="store_true")
    ap.add_argument("--no-brain", action="store_true")
    ap.add_argument("--no-repos", action="store_true")
    ap.add_argument("--archive-dir", default=None, help="directorio del archivo verbatim (default /opt/data/brain/memoria-archivo)")
    ap.add_argument("--only-archive", action="store_true", help="buscar solo en el archivo verbatim de memoria nativa")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    query = " ".join(args.query)
    terms = terms_of(query)
    if not terms:
        print("consulta sin términos útiles", file=sys.stderr)
        return 2
    phrase = query.strip().lower()

    hits: list[dict] = []
    scanned = 0
    archive_dir = Path(args.archive_dir) if args.archive_dir else ARCHIVE_DIR
    for doc in gather_docs(include_brain=not (args.no_brain or args.only_archive),
                           include_repos=not (args.no_repos or args.only_archive),
                           archive_dir=archive_dir,
                           include_skills=not args.only_archive):
        scanned += 1
        score = score_text(doc["text"], terms, phrase)
        if score:
            hits.append({**doc, "score": score, "snippet": snippet(doc["text"], terms)})
    if not (args.no_engram or args.only_archive):
        for doc in search_engram(terms, args.limit * 2):
            scanned += 1
            score = score_text(doc["title"] + " " + doc["text"], terms, phrase) + 2
            hits.append({**doc, "score": score, "snippet": snippet(doc["text"], terms)})

    hits.sort(key=lambda h: (-h["score"], h["kind"]))
    hits = hits[: args.limit]

    if args.json:
        print(json.dumps({"query": query, "terms": terms, "scanned": scanned, "hits": hits},
                         ensure_ascii=False, indent=2))
        return 0
    if not hits:
        print(f"sin coincidencias para {terms} en {scanned} documentos "
              f"(archivo nativa, brain, repos, skills, vault{' , Engram' if not args.no_engram else ''}).")
        print("prueba con un token literal (ID, ruta, dominio, nombre propio) o revisa el plan de compactación.")
        return 1
    print(f"{len(hits)} coincidencias de {scanned} documentos para {terms}\n")
    for h in hits:
        extra = ""
        if h.get("destination"):
            extra = f" -> {h['destination']}"
        elif h.get("project"):
            extra = f" [{h.get('project')}/{h.get('type')}]"
        print(f"[{h['kind']}] {h['ref']}{extra}")
        print(f"  {h['title'][:110]}")
        print(f"  {h['snippet']}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
