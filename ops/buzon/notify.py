"""Notificación push del buzón de agentes contra el webhook del gateway.

El buzón (`agent_handoff.py`) escribe el encargo en `inbox/<perfil>/from-<origen>/`;
hasta hoy el receptor se enteraba por polling (un cron por perfil cada minuto).
Este módulo emite el aviso en el momento, sin cambiar la fuente de verdad: el
archivo se deposita igual y el barrido lento sigue siendo la red de seguridad.

Contrato con el receptor (`gateway/platforms/webhook.py`, esquema *Generic V2*):

    POST {base_url}/p/{perfil}/webhooks/{ruta}
    X-Webhook-Timestamp     epoch (el adaptador aplica ventana anti-replay)
    X-Webhook-Signature-V2  hex HMAC-SHA256(secreto, "<timestamp>.<body>")
    webhook-id              clave de idempotencia (TTL 3600 s en el gateway)

Reglas de diseño:

* **Nunca lanza.** Un fallo de red no puede tumbar el depósito del buzón; se
  devuelve un `NotifyResult` con el motivo y el barrido recogerá el mensaje.
* **Sin reintentos.** El reintento es el barrido lento, no un bucle aquí dentro:
  reintentar en el emisor multiplica sesiones cuando el gateway está saturado.
* **stdlib puro.** Se instala en `/opt/data/scripts/` fuera del repo, así que no
  puede importar `gateway.*` ni `hermes.*`.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Mapping, Optional

__all__ = ["NotifyResult", "notify", "EVENTO_NUEVO", "firmar"]

EVENTO_NUEVO = "buzon.nuevo"
RUTA_POR_DEFECTO = "buzon"
TIMEOUT_POR_DEFECTO = 2.0


@dataclass(frozen=True)
class NotifyResult:
    """Resultado de un intento de notificación. Nunca se propaga una excepción."""

    sent: bool
    status: Optional[int] = None
    reason: Optional[str] = None

    def __bool__(self) -> bool:  # azúcar: `if notify(...)`
        return self.sent


def firmar(secreto: str, timestamp: str, cuerpo: bytes) -> str:
    """Firma Generic V2: hex HMAC-SHA256 de ``"<timestamp>.<cuerpo>"``."""
    return hmac.new(
        secreto.encode("utf-8"), timestamp.encode("ascii") + b"." + cuerpo, hashlib.sha256
    ).hexdigest()


def _id_idempotencia(payload: Mapping[str, Any], cuerpo: bytes) -> str:
    """Clave estable: el ticket si existe; si no, el hash del cuerpo."""
    for clave in ("ticket_id", "id", "msg_id"):
        valor = payload.get(clave)
        if isinstance(valor, str) and valor.strip():
            return valor.strip()
    return hashlib.sha256(cuerpo).hexdigest()[:32]


def notify(
    perfil: str,
    payload: Mapping[str, Any],
    *,
    base_url: str,
    secret: str,
    ruta: str = RUTA_POR_DEFECTO,
    timeout: float = TIMEOUT_POR_DEFECTO,
    clock=time.time,
) -> NotifyResult:
    """Emite un evento de buzón al webhook del perfil destino.

    Devuelve siempre un `NotifyResult`; el llamador decide qué hacer con un fallo
    (por diseño: registrar y seguir, porque el barrido lento recoge el mensaje).
    """
    if not isinstance(secret, str) or not secret.strip():
        # Sin secreto el receptor rechaza con 403; no gastamos el viaje.
        return NotifyResult(False, None, "sin_secreto")
    if not perfil or not isinstance(perfil, str):
        return NotifyResult(False, None, "sin_perfil")

    cuerpo = json.dumps(dict(payload), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    timestamp = str(int(clock()))
    url = f"{base_url.rstrip('/')}/p/{perfil}/webhooks/{ruta}"
    request = urllib.request.Request(
        url,
        data=cuerpo,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Webhook-Timestamp": timestamp,
            "X-Webhook-Signature-V2": firmar(secret, timestamp, cuerpo),
            "webhook-id": _id_idempotencia(payload, cuerpo),
            "User-Agent": "hermes-buzon-notify/1",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as respuesta:
            return NotifyResult(True, int(respuesta.status))
    except urllib.error.HTTPError as exc:
        return NotifyResult(False, int(exc.code), "http")
    except (socket.timeout, TimeoutError):
        return NotifyResult(False, None, "timeout")
    except urllib.error.URLError as exc:
        motivo = "timeout" if isinstance(exc.reason, (socket.timeout, TimeoutError)) else "error"
        return NotifyResult(False, None, motivo)
    except Exception:  # noqa: BLE001 - el buzón no puede fallar por el aviso
        return NotifyResult(False, None, "error")
