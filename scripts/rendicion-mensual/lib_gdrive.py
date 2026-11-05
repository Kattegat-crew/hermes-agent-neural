#!/usr/bin/env python3
"""lib_gdrive.py — helpers de Google Drive/Sheets para la rendición mensual.

Intercambio de refresh_token -> access_token según el patrón canónico de la skill
google-workspace-ops (secrets en /opt/data/secrets/<conn>.json).
Solo stdlib. NUNCA imprime tokens.
"""
import json
import urllib.parse
import urllib.request

SECRETS_DIR = "/opt/data/secrets"

# Hojas de Bre-B (fuente real, verificada el 2026-11-04):
#   golden: 'Bre-B Golden — Pagos' con tabs [base, Informe Septiembre, Informe Octubre]
#   lucky:  'Bre-B Lucky — Pagos' con tabs [base, Informe Septiembre, Informe Octubre]
BREB_SHEETS = {
    "golden": "1j0vsPs4R4owvm_gisidizO0j0xckeZpK4z-Mev2xYu0",
    "lucky": "1bAcrcBjddAAqxo8V3xnwmOElk_9bAay5G-w1ZREUfGo",
}

_drive_tokens = {}


def _secret_path(conn: str) -> str:
    return f"{SECRETS_DIR}/{conn}.json"


def access_token(conn: str) -> str:
    """conn = nombre del secret, ej 'golden-drive', 'lucky-drive', 'jonathan-drive'."""
    if conn in _drive_tokens:
        return _drive_tokens[conn]
    cred = json.load(open(_secret_path(conn), encoding="utf-8"))
    body = urllib.parse.urlencode({
        "client_id": cred["client_id"],
        "client_secret": cred["client_secret"],
        "refresh_token": cred["refresh_token"],
        "grant_type": "refresh_token",
    }).encode()
    r = urllib.request.urlopen(
        urllib.request.Request("https://oauth2.googleapis.com/token", body), timeout=30)
    tok = json.loads(r.read())["access_token"]
    _drive_tokens[conn] = tok
    return tok


def gapi(conn: str, url: str, method: str = "GET", data=None, timeout=60):
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + access_token(conn)},
                                 method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
        req.data = json.dumps(data).encode()
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read())


def drive_search(conn: str, query: str, fields="files(id,name,mimeType,parents)", page_size=50):
    q = urllib.parse.quote(f"{query} and trashed=false")
    url = ("https://www.googleapis.com/drive/v3/files?q=" + q +
           f"&pageSize={page_size}&fields={fields}")
    return gapi(conn, url).get("files", [])


def sheet_tabs(conn: str, sheet_id: str):
    meta = gapi(conn, f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}"
                      "?fields=properties.title,sheets.properties.title")
    return [s["properties"]["title"] for s in meta["sheets"]]


def sheet_values(conn: str, sheet_id: str, rng: str):
    url = (f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}/values/"
           + urllib.parse.quote(rng))
    return gapi(conn, url).get("values", [])


def export_csv(conn: str, file_id: str) -> str:
    url = f"https://www.googleapis.com/drive/v3/files/{file_id}/export?mimeType=text/csv"
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + access_token(conn)})
    return urllib.request.urlopen(req, timeout=90).read().decode("utf-8", errors="replace")
