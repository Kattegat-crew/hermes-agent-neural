"""Ticket board sync — listener `threadUpdate` del foro de tickets.

Cuando el adapter Discord normaliza un cambio de ``applied_tags`` como
``thread_tags_changed`` (#tablero de prioridades), este plugin dispara el motor
de regeneración que recalcula el tablero desde los tags del foro:

    /opt/hermes-agent/skills/ops/discord-server-ops/scripts/regenerar_tablero.py --publish

No reimplementa nada: filtra, coalescea la ráfaga y lo corre fuera del loop de
eventos. El cron diario 06:00 (``tablero-tickets-0600``) queda como red de
seguridad si este listener no corre.
"""

from __future__ import annotations

import logging
import subprocess
import threading
from typing import Any, Optional

logger = logging.getLogger("hermes.plugins.ticket_board_sync")

FORUM_ID = "1554957746980261938"
BOARD_CHANNEL_ID = "1569356056176361605"
SCRIPT = ("/opt/hermes-agent/skills/ops/discord-server-ops/scripts/"
          "regenerar_tablero.py")
DEBOUNCE_S = 6.0
RUN_TIMEOUT_S = 180

_lock = threading.Lock()
_state: dict[str, Any] = {"pending": 0, "timer": None, "running": False}


def should_sync(event_type: Optional[str], payload: Optional[dict]) -> bool:
    """True solo para cambios de tag del foro de tickets."""
    if event_type != "thread_tags_changed":
        return False
    if not payload:
        return False
    if str(payload.get("parent_chat_id")) != FORUM_ID:
        return False
    return payload.get("old_tags") != payload.get("new_tags")


def _arm(seconds: float) -> None:
    timer = threading.Timer(seconds, _fire)
    timer.daemon = True
    _state["timer"] = timer
    timer.start()


def _fire() -> None:
    with _lock:
        _state["timer"] = None
        if _state["running"]:
            _arm(DEBOUNCE_S)  # corrida en curso: los cambios en vuelo se reprograman
            return
        _state["running"] = True
        _state["pending"] = 0
    try:
        proc = subprocess.run(
            ["python3", SCRIPT, "--publish"],
            capture_output=True, text=True, timeout=RUN_TIMEOUT_S,
        )
        salida = ((proc.stdout or "").strip() or (proc.stderr or "").strip())[-500:]
        if proc.returncode:
            logger.warning("[ticket-board-sync] regeneración exit=%s: %s",
                           proc.returncode, salida)
        else:
            logger.info("[ticket-board-sync] tablero regenerado: %s", salida)
    except subprocess.TimeoutExpired:
        logger.error("[ticket-board-sync] timeout tras %ss", RUN_TIMEOUT_S)
    except Exception as exc:  # nunca tirar el evento de la plataforma
        logger.error("[ticket-board-sync] error de regeneración: %s", exc)
    finally:
        with _lock:
            _state["running"] = False
            if _state["pending"] > 0:
                _arm(DEBOUNCE_S)


def _schedule() -> None:
    with _lock:
        _state["pending"] += 1
        if _state["timer"] is not None:
            return  # ráfaga: la corrida pendiente ya va a ver este estado
        _arm(DEBOUNCE_S)


def _on_platform_event(platform: Optional[str] = None,
                       event_type: Optional[str] = None,
                       payload: Optional[dict] = None,
                       **_kwargs: Any) -> None:
    """Hook ``gateway_platform_event`` — coalescea y dispara en hilo aparte."""
    try:
        if platform != "discord":
            return None
        if not should_sync(event_type, payload):
            return None
        _schedule()
    except Exception as exc:
        logger.warning("[ticket-board-sync] hook error: %s", exc)
    return None


def register(ctx: Any) -> None:
    ctx.register_hook("gateway_platform_event", _on_platform_event)
