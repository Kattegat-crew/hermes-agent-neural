#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Búsqueda y descarga parametrizable en Google Drive.
Uso: python3 drive_search_download.py --term "golden" [--out /opt/data/drive_cliente] [--download]
Requiere: /opt/data/google_token.json con scopes drive/drive.readonly.
Dependencias: google-auth, google-api-python-client (disponibles en el entorno).
"""
import argparse, json, io, os, sys

def get_service():
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    token = json.load(open("/opt/data/google_token.json"))
    creds = Credentials(
        token=token["token"], refresh_token=token["refresh_token"],
        token_uri=token["token_uri"], client_id=token["client_id"],
        client_secret=token["client_secret"], scopes=token["scopes"],
    )
    return build("drive", "v3", credentials=creds)

def search(svc, q, label, page_size=50):
    print(f"\n=== {label} ===")
    try:
        res = svc.files().list(q=q, pageSize=page_size,
            fields="files(id,name,mimeType,parents,size,modifiedTime)").execute()
        files = res.get("files", [])
        if not files:
            print("(sin resultados)")
        for f in files:
            print(f"- {f['name']} | {f['mimeType']} | {f.get('size','?')}B | {f.get('modifiedTime','')} | id={f['id']}")
        return files
    except Exception as e:
        print("ERROR:", e)
        return []

def download(svc, fid, dest):
    from googleapiclient.http import MediaIoBaseDownload
    req = svc.files().get_media(fileId=fid)
    buf = io.BytesIO()
    dl = MediaIoBaseDownload(buf, req, chunksize=1024 * 1024)
    done = False
    while not done:
        _, done = dl.next_chunk()
    with open(dest, "wb") as f:
        f.write(buf.getvalue())
    print(f"[OK] {os.path.basename(dest)} ({os.path.getsize(dest)}B)")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--term", required=True, help="Término de búsqueda (marca/cliente)")
    ap.add_argument("--out", default="/opt/data/drive_cliente")
    ap.add_argument("--download", action="store_true", help="Descargar los archivos binarios hallados")
    ap.add_argument("--max", type=int, default=40, help="Máx. archivos a descargar")
    args = ap.parse_args()

    svc = get_service()
    term = args.term
    found = []
    found += search(svc, f"name contains '{term}' or name contains '{term.title()}'", "Por nombre")
    found += search(svc, f"fullText contains '{term.title()}'", "Por contenido (docs/sheets indexados)")

    # Dedupe por nombre (Drive suele tener copias en varias carpetas)
    seen = set()
    unique = []
    for f in found:
        if f["name"] not in seen:
            seen.add(f["name"])
            unique.append(f)

    if args.download:
        os.makedirs(args.out, exist_ok=True)
        n = 0
        for f in unique:
            if f["mimeType"].startswith("application/vnd.google-apps"):
                print(f"[SKIP nativo] {f['name']} (usar export o fullText)")
                continue
            if n >= args.max:
                break
            ext = {"pdf": ".pdf", "vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
                   "vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
                   "markdown": ".md", "plain": ".txt"}.get(f["mimeType"].split(".")[-1], "")
            dest = os.path.join(args.out, f["name"].replace("/", "_") + ext)
            if os.path.exists(dest):
                print(f"[SKIP] ya existe {f['name']}")
                continue
            try:
                download(svc, f["id"], dest)
                n += 1
            except Exception as e:
                print(f"[ERR] {f['name']}: {e}")

    print(f"\nTotal únicos: {len(unique)}")

if __name__ == "__main__":
    main()
