#!/usr/bin/env python3
"""
ap_connect_flow.py — Crear una conexión en ActivePieces por REST (flujo white-label).

Uso (desde el contenedor hermes o cualquier host con /opt/data/.env):
    AP_URL=http://100.73.30.29:8088 \
    AP_CONNECTION=neuralcrew-gmail \
    GOOGLE_CLIENT_ID=<google-oauth-client-id> \
    REDIRECT_URL=https://connect.dominio.com/callback \
    python3 ap_connect_flow.py auth-url          # paso 1: imprime authorizationUrl (abrir en navegador)
    python3 ap_connect_flow.py complete <code>   # paso 2: entrega el code a AP y guarda la conexión

Requiere:
  - /opt/data/connections-map.json  (entrada con ap_user_id, ap_project_id, ap_platform_id, ap_token_version)
  - /opt/data/.env con AP_JWT_SECRET
  - El entry del mapa DEBE tener ap_token_version = user_identity.tokenVersion (si no, editarlo)

El script no toca la UI: crea/upserta la conexión dentro de ActivePieces (OAuth CLOUD_OAUTH2).
"""
import json, os, sys, time, hmac, hashlib, base64, urllib.request, urllib.error

AP_URL = os.environ.get("AP_URL", "http://100.73.30.29:8088")
CONNECTION = os.environ.get("AP_CONNECTION", "neuralcrew-gmail")
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
REDIRECT_URL = os.environ.get("REDIRECT_URL", "https://connect.neuralcrewlabs.com/callback")
PIECE = os.environ.get("AP_PIECE", "@activepieces/piece-gmail")
MAP_PATH = os.environ.get("MAP_PATH", "/opt/data/connections-map.json")
ENV_PATH = os.environ.get("ENV_PATH", "/opt/data/.env")


def b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def get_secret() -> str:
    for line in open(ENV_PATH):
        if line.startswith("AP_JWT_SECRET="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("AP_JWT_SECRET no encontrado en " + ENV_PATH)


def make_jwt(secret: str, uid: str, plid: str, token_version: str) -> str:
    now = int(time.time())
    payload = {
        "id": uid, "type": "USER", "platform": {"id": plid},
        "tokenVersion": token_version, "iss": "activepieces",
        "iat": now, "exp": now + 604800,
    }
    h = {"alg": "HS256", "typ": "JWT"}
    s1 = b64url(json.dumps(h, separators=(",", ":")).encode())
    s2 = b64url(json.dumps(payload, separators=(",", ":")).encode())
    return f"{s1}.{s2}." + b64url(hmac.new(secret.encode(), f"{s1}.{s2}".encode(), hashlib.sha256).digest())


def setup() -> tuple:
    cm = json.load(open(MAP_PATH))
    e = cm.get(CONNECTION)
    if not e:
        raise SystemExit(f"conexion {CONNECTION} no registrada en {MAP_PATH}")
    tok = make_jwt(get_secret(), e["ap_user_id"], e["ap_platform_id"],
                   e.get("ap_token_version", ""))
    if not e.get("ap_token_version"):
        print("AVISO: entry no tiene ap_token_version; el token puede fallar con 'session expired'")
    return tok, e["ap_project_id"]


def call(tok, pid, method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{AP_URL}{path}", data=data, method=method,
        headers={"Content-Type": "application/json", "Accept": "application/json",
                 "Authorization": f"Bearer {tok}", "X-Project-Id": pid})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        raise SystemExit(f"HTTP {e.code}: {e.read().decode()[:400]}")


def cmd_auth_url(tok, pid):
    _, resp = call(tok, pid, "POST", "/api/v1/app-connections/oauth2/authorization-url", {
        "pieceName": PIECE, "projectId": pid,
        "clientId": GOOGLE_CLIENT_ID, "redirectUrl": REDIRECT_URL,
    })
    url = resp.get("authorizationUrl", "")
    if not url:
        raise SystemExit("AP no devolvió authorizationUrl: " + json.dumps(resp)[:300])
    print("ABRE ESTA URL EN EL NAVEGADOR:")
    print(url)


def cmd_complete(tok, pid, code):
    status, resp = call(tok, pid, "POST", "/api/v1/app-connections", {
        "externalId": CONNECTION, "displayName": CONNECTION, "pieceName": PIECE,
        "projectId": pid, "type": "CLOUD_OAUTH2",
        "value": {"client_id": GOOGLE_CLIENT_ID, "code": code,
                  "scope": "<scopes que AP pidió en la URL>", "type": "CLOUD_OAUTH2"},
    })
    print("CONECTADO:", status, resp.get("externalId") or json.dumps(resp)[:200])


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "auth-url"
    tok, pid = setup()
    if cmd == "auth-url":
        cmd_auth_url(tok, pid)
    elif cmd == "complete":
        if len(sys.argv) < 3:
            raise SystemExit("uso: ap_connect_flow.py complete <code>")
        cmd_complete(tok, pid, sys.argv[2])
    else:
        raise SystemExit("uso: ap_connect_flow.py [auth-url|complete <code>]")