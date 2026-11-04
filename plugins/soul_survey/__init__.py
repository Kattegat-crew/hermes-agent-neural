"""Soul Survey Plugin for Hermes Agent."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

from .survey_engine import handle_survey_message, load_state

logger = logging.getLogger("hermes.plugins.soul_survey")


def _on_pre_gateway_dispatch(event: Any, gateway: Any, **kwargs: Any) -> Optional[Dict[str, Any]]:
    try:
        source = getattr(event, "source", None)
        if not source:
            return None

        chat_id = getattr(source, "chat_id", None)
        text = (getattr(event, "text", "") or "").strip().lower()
        is_trigger = text in {"/soul", "soul", "comienza la encuesta", "perfilame", "configurar mi agente", "quiero mi soul"}
        state = load_state(chat_id) if chat_id else None

        if is_trigger or state:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(handle_survey_message(event, gateway))
            return {"action": "skip", "reason": "soul_survey_active"}

        return None
    except Exception as e:
        logger.warning("soul_survey hook error: %s", e)
        return None


def register(ctx: Any) -> None:
    ctx.register_hook("pre_gateway_dispatch", _on_pre_gateway_dispatch)
