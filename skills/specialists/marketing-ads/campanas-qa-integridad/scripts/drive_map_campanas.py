#!/usr/bin/env python3
"""drive_map_campanas.py — levanta el mapa REAL (con IDs) de las carpetas de campana en
el Drive compartido, para no responder ubicaciones de memoria.

Correr con el python que trae google-api-python-client:
    /opt/data/.venv/bin/python scripts/drive_map_campanas.py
    /opt/data/.venv/bin/python scripts/drive_map_campanas.py --search "Marketing"

Read-only (files.list / files.get). Prueba credenciales en orden y usa la primera que
refresque; el token raiz /opt/data/google_token.json suele estar expirado.
"""
import argparse
import json
import os
import sys

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

CANDIDATES = [
    "/opt/data/secrets/neuralcrew-drive.json",
    "/opt/data/secrets/golden-drive.json",
    "/opt/data/secrets/lucky-drive.json",
    "/opt/data/secrets/jonathan-drive.json",
    "/opt/data/google_token.json",
]
FIELD = "files(id,name,mimeType,parents,driveId,modifiedTime,size)"


def load_service():
    for path in CANDIDATES:
        if not os.path.exists(path):
            continue
        try:
            d = json.load(open(path))
            sc = d.get("scopes") or d.get("scope") or ""
            if isinstance(sc, str):
                sc = sc.split()
            c = Credentials(
                token=d.get("token"), refresh_token=d.get("refresh_token"),
                client_id=d.get("client_id"), client_secret=d.get("client_secret"),
                token_uri=d.get("token_uri", "https://oauth2.googleapis.com/token"),
                scopes=sc or None,
            )
            c.refresh(Request())
            print("credencial OK:", os.path.basename(path))
            return build("drive", "v3", credentials=c)
        except Exception as exc:  # noqa: BLE001
            print("falla %s: %s: %s" % (os.path.basename(path), type(exc).__name__, str(exc)[:90]))
    sys.exit("sin credenciales Drive validas")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--search", nargs="*", default=["Marketing", "Reel", "Escena", "Guion", "Campa"],
                    help="patrones de nombre a buscar (carpetas)")
    ap.add_argument("--roots", nargs="*", default=[], help="IDs de carpeta para listar hijos")
    args = ap.parse_args()
    svc = load_service()

    about = svc.about().get(fields="user(emailAddress,displayName)").execute()
    print("cuenta:", about.get("user"))
    try:
        for drv in svc.drives().list(pageSize=20).execute().get("drives", []):
            print("drive compartido:", drv["name"], "|", drv["id"])
    except Exception as exc:  # noqa: BLE001
        print("drives().list:", str(exc)[:90])

    def ls(q, page=100):
        return svc.files().list(q=q, pageSize=page, fields=FIELD,
                                includeItemsFromAllDrives=True,
                                supportsAllDrives=True).execute().get("files", [])

    seen = set()
    for pat in args.search:
        for f in ls("mimeType='application/vnd.google-apps.folder' and name contains '%s' and trashed=false" % pat):
            if f["id"] in seen:
                continue
            seen.add(f["id"])
            print("[%s] %-50s %s" % (pat, f["name"][:50], f["id"]))

    def path(fid):
        parts, cur = [], fid
        for _ in range(12):
            if not cur:
                break
            m = svc.files().get(fileId=cur, fields="name,parents", supportsAllDrives=True).execute()
            parts.append(m["name"])
            cur = (m.get("parents") or [None])[0]
        return " / ".join(reversed(parts))

    for fid in args.roots:
        print("raiz:", path(fid))
        for k in ls("'%s' in parents and trashed=false" % fid):
            print("   %-46s %s %s" % (k["name"][:46], "DIR " if "folder" in k["mimeType"] else "file", k["id"]))


if __name__ == "__main__":
    main()
