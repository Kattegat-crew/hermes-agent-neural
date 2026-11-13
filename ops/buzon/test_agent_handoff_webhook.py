"""Tests de integración: el depósito del buzón no puede depender del webhook.

Invoca `agent_handoff.py` como subproceso (es el contrato real: un usuario o un
agente lo ejecuta por CLI) contra un inbox temporal y un servidor HTTP local que
verifica la firma. Nunca toca /opt/hermes-agent-data/inbox.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

AQUI = Path(__file__).resolve().parent
SCRIPT = AQUI / "agent_handoff.py"
SECRET = "secreto-buzon-test"


class _Server:
    def __init__(self, status: int = 202, verify: bool = True):
        self.status = status
        self.verify = verify
        self.hits: list[dict] = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                length = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(length)
                ts = self.headers.get("X-Webhook-Timestamp", "")
                expected = hmac.new(
                    SECRET.encode(), ts.encode() + b"." + body, hashlib.sha256
                ).hexdigest()
                provided = self.headers.get("X-Webhook-Signature-V2", "")
                ok = hmac.compare_digest(provided, expected) if outer.verify else True
                outer.hits.append(
                    {
                        "path": self.path,
                        "body": json.loads(body or b"{}"),
                        "firma_ok": ok,
                        "webhook_id": self.headers.get("webhook-id"),
                    }
                )
                code = outer.status if ok else 403
                self.send_response(code)
                self.end_headers()
                self.wfile.write(b"{}")

            def log_message(self, format, *args):  # noqa: A002
                return

        self._httpd = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self._httpd.server_address[1]}"
        self._t = threading.Thread(target=self._httpd.serve_forever, daemon=True)

    def __enter__(self):
        self._t.start()
        return self

    def __exit__(self, *exc):
        self._httpd.shutdown()
        self._httpd.server_close()


def _run(tmp_path: Path, *extra: str) -> subprocess.CompletedProcess:
    cmd = [
        sys.executable,
        str(SCRIPT),
        "send",
        "--from",
        "ragnar",
        "--to",
        "ullr",
        "--asunto",
        "prueba de push",
        "--tarea",
        "verificar el aviso",
        "--id",
        "tkt-20261113-ragnar-ullr-0001",
        "--inbox-root",
        str(tmp_path),
        *extra,
    ]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=60)


def test_deposita_y_avisa_con_firma_valida(tmp_path):
    with _Server(status=202, verify=True) as srv:
        out = _run(tmp_path, "--webhook-base", srv.url, "--webhook-secret", SECRET)
        assert out.returncode == 0, out.stderr
        destino = tmp_path / "ullr" / "from-ragnar" / "tkt-20261113-ragnar-ullr-0001.json"
        assert destino.exists(), "el ticket debe quedar depositado"
        assert len(srv.hits) == 1
        assert srv.hits[0]["firma_ok"] is True
        # ruta derivada del receptor, no del emisor
        assert srv.hits[0]["path"] == "/p/ullr/webhooks/buzon-ullr"
        assert srv.hits[0]["body"]["ticket_id"] == "tkt-20261113-ragnar-ullr-0001"
        assert "aviso enviado" in out.stdout.lower()


def test_webhook_caido_no_rompe_el_deposito(tmp_path):
    # Puerto cerrado garantizado
    import socket

    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    puerto = s.getsockname()[1]
    s.close()
    out = _run(
        tmp_path, "--webhook-base", f"http://127.0.0.1:{puerto}", "--webhook-secret", SECRET
    )
    assert out.returncode == 0, out.stderr
    destino = tmp_path / "ullr" / "from-ragnar" / "tkt-20261113-ragnar-ullr-0001.json"
    assert destino.exists(), "el depósito es la fuente de verdad y no puede fallar"
    contenido = json.loads(destino.read_text(encoding="utf-8"))
    assert contenido["id"] == "tkt-20261113-ragnar-ullr-0001"
    assert "sin aviso" in out.stdout.lower() or "aviso fallido" in out.stdout.lower()


def test_no_webhook_bandera_desactiva_el_envio(tmp_path):
    with _Server(status=202) as srv:
        out = _run(tmp_path, "--webhook-base", srv.url, "--webhook-secret", SECRET, "--no-webhook")
        assert out.returncode == 0, out.stderr
        assert srv.hits == []
        assert (tmp_path / "ullr" / "from-ragnar" / "tkt-20261113-ragnar-ullr-0001.json").exists()


def test_sin_secreto_no_intenta(tmp_path):
    with _Server(status=202) as srv:
        # "" explícito = sin secreto. Hermético: no lee los secretos reales de la máquina.
        out = _run(tmp_path, "--webhook-base", srv.url, "--webhook-secret", "")
        assert out.returncode == 0, out.stderr
        assert srv.hits == []
        assert "sin aviso" in out.stdout.lower()


def test_http_500_no_rompe_el_deposito(tmp_path):
    with _Server(status=500, verify=False) as srv:
        out = _run(tmp_path, "--webhook-base", srv.url, "--webhook-secret", SECRET)
        assert out.returncode == 0, out.stderr
        assert len(srv.hits) == 1
        assert (tmp_path / "ullr" / "from-ragnar" / "tkt-20261113-ragnar-ullr-0001.json").exists()


def _reply(tmp_path: Path, ticket: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "reply", "--agent", "ullr", "--ticket", ticket,
         "--respuesta", "hecho", "--inbox-root", str(tmp_path)],
        capture_output=True, text=True, timeout=60,
    )


def test_reply_no_confunde_tkt_1_con_tkt_11(tmp_path):
    """El glob por subcadena cerraba tkt-11 cuando se pedía tkt-1."""
    _run(tmp_path, "--webhook-secret", "", "--id", "tkt-1")
    _run(tmp_path, "--webhook-secret", "", "--id", "tkt-11")
    out = _reply(tmp_path, "tkt-1")
    assert out.returncode == 0, out.stderr
    done = tmp_path / "ullr" / "done"
    assert (done / "tkt-1.json").exists()
    assert not (done / "tkt-11.json").exists(), "tkt-11 no era el objetivo"


def test_reply_falla_si_el_id_es_ambiguo(tmp_path):
    _run(tmp_path, "--webhook-secret", "", "--id", "tkt-dup")
    # segundo depósito con el mismo id en otra carpeta de origen
    _run(tmp_path, "--webhook-secret", "", "--id", "tkt-dup", "--from", "bragi")
    out = _reply(tmp_path, "tkt-dup")
    assert out.returncode == 1
    assert "ambiguo" in out.stderr.lower()


def test_reply_no_sobrescribe_una_respuesta_previa(tmp_path):
    _run(tmp_path, "--webhook-secret", "", "--id", "tkt-r")
    assert _reply(tmp_path, "tkt-r").returncode == 0
    _run(tmp_path, "--webhook-secret", "", "--id", "tkt-r")
    out = _reply(tmp_path, "tkt-r")
    assert out.returncode == 1
    assert "ya existe" in out.stderr.lower()
