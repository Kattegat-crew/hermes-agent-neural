#!/usr/bin/env python3
"""drive_map.py — mapa de carpetas de Google Drive por ID de carpeta raíz.

Uso:
  python3 drive_map.py --folder FOLDER_ID              # árbol de carpetas
  python3 drive_map.py --folder FOLDER_ID --files      # + archivos por carpeta
  python3 drive_map.py --folder FOLDER_ID --depth 2    # profundidad máxima de carpetas
  python3 drive_map.py --folder FOLDER_ID --max 300    # límite de nodos (protección API)
  python3 drive_map.py --folder FOLDER_ID --token /ruta/google_token.json

Requiere google-api-python-client + google-auth (oauth2client NO). El token
se refresca automáticamente. Token por defecto: /opt/data/google_token.json.
"""
import argparse
import json
import os
import sys


def build_service(token_path):
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    with open(token_path) as f:
        token = json.load(f)
    creds = Credentials(
        token=token["token"],
        refresh_token=token.get("refresh_token"),
        token_uri=token.get("token_uri"),
        client_id=token.get("client_id"),
        client_secret=token.get("client_secret"),
        scopes=token.get("scopes"),
    )
    return build("drive", "v3", credentials=creds)


def list_children(svc, folder_id, page_size=200):
    """Devuelve (folders, files) del padre con paginación completa."""
    folders, files = [], []
    q = f"'{folder_id}' in parents and trashed=false"
    page_token = None
    while True:
        res = svc.files().list(
            q=q, pageSize=page_size, pageToken=page_token,
            fields="nextPageToken,files(id,name,mimeType)",
        ).execute()
        for it in res.get("files", []):
            if it["mimeType"] == "application/vnd.google-apps.folder":
                folders.append(it)
            else:
                files.append(it)
        page_token = res.get("nextPageToken")
        if not page_token:
            break
    return folders, files


def walk(svc, folder_id, depth, max_depth, max_nodes, stats):
    """Recursión acotada por profundidad y por nodos totales."""
    folders, files = list_children(svc, folder_id)
    node = {"name": None, "id": folder_id, "folders": [], "files": files}
    for fo in sorted(folders, key=lambda x: x["name"].lower()):
        stats["count"] += 1
        child = {"name": fo["name"], "id": fo["id"], "folders": [], "files": []}
        if stats["count"] < max_nodes and (max_depth is None or depth < max_depth):
            child = walk(svc, fo["id"], depth + 1, max_depth, max_nodes, stats)
            child["name"], child["id"] = fo["name"], fo["id"]
        node["folders"].append(child)
    return node


def render(node, depth, with_files):
    """Árbol en texto. node: {name, id, folders, files}."""
    lines = []
    for f in node["folders"]:
        pad = "  " * depth
        lines.append(f"{pad}📁 {f['name']}")
        if f["folders"] or (with_files and f["files"]):
            lines.extend(render(f, depth + 1, with_files))
        if with_files:
            for fl in f["files"]:
                lines.append(f"{'  ' * (depth + 1)}📄 {fl['name']}")
    return lines


def main():
    ap = argparse.ArgumentParser(description="Mapa de carpetas de Google Drive")
    ap.add_argument("--folder", required=True, help="ID de carpeta raíz de Drive")
    ap.add_argument("--token", default=os.environ.get("DRIVE_TOKEN", "/opt/data/google_token.json"))
    ap.add_argument("--files", action="store_true", help="Incluir archivos por carpeta")
    ap.add_argument("--depth", type=int, default=3, help="Profundidad máxima de carpetas (default 3)")
    ap.add_argument("--max", type=int, default=2000, help="Límite de nodos API (default 2000)")
    args = ap.parse_args()

    if not os.path.exists(args.token):
        sys.exit(f"ERROR: no existe token: {args.token}")

    try:
        svc = build_service(args.token)
        stats = {"count": 0}
        tree = walk(svc, args.folder, 0, args.depth, args.max, stats)

        print(f"# Mapa de Drive — raíz {args.folder} (id)\n")
        lines = render(tree, 0, args.files)
        print("\n".join(lines) if lines else "(carpeta vacía)")
        count = sum(1 for _ in _iter_folders(tree))
        print(f"\n{count} carpetas recorridas — registra el mapa en /opt/data/brain/folder-maps/")
    except ModuleNotFoundError as e:
        sys.exit(f"FALTA DEPENDENCIA: {e}. Instala: pip install google-api-python-client google-auth")


def _iter_folders(node):
    for f in node["folders"]:
        yield f
        yield from _iter_folders(f)


if __name__ == "__main__":
    main()