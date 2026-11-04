#!/usr/bin/env python3
"""Estado real de las piezas del calendario: JSONL local + AMBAS copias XLSX de Drive.

Uso (con el python del HOST, que tiene google-api-python-client + openpyxl):
    ssh dev 'python3 /tmp/check_calendar_rows.py sep12'
    python3 check_calendar_rows.py 2026-09-12 --repo /root/marketing-campaign-generator

Sin --repo resuelve la ruta del repo entre los candidatos vivos (nunca hardcodear una sola).
Imprime, por fuente, id / brand / type / slot / estado / nº de slides (y sus nombres si es carrusel).
"""
import argparse
import io
import json
import os
import sys
from pathlib import Path

DRIVE_XLSX = {
    "golden": "1K1EFCAQiR8Z-hch_0Hr1IY4Y9Fjd8n6e",
    "lucky": "1O1KX15rSq4CY3xuPlox5y2FosfTRC_Gn",
}
REPO_CANDIDATES = [
    "/root/marketing-campaign-generator",
    "/host/root/marketing-campaign-generator",
    "/opt/data/repos/marketing-campaign-generator",
    "/root/hermes-agent-legacy-docker/data/repos/marketing-campaign-generator",
]
CRED_CANDIDATES = [
    os.environ.get("GOOGLE_DRIVE_CREDENTIALS_PATH", ""),
    "/root/hermes-agent-legacy-docker/data/secrets/jonathan-drive.json",
    "/opt/data/secrets/jonathan-drive.json",
]


def first_existing(paths):
    for p in paths:
        if not p:
            continue
        try:
            if Path(p).exists():
                return Path(p)
        except OSError:  # Path.exists() puede LANZAR PermissionError entre namespaces
            pass
    return None


def local_rows(cal, needle):
    out = []
    for line in cal.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if needle in json.dumps(r, ensure_ascii=False):
            out.append(r)
    return out


def describe(r, source):
    slides = r.get("slides") or []
    names = "; ".join(s.get("name", "?").split("/")[-1] for s in slides) or "-"
    print(f"  [{source}] {r.get('id')} | {r.get('brand')} | {r.get('type')} | {r.get('slot')} "
          f"| estado={r.get('estado')} | slides={len(slides)} ({names})")
    return len(slides)


def drive_rows(file_id, needle, creds_path):
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload
    import openpyxl

    info = json.loads(Path(creds_path).read_text(encoding="utf-8"))
    scopes = info.get("scopes")
    if isinstance(scopes, str):
        scopes = [scopes]
    scopes = scopes or ["https://www.googleapis.com/auth/drive"]
    creds = Credentials(None, refresh_token=info["refresh_token"],
                        token_uri=info.get("token_uri", "https://oauth2.googleapis.com/token"),
                        client_id=info["client_id"], client_secret=info["client_secret"],
                        scopes=scopes)
    creds.refresh(Request())
    svc = build("drive", "v3", credentials=creds)
    meta = svc.files().get(fileId=file_id, fields="name,modifiedTime").execute()
    print(f"  [{meta['name']}] modificado {meta['modifiedTime']}")
    buf = io.BytesIO()
    dl = MediaIoBaseDownload(buf, svc.files().get_media(fileId=file_id))
    done = False
    while not done:
        _, done = dl.next_chunk()
    buf.seek(0)
    wb = openpyxl.load_workbook(buf)
    rows = []
    for ws in wb.worksheets:
        for r in ws.iter_rows(values_only=True):
            if r and any(c is not None and needle in str(c) for c in r):
                rows.append(r)
                print("    " + " | ".join("" if c is None else str(c)[:46] for c in r))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("needle", help="substring: 'sep12', '2026-09-12' o un id completo")
    ap.add_argument("--repo", help="ruta del repo marketing-campaign-generator")
    ap.add_argument("--local-only", action="store_true")
    a = ap.parse_args()

    repo = Path(a.repo) if a.repo else first_existing(REPO_CANDIDATES)
    if not repo:
        sys.exit("no encontré el repo; pasar --repo")
    cal = repo / "planning" / "calendario-sep2026" / "calendario.jsonl"
    print(f"repo: {repo}\ncalendario: {cal}")

    print("\n== JSONL local ==")
    fl = local_rows(cal, a.needle)
    for r in fl:
        describe(r, "local")
    if not fl:
        print("  (sin coincidencias)")

    if a.local_only:
        return
    creds_path = first_existing(CRED_CANDIDATES)
    if not creds_path:
        print("\n(sin credencial Drive; usar --local-only)")
        return
    for brand, fid in DRIVE_XLSX.items():
        print(f"\n== XLSX Drive ({brand}) ==")
        try:
            drive_rows(fid, a.needle, creds_path)
        except Exception as e:  # noqa: BLE001
            print(f"  error: {e}")

    print("\nRecordatorio: el espejo puede estar atrasado; comparar estado y nº de slides a ojo.")
    print(f"ids locales: {sorted(r['id'] for r in fl)}")


if __name__ == "__main__":
    main()
