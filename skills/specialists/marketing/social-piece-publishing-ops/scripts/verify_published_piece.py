#!/usr/bin/env python3
"""verify_published_piece.py — read-back por API de lo que REALMENTE quedó publicado.

Por qué existe: el JSONL, el XLSX y el stdout del publisher registran lo que el script CREYÓ
hacer. Este probe lee el objeto desde la API real (IG stories / IG media / FB page posts) y
resuelve el pitfall de `composio execute`: la respuesta puede venir inline o guardada en
`outputFilePath` (`storedInFile: true`) — parsear solo el JSON inline devuelve 0 filas y parece
que nada se publicó (falso negativo verificado 12-sep-2026).

Uso:
  python3 verify_published_piece.py --brand golden --kind stories
  python3 verify_published_piece.py --brand golden --kind media --limit 6
  python3 verify_published_piece.py --brand golden --kind fb-posts --limit 6
  python3 verify_published_piece.py --brand lucky  --kind stories
  python3 verify_published_piece.py --brand golden --kind stories --json

Los IDs numéricos y los alias de cuenta se leen del `publish.py` del repo de campañas cuando está
accesible (cero estado obsoleto); si no, se usan los defaults de abajo.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

COMPOSIO_PATH = "/opt/data/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
COMPOSIO_HOME = os.environ.get("COMPOSIO_HOME", "/opt/data/home")

# Defaults (campaña bingo-sep2026). Se sobrescriben con lo que diga publish.py si existe.
ACCOUNTS = {
    "golden": {
        "ig_account": "instagram_demal-molala",
        "ig_user_id": "40006158832316994",
        "fb_account": "facebook_uncite-skyish",
        "fb_page_id": "820898971112738",
    },
    "lucky": {
        "ig_account": "instagram_scot-linked",
        "ig_user_id": "27571270162548342",
        "fb_account": "facebook_uncite-skyish",
        "fb_page_id": "765896786617957",
    },
}

REPO_CANDIDATES = (
    "/host/root/marketing-campaign-generator",
    "/root/marketing-campaign-generator",
    "/opt/data/repos/marketing-campaign-generator",
)


def _find_publish_py() -> Path | None:
    for cand in REPO_CANDIDATES:
        root = Path(cand)
        if not root.is_dir():
            continue
        for p in root.glob("planning/*/publish.py"):
            return p
    return None


def _parse_dict(src: str, name: str) -> dict[str, str]:
    m = re.search(name + r"\s*=\s*\{([^}]*)\}", src)
    if not m:
        return {}
    return {k.strip().strip("'\""): v.strip().strip("'\"")
            for k, v in re.findall(r"['\"]([^'\"]+)['\"]\s*:\s*['\"]([^'\"]+)['\"]", m.group(1))}


def accounts(from_repo: bool = True) -> dict:
    acc = json.loads(json.dumps(ACCOUNTS))
    if not from_repo:
        return acc
    pub = _find_publish_py()
    if not pub:
        return acc
    try:
        src = pub.read_text(encoding="utf-8")
    except OSError:
        return acc
    ig, fb = _parse_dict(src, "IG_USER"), _parse_dict(src, "FB_PAGE")
    ig_acct = _parse_dict(src, "IG_ACCOUNT") or _parse_dict(src, "ACCT_IG")
    for brand, ids in acc.items():
        if ig.get(brand):
            ids["ig_user_id"] = ig[brand]
        if fb.get(brand):
            ids["fb_page_id"] = fb[brand]
        if ig_acct.get(brand):
            ids["ig_account"] = ig_acct[brand]
    return acc


def _rows(payload: dict) -> list:
    d = payload.get("data") if isinstance(payload, dict) else None
    if isinstance(d, dict):
        d = d.get("data")
    return d if isinstance(d, list) else []


def cap(tool: str, data: dict, account: str, timeout: int = 180) -> tuple[list, dict]:
    """Ejecuta un tool de Composio y devuelve (filas, meta).

    Maneja los DOS formatos de respuesta: payload inline o guardado en outputFilePath.
    """
    env = {"PATH": COMPOSIO_PATH, "HOME": COMPOSIO_HOME}
    r = subprocess.run(["composio", "execute", tool, "-d", json.dumps(data), "--account", account],
                       capture_output=True, text=True, env=env, timeout=timeout)
    raw = (r.stdout or "") + (r.stderr or "")
    i = raw.find("{")
    meta = json.loads(raw[i:]) if i >= 0 else {"raw": raw[:400]}
    fp = meta.get("outputFilePath")
    if fp:
        for cand in (fp, "/host" + fp):
            p = Path(cand)
            if p.exists():
                try:
                    return _rows(json.loads(p.read_text(encoding="utf-8"))), meta
                except (OSError, json.JSONDecodeError):
                    pass
    return _rows(meta), meta


def ig_stories(brand: str, ids: dict) -> list:
    rows, meta = cap("INSTAGRAM_GET_IG_USER_STORIES", {}, ids["ig_account"])
    if not meta.get("successful"):
        print(f"[!] stories {brand}: {meta.get('error')}", file=sys.stderr)
    return rows


def ig_media(brand: str, ids: dict, limit: int) -> list:
    rows, meta = cap("INSTAGRAM_GET_IG_USER_MEDIA",
                     {"ig_user_id": ids["ig_user_id"], "limit": limit}, ids["ig_account"])
    if not meta.get("successful"):
        print(f"[!] media {brand}: {meta.get('error')}", file=sys.stderr)
    return rows


def fb_posts(brand: str, ids: dict, limit: int) -> list:
    rows, meta = cap("FACEBOOK_GET_PAGE_POSTS",
                     {"page_id": ids["fb_page_id"], "limit": limit}, ids["fb_account"])
    if not meta.get("successful"):
        print(f"[!] fb posts {brand}: {meta.get('error')}", file=sys.stderr)
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--brand", required=True, choices=sorted(ACCOUNTS))
    ap.add_argument("--kind", required=True, choices=("stories", "media", "fb-posts", "all"))
    ap.add_argument("--limit", type=int, default=6)
    ap.add_argument("--json", action="store_true", help="salida cruda (para encadenar en código)")
    args = ap.parse_args()

    ids = accounts()[args.brand]
    kinds = ("stories", "media", "fb-posts") if args.kind == "all" else (args.kind,)
    out: dict[str, list] = {}
    for kind in kinds:
        if kind == "stories":
            rows = ig_stories(args.brand, ids)
        elif kind == "media":
            rows = ig_media(args.brand, ids, args.limit)
        else:
            rows = fb_posts(args.brand, ids, args.limit)
        out[kind] = rows

    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return 0

    for kind, rows in out.items():
        print(f"\n=== {args.brand} · {kind} · {len(rows)} ===")
        for r in rows:
            if kind == "fb-posts":
                copy = (r.get("story") or r.get("message") or "").replace("\n", " ")[:60]
                print(f"  {r.get('id')} | {r.get('created_time')} | {copy} | {r.get('permalink_url')}")
            else:
                print(f"  {r.get('id')} | {r.get('media_type')} | {r.get('timestamp')} | {r.get('permalink')}")
    print("\nRecordatorio: un post borrado NO aparece en estas listas; la ausencia es la prueba. "
          "La URL pública de IG devuelve 200 exista o no el post.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
