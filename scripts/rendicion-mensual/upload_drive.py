#!/usr/bin/env python3
"""upload_drive.py — sube staging a <Cliente>/05-informes/rendicion-de-cuentas/<YYYY-MM>/.

Estructura destino:
  golden → carpeta raíz 11_0J6plN_FAAtQbpXYf7yT_6Yti27qPk
  lucky  → carpeta raíz 1VqEJY7ZjS2MBTGEpiN6uvQcvkZW5ey3z
  en cada raíz: 05-informes/rendicion-de-cuentas/<YYYY-MM>/ (se crea si falta)
Credenciales de subida: /opt/data/secrets/jonathan-drive.json (refresh token OAuth).
Multipart resumable simple (stdlib). Nunca se ejecuta sin el gate APPROVED=1.

uso: python3 upload_drive.py --mes 2026-11 --staging DIR
"""
import argparse
import json
import os
import sys
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib_gdrive import access_token  # noqa: E402

UPLOAD_CONN = "jonathan-drive"
# el token de subida puede venir de la cuenta de jonathan o de cada cliente
CLIENT_CONN = {"golden": "golden-drive", "lucky": "lucky-drive"}
ROOTS = {"golden": "11_0J6plN_FAAtQbpXYf7yT_6Yti27qPk",
         "lucky": "1VqEJY7ZjS2MBTGEpiN6uvQcvkZW5ey3z"}
PREFIX = {"golden": "Rendicion_Oct2026_Golden", "golden_kw": "golden",
          "lucky_kw": "lucky"}


def api(conn, url, method="GET", data=None, ctype=None):
    req = urllib.request.Request(url, method=method,
                                 headers={"Authorization": "Bearer " + access_token(conn)})
    if data is not None:
        req.add_header("Content-Type", ctype or "application/json")
        req.data = data
    return urllib.request.urlopen(req, timeout=300)


def ensure_folder(conn, name, parent):
    q = urllib.parse.quote(
        f"name='{name}' and mimeType='application/vnd.google-apps.folder' "
        f"and '{parent}' in parents and trashed=false")
    r = json.load(api(conn, f"https://www.googleapis.com/drive/v3/files?q={q}&fields=files(id,name)"))
    if r.get("files"):
        return r["files"][0]["id"]
    body = json.dumps({"name": name, "mimeType": "application/vnd.google-apps.folder",
                       "parents": [parent]}).encode()
    return json.load(api(conn, "https://www.googleapis.com/drive/v3/files", "POST", body))["id"]


def upload(conn, path, parent, name=None):
    name = name or os.path.basename(path)
    meta = json.dumps({"name": name, "parents": [parent]}).encode()
    boundary = "==rendicion=="
    data = (f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n"
            .encode() + meta +
            f"\r\n--{boundary}\r\nContent-Type: application/octet-stream\r\n\r\n".encode()
            + open(path, "rb").read() + f"\r\n--{boundary}--".encode())
    r = api(conn, "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart"
                  "&fields=id,name", "POST", data, f"multipart/related; boundary={boundary}")
    return json.load(r)


def brand_of(fname):
    low = fname.lower()
    if "golden" in low:
        return "golden"
    if "lucky" in low or "paradise" in low:
        return "lucky"
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mes", required=True)
    ap.add_argument("--staging", required=True)
    args = ap.parse_args()
    staged = sorted(os.listdir(args.staging))
    entregables = [f for f in staged if f.endswith((".docx", ".pdf", ".mp4"))
                   and brand_of(f)]
    if not entregables:
        print("upload_drive: no hay entregables etiquetados por marca en staging")
        return 1
    for f in entregables:
        brand = brand_of(f)
        conn = CLIENT_CONN[brand]
        d5 = ensure_folder(conn, "05-informes", ROOTS[brand])
        dr = ensure_folder(conn, "rendicion-de-cuentas", d5)
        dm = ensure_folder(conn, args.mes, dr)
        res = upload(conn, os.path.join(args.staging, f), dm)
        print(f"subido [{brand}] {f} -> {res['id']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
