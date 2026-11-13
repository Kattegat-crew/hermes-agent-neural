"""Tests de contrato para ops/buzon/notify.py.

Regla del receptor (gateway/platforms/webhook.py, Generic V2):
  X-Webhook-Timestamp  = epoch
  X-Webhook-Signature-V2 = hex HMAC-SHA256(secret, "<timestamp>." + body)
  webhook-id           = clave de idempotencia (prioridad de _header_delivery_id)

Estos tests levantan un servidor HTTP real en loopback y verifican la firma con
la misma fórmula, para no probar contra un mock que acepta cualquier cosa.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

import notify as notify_mod
from notify import notify


SECRET = "s3cr3t-de-prueba"


class _Server:
    """Servidor HTTP de un solo uso que registra la petición recibida."""

    def __init__(self, status: int = 202, delay: float = 0.0, verify_signature: bool = False):
        self.status = status
        self.delay = delay
        self.verify_signature = verify_signature
        self.requests: list[dict] = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802 - API de http.server
                length = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(length)
                if outer.delay:
                    time.sleep(outer.delay)
                record = {
                    "path": self.path,
                    "headers": {k.lower(): v for k, v in self.headers.items()},
                    "body": body,
                    "body_json": json.loads(body or b"{}"),
                }
                outer.requests.append(record)
                code = outer.status
                if outer.verify_signature:
                    ts = self.headers.get("X-Webhook-Timestamp", "")
                    provided = self.headers.get("X-Webhook-Signature-V2", "")
                    expected = hmac.new(
                        SECRET.encode(), ts.encode() + b"." + body, hashlib.sha256
                    ).hexdigest()
                    if not provided or not hmac.compare_digest(provided, expected):
                        code = 403
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status":"accepted"}')

            def log_message(self, format, *args):  # noqa: A002 - firma de http.server
                return

        self._httpd = HTTPServer(("127.0.0.1", 0), Handler)
        self.port = self._httpd.server_address[1]
        self.url = f"http://127.0.0.1:{self.port}"
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._httpd.shutdown()
        self._httpd.server_close()


def _payload():
    return {
        "event_type": "buzon.nuevo",
        "ticket_id": "ticket-20261113-ragnar-001",
        "de": "ragnar",
        "asunto": "prueba de push",
    }


def test_envia_a_la_ruta_del_perfil_con_firma_aceptada():
    with _Server(status=202, verify_signature=True) as srv:
        res = notify(
            "ullr",
            _payload(),
            base_url=srv.url,
            secret=SECRET,
        )
        assert res.sent is True
        assert res.status == 202
        assert len(srv.requests) == 1
        req = srv.requests[0]
        assert req["path"] == "/p/ullr/webhooks/buzon"
        assert req["body_json"]["ticket_id"] == _payload()["ticket_id"]
        assert req["headers"]["webhook-id"] == _payload()["ticket_id"]


def test_firma_invalida_es_rechazada_y_no_reintenta():
    with _Server(status=202, verify_signature=True) as srv:
        res = notify("ullr", _payload(), base_url=srv.url, secret="secreto-equivocado")
        # El servidor de prueba firma con SECRET; con otro secreto debe rechazar.
        assert res.sent is False
        assert res.status == 403
        assert len(srv.requests) == 1


def test_timeout_no_lanza_y_reporta():
    with _Server(status=202, delay=1.5) as srv:
        res = notify("ullr", _payload(), base_url=srv.url, secret=SECRET, timeout=0.2)
        assert res.sent is False
        assert res.reason in {"timeout", "error"}


def test_http_500_no_lanza():
    with _Server(status=500) as srv:
        res = notify("ullr", _payload(), base_url=srv.url, secret=SECRET)
        assert res.sent is False
        assert res.status == 500


def test_host_inalcanzable_no_lanza():
    # Puerto cerrado: se reserva uno y se libera para garantizar que nadie escucha.
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    res = notify("ullr", _payload(), base_url=f"http://127.0.0.1:{port}", secret=SECRET, timeout=0.5)
    assert res.sent is False
    assert res.reason in {"error", "timeout"}


def test_webhook_id_es_estable_por_ticket():
    with _Server(status=202) as srv:
        notify("ullr", _payload(), base_url=srv.url, secret=SECRET)
        notify("ullr", _payload(), base_url=srv.url, secret=SECRET)
        ids = [r["headers"]["webhook-id"] for r in srv.requests]
        assert ids[0] == ids[1] == "ticket-20261113-ragnar-001"


def test_secreto_vacio_no_envia():
    with _Server(status=202) as srv:
        res = notify("ullr", _payload(), base_url=srv.url, secret="")
        assert res.sent is False
        assert res.reason == "sin_secreto"
        assert srv.requests == []


def test_el_modulo_no_importa_el_gateway():
    """El notificador debe ser stdlib puro: se instala fuera del repo."""
    fuente = notify_mod.__file__ or ""
    with open(fuente, encoding="utf-8") as fh:
        texto = fh.read()
    for prohibido in ("import gateway", "from gateway", "import hermes"):
        assert prohibido not in texto


class _NoSerializable:
    """Objeto que json.dumps no puede serializar."""


def test_payload_no_serializable_no_lanza():
    """Hallazgo del reviewer: json.dumps estaba fuera del try y escapaba."""
    res = notify(
        "ullr",
        {"event_type": "buzon.nuevo", "objeto": _NoSerializable()},
        base_url="http://127.0.0.1:9",
        secret=SECRET,
    )
    assert res.sent is False
    assert res.reason == "error"


def test_clock_no_callable_no_lanza():
    res = notify(
        "ullr",
        {"event_type": "buzon.nuevo", "ticket_id": "x-1"},
        base_url="http://127.0.0.1:9",
        secret=SECRET,
        clock=None,
    )
    assert res.sent is False


def test_id_idempotencia_sin_ticket_usa_digest_completo():
    """Dos cuerpos distintos no pueden colisionar por un prefijo de 32 hex."""
    cuerpo = b'{"event_type":"buzon.nuevo"}'
    identificador = notify_mod._id_idempotencia({}, cuerpo)
    assert len(identificador) == 64
    assert identificador == hashlib.sha256(cuerpo).hexdigest()


def test_id_idempotencia_prefiere_el_ticket():
    assert notify_mod._id_idempotencia({"ticket_id": "tkt-9"}, b"{}") == "tkt-9"


@pytest.mark.parametrize(
    "kwargs,esperado",
    [
        ({"perfil": "../etc", "ruta": "buzon"}, "perfil_invalido"),
        ({"perfil": "a b", "ruta": "buzon"}, "perfil_invalido"),
        ({"perfil": "ullr", "ruta": "../x"}, "ruta_invalida"),
        ({"perfil": "ullr", "ruta": "a/b"}, "ruta_invalida"),
        ({"perfil": "ullr", "ruta": "buzon", "base_url": "ftp://x"}, "base_invalida"),
    ],
)
def test_segmentos_de_url_se_validan(kwargs, esperado):
    """perfil y ruta entran crudos en la URL: un `../` cambiaría el destino."""
    datos = {"perfil": "ullr", "ruta": "buzon", "base_url": "http://127.0.0.1:9"}
    datos.update(kwargs)
    res = notify(
        datos["perfil"],
        {"event_type": "buzon.nuevo", "ticket_id": "x-1"},
        base_url=datos["base_url"],
        secret=SECRET,
        ruta=datos["ruta"],
    )
    assert res.sent is False
    assert res.reason == esperado
