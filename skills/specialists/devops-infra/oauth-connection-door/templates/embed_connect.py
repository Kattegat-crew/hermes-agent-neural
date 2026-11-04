#!/usr/bin/env python3
"""
Embed Connect Gateway — ActivePieces connect() para la puerta NeuralCrew.

Servidor probado (2026-08): página "Conectar con <marca>" + /api/jwt (JWT embebido
tipo USER) + secuencia de activepieces.connect() por pieza (gmail/drive/calendar).
Cada connect() crea UNA conexión DENTRO de AP; el connectionName es el externalId.

Requisitos para correr (env):
  AP_INSTANCE_URL=<http://...:8088>   # interna del contenedor o Tailscale
  AP_JWT_SECRET=<AP_JWT_SECRET>       # firma HS256 (mismo secret de los JWT MCP)
  AP_PLATFORM_ID / AP_PROJECT_ID / AP_USER_ID  # SELECT id FROM platform/project/"user" en ap-db
  TENANT=<tenant>                     # ej. neuralcrew → conexiones {tenant}-gmail/-drive/-calendar
  PORT=<puerto>
"""

import base64
import hashlib
import hmac
import json
import os
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse


AP_INSTANCE_URL = os.environ.get("AP_INSTANCE_URL", "http://100.73.30.29:8088")
AP_JWT_SECRET = os.environ.get("AP_JWT_SECRET", "")          # REQUERIDO
AP_PLATFORM_ID = os.environ.get("AP_PLATFORM_ID", "")        # REQUERIDO
AP_PROJECT_ID = os.environ.get("AP_PROJECT_ID", "")          # REQUERIDO
AP_USER_ID = os.environ.get("AP_USER_ID", "")                # REQUERIDO
TENANT = os.environ.get("TENANT", "neuralcrew")
PORT = int(os.environ.get("PORT", "8648"))

# UNA conexión por pieza — cada piece pide sus propios scopes en el consent screen.
PIECES = [
    {"label": "Gmail", "pieceName": "@activepieces/piece-gmail",
     "connectionName": f"{TENANT}-gmail"},
    {"label": "Drive", "pieceName": "@activepieces/piece-google-drive",
     "connectionName": f"{TENANT}-drive"},
    {"label": "Calendar", "pieceName": "@activepieces/piece-google-calendar",
     "connectionName": f"{TENANT}-calendar"},
]


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def sign_hs256(data: bytes, secret: str) -> str:
    return b64url(hmac.new(secret.encode(), data, hashlib.sha256).digest())


def make_embed_jwt() -> str:
    """JWT de usuario embebido para activepieces.configure() — tipo USER, NO el JWT MCP."""
    if not AP_JWT_SECRET:
        raise ValueError("AP_JWT_SECRET no configurado")
    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": AP_USER_ID,
        "platformId": AP_PLATFORM_ID,
        "projectId": AP_PROJECT_ID,
        "type": "USER",
        "tokenVersion": 1,          # requerido por AP (extraído de la DB)
        "iat": now,
        "exp": now + 3600,          # 1h para el embed
    }
    h = b64url(json.dumps(header, separators=(",", ":")).encode())
    p = b64url(json.dumps(payload, separators=(",", ":")).encode())
    sig = sign_hs256(f"{h}.{p}".encode(), AP_JWT_SECRET)
    return f"{h}.{p}.{sig}"


PAGE_HTML = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Conectar con NeuralCrew Labs</title>
<style>
  :root { --bg:#0D0D0D; --card:#1A1A1A; --gold:#d4af37; --ok:#4CAF50; --err:#f44336; }
  * { box-sizing:border-box; margin:0; padding:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; }
  body { background:var(--bg); min-height:100vh; display:flex; align-items:center; justify-content:center; padding:20px; }
  .card { background:var(--card); border-radius:20px; max-width:420px; width:100%; padding:36px 32px; text-align:center; }
  .logo { font-size:22px; font-weight:800; letter-spacing:2px; color:#fff; }
  .logo span { color:var(--gold); }
  h1 { color:#fff; font-size:24px; margin:18px 0 8px; }
  .sub { color:#bbb; font-size:14px; line-height:1.5; margin-bottom:24px; }
  .btn { width:100%; display:flex; align-items:center; justify-content:center; gap:10px;
         background:#fff; color:#333; border:none; border-radius:10px; padding:13px 16px;
         font-size:15px; font-weight:600; cursor:pointer; transition:opacity .2s; }
  .btn:disabled { opacity:.6; cursor:wait; }
  .btn svg { width:20px; height:20px; }
  .benefits { text-align:left; margin:20px 0 4px; }
  .benefits li { color:#ccc; font-size:13px; list-style:none; margin:8px 0; display:flex; gap:8px; align-items:center; }
  .benefits li::before { content:"✓"; color:var(--gold); font-weight:700; }
  .status { margin-top:16px; font-size:14px; min-height:20px; }
  .ok { color:var(--ok); } .err { color:var(--err); }
  .footer { margin-top:20px; font-size:11px; color:#777; }
  .spinner { display:inline-block; width:14px; height:14px; border:2px solid #888; border-top-color:var(--gold);
             border-radius:50%; animation:spin .8s linear infinite; vertical-align:-2px; }
  @keyframes spin { to { transform:rotate(360deg); } }
</style>
</head>
<body>
<div class="card">
  <div class="logo">NEURAL<span>CREW</span> <span>LABS</span></div>
  <h1>Conecta tu cuenta</h1>
  <p class="sub">Autoriza a NeuralCrew a gestionar tus comunicaciones de marketing.<br>Solo te tomará 10 segundos.</p>
  <button class="btn" id="connectBtn" onclick="startConnect()">
    <svg viewBox="0 0 24 24" fill="none"><path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.27-4.74 3.27-8.1z" fill="#4285F4"/><path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84A11 11 0 0 0 12 23z" fill="#34A853"/><path d="M5.84 14.1a6.6 6.6 0 0 1 0-4.2V7.06H2.18a11 11 0 0 0 0 9.88l3.66-2.84z" fill="#FBBC05"/><path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15A11 11 0 0 0 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z" fill="#EA4335"/></svg>
    Continuar con Google
  </button>
  <ul class="benefits">
    <li>Leer y enviar correo de tu cuenta</li>
    <li>Gestionar tu calendario</li>
    <li>Acceso a tus archivos de Drive</li>
  </ul>
  <div class="status" id="status"></div>
  <div class="footer">Tus datos están seguros. Solo autorizas lo que NeuralCrew necesita para operar tu campaña.</div>
</div>

<script src="https://cdn.activepieces.com/sdk/embed/0.13.0.js"></script>
<script>
async function startConnect() {
  const btn = document.getElementById('connectBtn');
  const status = document.getElementById('status');
  btn.disabled = true;
  status.className = 'status';
  status.innerHTML = '<span class="spinner"></span> Preparando conexión...';
  try {
    // 1. JWT embebido + lista de piezas desde nuestro backend
    const jwtRes = await fetch('/api/jwt');
    if (!jwtRes.ok) throw new Error('No se pudo iniciar (jwt) ' + jwtRes.status);
    const { jwtToken, instanceUrl, pieces } = await jwtRes.json();

    // 2. Configurar SDK de AP
    await activepieces.configure({ instanceUrl, jwtToken });

    // 3. Diálogo embebido por pieza — la conexión nace DENTRO de AP
    const done = [];
    const skipped = [];
    for (const p of pieces) {
      status.innerHTML = '<span class="spinner"></span> Conectando ' + p.label + '...';
      const result = await activepieces.connect({
        pieceName: p.pieceName,
        connectionName: p.connectionName,
      });
      if (result && result.connection) {
        done.push(p.label);
      } else {
        skipped.push(p.label);
      }
    }

    if (done.length === pieces.length) {
      status.className = 'status ok';
      status.textContent = '✅ Conectado: ' + done.join(', ');
    } else if (done.length > 0) {
      status.className = 'status ok';
      status.textContent = '✅ Conectado: ' + done.join(', ') +
        (skipped.length ? ' | Pendiente (se cerró): ' + skipped.join(', ') : '');
    } else {
      status.className = 'status';
      status.textContent = 'No se conectó nada. Puedes reintentar.';
    }
  } catch (e) {
    status.className = 'status err';
    status.textContent = '❌ Error: ' + e.message + '. Intenta de nuevo.';
  } finally {
    btn.disabled = false;
  }
}
</script>
</body>
</html>
"""


FILE_DIR = os.path.dirname(os.path.abspath(__file__))


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, ctype: str = "text/html; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, name: str):
        path = os.path.join(FILE_DIR, name)
        if os.path.exists(path):
            with open(path, "rb") as f:
                self._send(200, f.read())
        else:
            self._send(404, b"Not found")

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            self._send(200, PAGE_HTML.encode())
        elif path == "/privacy":
            self._send_file("privacy.html")
        elif path == "/terms":
            self._send_file("terms.html")
        elif path == "/api/health":
            ok = bool(AP_JWT_SECRET and AP_PLATFORM_ID and AP_PROJECT_ID and AP_USER_ID)
            self._send(200 if ok else 503,
                       json.dumps({"status": "ok" if ok else "incomplete-config"}).encode(),
                       "application/json")
        elif path == "/api/jwt":
            try:
                body = json.dumps({
                    "jwtToken": make_embed_jwt(),
                    "instanceUrl": AP_INSTANCE_URL,
                    "pieces": PIECES,
                }).encode()
                self._send(200, body, "application/json")
            except Exception as e:
                self._send(500, json.dumps({"error": str(e)}).encode(), "application/json")
        else:
            self._send(404, b"Not found")

    def log_message(self, format, *args):  # noqa: A002
        pass


if __name__ == "__main__":
    print(f"Embed Connect Gateway en :{PORT} (tenant={TENANT})")
    ok = AP_JWT_SECRET and AP_PLATFORM_ID and AP_PROJECT_ID and AP_USER_ID
    print("config JWT:", "OK" if ok else "FALTA: AP_JWT_SECRET/AP_PLATFORM_ID/AP_PROJECT_ID/AP_USER_ID")
    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()