#!/usr/bin/env python3
"""
ap_call.py — Wrapper de enforcement para conexiones ActivePieces (Capa 5).
"El SOUL es el contrato, la Capa 5 es la ley."

Todo acceso a conexiones de AP pasa por este script. Valida que el perfil
llamador es el DUEÑO de la conexión antes de permitir la llamada. Si no lo
es, bloquea con error claro y registra el intento.

Uso:
    ap_call.py --connection <nombre> --action <accion> [--params '<json>'] [--profile <perfil>]

El perfil se detecta automáticamente de HERMES_HOME si no se pasa --profile:
    /opt/data/profiles/<name> -> <name>
    /opt/data               -> default

Salidas:
    exit 0 + JSON resultado (si es dueño y AP responde)
    exit 1 + BLOCKED (si no es dueño)
    exit 2 (error de config/mapa)
    exit 3 (error de AP)

Mapa de conexiones: /opt/data/connections-map.json (fuente de verdad local,
editado por admin; el mismo mapa vive en Engram con topic_key connections-map).
"""
import argparse
import json
import os
import sys
import time
import subprocess
from datetime import datetime, timezone
from pathlib import Path

MAP_PATH = Path("/opt/data/connections-map.json")
LOG_PATH = Path("/opt/data/logs/ap_call.log")
AP_URL = os.environ.get("AP_URL", "http://100.73.30.29:8088/mcp")
AP_HOST = os.environ.get("AP_HOST", "169.58.189.222")
AP_SSH_USER = os.environ.get("AP_SSH_USER", "root")


def log(line: str):
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with open(LOG_PATH, "a") as f:
        f.write(f"{ts} {line}\n")


def detect_profile() -> str:
    """Detecta el perfil llamador desde HERMES_HOME."""
    hh = os.environ.get("HERMES_HOME", "")
    if not hh:
        return "default"
    hh = str(Path(hh).resolve())
    if "/profiles/" in hh:
        return Path(hh).name
    return "default"


def load_map() -> dict:
    if not MAP_PATH.exists():
        return {}
    return json.loads(MAP_PATH.read_text())


def get_ap_jwt_secret() -> str:
    """Lee el secret del JWT de AP. Intenta env primero, luego SSH al host."""
    s = os.environ.get("AP_JWT_SECRET", "")
    if s:
        return s
    try:
        r = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=8", "-o", "StrictHostKeyChecking=no",
             f"{AP_SSH_USER}@{AP_HOST}",
             "docker exec ap-app printenv AP_JWT_SECRET 2>/dev/null"],
            capture_output=True, text=True, timeout=15,
        )
        return r.stdout.strip()
    except Exception:
        return ""


def make_jwt(secret: str, user_id: str, project_id: str, platform_id: str) -> str:
    """Genera JWT HS256 para el MCP de AP (payload mcp_oauth, TTL 15 min)."""
    import hmac
    import base64
    import hashlib

    def b64url(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

    header = {"alg": "HS256", "typ": "JWT"}
    now = int(time.time())
    payload = {
        "sub": user_id,
        "projectId": project_id,
        "platformId": platform_id,
        "type": "mcp_oauth",
        "aud": "MCP_OAUTH_ACCESS",
        "iat": now,
        "exp": now + 900,
    }
    seg1 = b64url(json.dumps(header, separators=(",", ":")).encode())
    seg2 = b64url(json.dumps(payload, separators=(",", ":")).encode())
    signing = f"{seg1}.{seg2}".encode()
    sig = b64url(hmac.new(secret.encode(), signing, hashlib.sha256).digest())
    return f"{seg1}.{seg2}.{sig}"


def main():
    p = argparse.ArgumentParser(description="AP connection wrapper (Capa 5)")
    p.add_argument("--connection", required=True, help="Nombre de conexión: {tenant}-{servicio}")
    p.add_argument("--action", required=True, help="Acción a ejecutar (ej. gmail_send, gmail_search)")
    p.add_argument("--params", default="{}", help="JSON con parámetros de la acción")
    p.add_argument("--profile", default=None, help="Perfil llamador (default: auto de HERMES_HOME)")
    args = p.parse_args()

    profile = args.profile or detect_profile()
    try:
        params = json.loads(args.params) if args.params else {}
    except json.JSONDecodeError as e:
        log(f"[ERROR] perfil={profile} params inválidos: {e}")
        print(json.dumps({"error": f"params inválidos: {e}"}))
        sys.exit(2)

    # 1. Validar dueño contra el mapa
    cmap = load_map()
    entry = cmap.get(args.connection)
    if not entry:
        log(f"[BLOQUEADO] perfil={profile} conexion={args.connection} (no existe en el mapa)")
        print(json.dumps({"blocked": True, "reason": f"conexion {args.connection} no registrada en connections-map"}))
        sys.exit(1)

    owner = entry.get("owner", "")
    if owner and owner != profile:
        log(f"[BLOQUEADO] perfil={profile} conexion={args.connection} (dueño={owner})")
        print(json.dumps({"blocked": True, "reason": f"perfil {profile} no es dueño de {args.connection}"}))
        sys.exit(1)

    # 2. Ejecutar vía AP MCP
    secret = get_ap_jwt_secret()
    if not secret:
        log(f"[ERROR] perfil={profile} sin AP_JWT_SECRET accesible")
        print(json.dumps({"error": "no se pudo obtener AP_JWT_SECRET"}))
        sys.exit(2)

    user_id = entry.get("ap_user_id", "00000000-0000-0000-0000-000000000000")
    project_id = entry.get("ap_project_id", "00000000-0000-0000-0000-000000000000")
    platform_id = entry.get("ap_platform_id", "00000000-0000-0000-0000-000000000000")

    token = make_jwt(secret, user_id, project_id, platform_id)

    mcp_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": args.action, "arguments": params},
    }

    try:
        import urllib.request
        req = urllib.request.Request(
            AP_URL,
            data=json.dumps(mcp_request).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read().decode()
        log(f"[OK] perfil={profile} conexion={args.connection} accion={args.action}")
        print(body)
        sys.exit(0)
    except Exception as e:
        log(f"[ERROR] perfil={profile} conexion={args.connection} accion={args.action}: {e}")
        print(json.dumps({"error": str(e)}))
        sys.exit(3)


if __name__ == "__main__":
    main()
