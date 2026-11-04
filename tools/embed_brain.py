#!/usr/bin/env python3
"""embed_brain.py — capa de búsqueda semántica (embeddings) sobre el brain de Ragnar.

Complementa (no reemplaza) el grafo de graphify y la búsqueda literal de
memory_graph.py: indexa notas .md del brain + nodos del grafo con
qwen3-embedding vía nan.builders, con indexado incremental por sha1.

Uso:
  /usr/bin/python3 embed_brain.py index            # indexar (incremental)
  /usr/bin/python3 embed_brain.py search "query"   # búsqueda semántica top-k
  /usr/bin/python3 embed_brain.py search "query" -k 15 --json

Requiere: /usr/bin/python3 (numpy 2.x). Solo stdlib + numpy.
Corre con cron (hook en brain_graph_update_inner.sh) y manualmente.
"""
import argparse
import hashlib
import json
import math
import os
import sqlite3
import struct
import sys
import time
import urllib.request

ROOT = "/opt/hermes-agent-data/brain"
GRAPH = os.path.join(ROOT, "graphify-out-v2", "graph.json")
DB = os.path.join(ROOT, "graphify-out-v2", "embeddings.db")
BASE_URL = "https://api.nan.builders/v1"
MODEL = os.environ.get("EMBED_MODEL", "qwen3-embedding")
BATCH = 48
MAX_CHARS = 2400            # trunca notas largas (head+tail)
SKIP_DIRS = {"graphify-out", "graphify-out-v2", "archive", "raw"}


# ── API key (mismo método que brain_graph_update_inner.sh) ──────────────────
def load_key():
    import yaml  # noqa: F401 — valida que exista; /usr/bin/python3 lo trae
    with open("/opt/hermes-agent-data/config.yaml") as f:
        key = yaml.safe_load(f)["providers"]["NaN-Builders"]["api_key"]
    if key.startswith("${"):
        var = key[2:-1]
        sys.path.insert(0, "/opt/hermes-agent")
        from hermes_cli.env_loader import hydrate_profile_secret_sources
        key = hydrate_profile_secret_sources("/opt/hermes-agent-data").get(var, "")
    if not key:
        print("EXTRACT_ERROR: API key de NaN-Builders vacía/ilegible", file=sys.stderr)
        sys.exit(1)
    return key


KEY = None  # lazy


def embed(texts):
    """Devuelve lista de vectores (list[float]) para un batch de textos."""
    global KEY
    if KEY is None:
        KEY = load_key()
    req = urllib.request.Request(
        BASE_URL + "/embeddings",
        data=json.dumps({"model": MODEL, "input": texts}).encode(),
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
    )
    last = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                d = json.loads(r.read())
            return [e["embedding"] for e in d["data"]]
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"embeddings falló tras 3 intentos: {last}")


# ── Corpus ───────────────────────────────────────────────────────────────────
def note_text(path):
    raw = open(path, encoding="utf-8", errors="replace").read()
    if len(raw) > MAX_CHARS:  # head+tail: título + arranque + cierre
        raw = raw[: MAX_CHARS // 2] + "\n[…]\n" + raw[-MAX_CHARS // 4:]
    return raw


def collect():
    """[(key, kind, source, label, text)] — notas del brain + nodos del grafo."""
    items = []
    for dp, dn, fn in os.walk(ROOT):
        dn[:] = [d for d in dn if d not in SKIP_DIRS]
        for f in fn:
            if not f.endswith(".md"):
                continue
            p = os.path.join(dp, f)
            rel = os.path.relpath(p, ROOT)
            items.append(("note:" + rel, "note", rel, f, note_text(p)))
    try:
        g = json.load(open(GRAPH))
    except Exception:
        g = {"nodes": []}
    for n in g.get("nodes", []):
        label = n.get("label", "")
        summ = n.get("summary", "") or ""
        text = (label + "\n" + summ).strip()
        if text:
            items.append(("node:" + n.get("id", label), "node", "graph", label, text[:MAX_CHARS]))
    return items


# ── Index ────────────────────────────────────────────────────────────────────
def cmd_index():
    items = collect()
    con = sqlite3.connect(DB)
    con.execute("""CREATE TABLE IF NOT EXISTS vectors(
        key TEXT PRIMARY KEY, kind TEXT, source TEXT, label TEXT,
        sha1 TEXT, vec BLOB)""")
    known = {k for (k,) in con.execute("SELECT key FROM vectors")}
    hashes = {row[0]: row[1] for row in con.execute("SELECT key, sha1 FROM vectors")}

    todo = []
    for key, kind, source, label, text in items:
        h = hashlib.sha1(text.encode()).hexdigest()
        if key not in known or hashes.get(key) != h:
            todo.append((key, kind, source, label, text, h))

    # poda: filas cuyas fuentes ya no existen
    alive = {k for k, *_ in items}
    dead = known - alive
    if dead:
        con.executemany("DELETE FROM vectors WHERE key=?", [(k,) for k in dead])

    print(f"[embed-brain] corpus: {len(items)} · nuevos/cambiados: {len(todo)} · podados: {len(dead)}")
    t0 = time.time()
    done = 0
    for i in range(0, len(todo), BATCH):
        chunk = todo[i : i + BATCH]
        vecs = embed([c[4] for c in chunk])
        rows = [
            (c[0], c[1], c[2], c[3], c[5], struct.pack(f"<{len(v)}e", *v))
            for c, v in zip(chunk, vecs)
        ]
        con.executemany(
            "INSERT OR REPLACE INTO vectors VALUES (?,?,?,?,?,?)", rows)
        con.commit()
        done += len(chunk)
        print(f"[embed-brain] {done}/{len(todo)} ({time.time()-t0:.0f}s)")
    print(f"[embed-brain] OK — {done} vector(es) · {time.time()-t0:.0f}s · DB {os.path.getsize(DB)//1024} KB")


# ── Search ───────────────────────────────────────────────────────────────────
def cmd_search(query, k):
    import numpy as np
    con = sqlite3.connect(DB)
    try:
        rows = con.execute("SELECT key, kind, source, label, vec FROM vectors").fetchall()
    except sqlite3.OperationalError:
        print("Índice vacío — corre primero: embed_brain.py index")
        sys.exit(1)
    if not rows:
        print("Índice vacío — corre primero: embed_brain.py index")
        sys.exit(1)
    mat = np.frombuffer(b"".join(r[4] for r in rows), dtype="<f2").reshape(len(rows), -1).astype(np.float32)
    qv = np.array(embed([query])[0], dtype=np.float32)
    # similitud coseno
    mat_n = mat / (np.linalg.norm(mat, axis=1, keepdims=True) + 1e-9)
    qn = qv / (np.linalg.norm(qv) + 1e-9)
    sims = mat_n @ qn
    top = np.argsort(-sims)[:k]
    out = []
    for i in top:
        key, kind, source, label, _ = rows[int(i)]
        out.append({"score": round(float(sims[int(i)]), 4), "kind": kind,
                    "label": label, "source": source, "key": key})
    return out


def main():
    ap = argparse.ArgumentParser(description="Búsqueda semántica del brain (qwen3-embedding via nan)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("index")
    s = sub.add_parser("search")
    s.add_argument("query", nargs="+")
    s.add_argument("-k", type=int, default=8)
    s.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if a.cmd == "index":
        cmd_index()
    else:
        res = cmd_search(" ".join(a.query), a.k)
        if a.json:
            print(json.dumps(res, ensure_ascii=False, indent=1))
        else:
            print(f"=== búsqueda semántica: {' '.join(a.query)!r} · top {len(res)} ===")
            for r in res:
                print(f"  {r['score']:.4f} [{r['kind']}] {r['label']}  ({r['source']})")


if __name__ == "__main__":
    main()
