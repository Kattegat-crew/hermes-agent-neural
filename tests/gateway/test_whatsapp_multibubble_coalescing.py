"""Tests for WhatsApp multi-bubble & multimodal batching, presence extension, and mid-turn redirect/steer."""

from __future__ import annotations

import asyncio
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gateway.config import Platform, PlatformConfig
from gateway.platforms.base import BasePlatformAdapter, _append_text
from gateway.platforms.event import MessageEvent, MessageType
from gateway.platforms.helpers import (
    await_batch_quiet_and_presence,
    merge_inbound_batch_event,
    resolve_batch_params_for_event,
    should_batch_inbound_event,
)
from gateway.profile_routing import ProfileRoute
from gateway.run import GatewayRunner
from gateway.session import SessionSource, build_session_key


class _DummyWhatsAppAdapter(BasePlatformAdapter):
    def __init__(self, extra: dict | None = None):
        cfg = PlatformConfig(enabled=True, extra=extra or {})
        super().__init__(cfg, Platform.WHATSAPP)
        self._configure_text_batch_delays()
        self.dispatched: list[MessageEvent] = []
        self.composing_states: list[bool] = []

    async def connect(self) -> bool:
        return True

    async def disconnect(self) -> None:
        return None

    async def send(self, chat_id: str, content: str, reply_to=None, metadata=None):
        return None

    async def get_chat_info(self, chat_id: str) -> dict:
        return {"name": chat_id, "type": "dm"}

    async def handle_message(self, event: MessageEvent) -> None:
        self.dispatched.append(event)

    async def _is_sender_composing(self, event: MessageEvent) -> bool:
        if self.composing_states:
            return self.composing_states.pop(0)
        return False


def _wa_event(
    text: str = "",
    *,
    msg_id: str = "m1",
    msg_type: MessageType = MessageType.TEXT,
    media_urls: list[str] | None = None,
    media_types: list[str] | None = None,
    media_text_inlined: list[bool | None] | None = None,
    profile: str | None = "roshi",
) -> MessageEvent:
    source = SessionSource(
        platform=Platform.WHATSAPP,
        chat_id="153580212334603@lid",
        chat_type="dm",
        user_id="573334011599",
        user_name="Jesús Díaz",
        profile=profile,
    )
    return MessageEvent(
        text=text,
        message_type=msg_type,
        source=source,
        message_id=msg_id,
        media_urls=list(media_urls or []),
        media_types=list(media_types or []),
        media_text_inlined=list(media_text_inlined or []),
    )


class TestMultimodalBatchCoalescing:
    """Verify N consecutive bubbles (text + document + voice + photo) coalesce without limit."""

    def test_six_consecutive_multimodal_bubbles_merge_cleanly(self):
        b1 = _wa_event("Hola Roshi", msg_id="b1")
        b2 = _wa_event("Necesito que revises este informe", msg_id="b2")
        b3 = _wa_event(
            "[Content of notes.txt]:\nResumen",
            msg_id="b3",
            msg_type=MessageType.DOCUMENT,
            media_urls=["/cache/doc_1_notes.txt"],
            media_types=["text/plain"],
            media_text_inlined=[True],
        )
        b4 = _wa_event(
            "",
            msg_id="b4",
            msg_type=MessageType.PHOTO,
            media_urls=["/cache/img_2_chart.png"],
            media_types=["image/png"],
        )
        b5 = _wa_event(
            "",
            msg_id="b5",
            msg_type=MessageType.VOICE,
            media_urls=["/cache/aud_3_voice.ogg"],
            media_types=["audio/ogg; codecs=opus"],
        )
        b6 = _wa_event("Y me digas qué opinas de los puntos 2 y 3", msg_id="b6")

        for incoming in (b2, b3, b4, b5, b6):
            merge_inbound_batch_event(b1, incoming, _append_text)

        assert getattr(b1, "_batch_chunk_count", 1) == 6
        assert "Hola Roshi" in b1.text
        assert "Necesito que revises este informe" in b1.text
        assert "Y me digas qué opinas de los puntos 2 y 3" in b1.text
        assert b1.media_urls == [
            "/cache/doc_1_notes.txt",
            "/cache/img_2_chart.png",
            "/cache/aud_3_voice.ogg",
        ]
        assert b1.media_types == ["text/plain", "image/png", "audio/ogg; codecs=opus"]
        assert b1.media_text_inlined == [True, None, None]
        # VOICE takes priority so STT still transcribes the voice note while document/image handlers run by MIME
        assert b1.message_type == MessageType.VOICE
        assert b1.message_id == "b6"

    def test_profile_scoped_batch_overrides_apply_only_to_configured_profile(self):
        adapter = _DummyWhatsAppAdapter(
            extra={
                "profile_batch_overrides": {
                    "roshi": {
                        "text_batch_delay_seconds": 3.0,
                        "text_batch_presence_extend_seconds": 2.5,
                        "text_batch_hard_cap_seconds": 10.0,
                        "multimodal_batching": True,
                    }
                }
            }
        )
        roshi_doc = _wa_event("", msg_id="d1", msg_type=MessageType.DOCUMENT, profile="roshi")
        default_doc = _wa_event("", msg_id="d2", msg_type=MessageType.DOCUMENT, profile="default")
        slash_cmd = _wa_event("/stop", msg_id="d3", msg_type=MessageType.TEXT, profile="roshi")

        roshi_params = resolve_batch_params_for_event(adapter, roshi_doc)
        default_params = resolve_batch_params_for_event(adapter, default_doc)

        assert roshi_params["delay"] == 3.0
        assert roshi_params["presence_extend"] == 2.5
        assert roshi_params["hard_cap"] == 10.0
        assert roshi_params["multimodal"] is True
        assert should_batch_inbound_event(adapter, roshi_doc) is True

        assert default_params["delay"] == pytest.approx(0.3)
        assert default_params["multimodal"] is False
        assert should_batch_inbound_event(adapter, default_doc) is False
        assert should_batch_inbound_event(adapter, slash_cmd) is False

    @pytest.mark.asyncio
    async def test_presence_extension_and_hard_cap_bound_wait_time(self):
        adapter = _DummyWhatsAppAdapter(
            extra={
                "profile_batch_overrides": {
                    "roshi": {
                        "text_batch_delay_seconds": 0.05,
                        "text_batch_presence_extend_seconds": 0.05,
                        "text_batch_hard_cap_seconds": 0.16,
                        "multimodal_batching": True,
                    }
                }
            }
        )
        # Keep composing True forever — hard_cap must terminate the loop deterministically
        adapter.composing_states = [True, True, True, True, True, True]
        ev1 = _wa_event("Parte 1", msg_id="m1", profile="roshi")
        ev2 = _wa_event("Parte 2", msg_id="m2", profile="roshi")

        start = time.monotonic()
        adapter._enqueue_text_event(ev1)
        adapter._enqueue_text_event(ev2)
        key = adapter._text_batch_key(ev1)
        task = adapter._pending_text_batch_tasks.get(key)
        assert task is not None
        await asyncio.wait_for(task, timeout=2.0)
        elapsed = time.monotonic() - start

        assert len(adapter.dispatched) == 1
        assert adapter.dispatched[0].text == "Parte 1\nParte 2"
        assert adapter.dispatched[0].message_id == "m2"
        assert 0.12 <= elapsed < 0.5


class TestBusyMultimodalRedirectAndSteer:
    """Verify mid-turn messages redirect in-flight model calls or steer during tool execution."""

    @pytest.mark.asyncio
    async def test_steer_mode_redirects_when_model_request_is_in_flight(self):
        runner = object.__new__(GatewayRunner)
        runner.config = SimpleNamespace(multiplex_profiles=False)
        runner._running_agents = {}
        runner._session_Runtime = {}
        runner._subagent_Disable = False
        runner._agent_has_active_subagents = lambda _agent: False
        runner._session_has_compression_in_flight = lambda _sk, _a: False
        runner._pending_event_audio_paths = lambda _ev: []
        runner._redirect_active_turn = MagicMock(return_value=True)
        runner._try_agent_verb = MagicMock(return_value=True)
        runner._fold_into_running_turn = MagicMock()

        model_active = threading.Event()
        model_active.set()
        running_agent = SimpleNamespace(
            _supports_active_turn_redirect=True,
            _executing_tools=False,
            _model_request_active=model_active,
            redirect=MagicMock(return_value=True),
            steer=MagicMock(return_value=True),
        )
        event = _wa_event("Olvidé adjuntar este dato adicional", msg_id="m9")

        outcome = await runner._resolve_busy_steer_or_redirect(
            event, "agent:roshi:whatsapp:dm:573334011599", "steer", running_agent
        )

        assert outcome.redirected is True
        assert outcome.steered is False
        runner._redirect_active_turn.assert_called_once()
        runner._try_agent_verb.assert_not_called()

    @pytest.mark.asyncio
    async def test_steer_mode_enriches_document_attachment_and_steers_during_tools(self):
        runner = object.__new__(GatewayRunner)
        runner.config = SimpleNamespace(multiplex_profiles=False)
        runner._agent_has_active_subagents = lambda _agent: False
        runner._session_has_compression_in_flight = lambda _sk, _a: False
        runner._pending_event_audio_paths = lambda _ev: []
        runner._try_agent_verb = MagicMock(return_value=True)
        runner._fold_into_running_turn = MagicMock()

        model_active = threading.Event()  # Not in model call; executing tools instead
        running_agent = SimpleNamespace(
            _supports_active_turn_redirect=True,
            _executing_tools=True,
            _model_request_active=model_active,
            redirect=MagicMock(return_value=True),
            steer=MagicMock(return_value=True),
        )
        event = _wa_event(
            "Aquí va el archivo que faltaba",
            msg_id="m10",
            msg_type=MessageType.DOCUMENT,
            media_urls=["/opt/hermes-agent-data/cache/documents/doc_123_RAE_3.docx"],
            media_types=["application/vnd.openxmlformats-officedocument.wordprocessingml.document"],
            media_text_inlined=[False],
        )

        outcome = await runner._resolve_busy_steer_or_redirect(
            event, "agent:roshi:whatsapp:dm:573334011599", "steer", running_agent
        )

        assert outcome.steered is True
        assert outcome.redirected is False
        runner._try_agent_verb.assert_called_once()
        steered_text = runner._try_agent_verb.call_args.args[2]
        assert "RAE_3.docx" in steered_text
        assert "Aquí va el archivo que faltaba" in steered_text


class TestSharedWhatsAppStandaloneProfileRouting:
    """Verify shared primary WhatsApp bridge can route to a standalone profile ('roshi')."""

    def test_shared_whatsapp_route_resolves_standalone_roshi_profile(self):
        runner = object.__new__(GatewayRunner)
        runner.config = SimpleNamespace(
            multiplex_profiles=True,
            profile_routes=[
                ProfileRoute(
                    name="chucho-wa-lid",
                    platform="whatsapp",
                    chat_id="153580212334603@lid",
                    profile="roshi",
                )
            ],
        )
        source = SessionSource(
            platform=Platform.WHATSAPP,
            chat_id="153580212334603@lid",
            chat_type="dm",
            user_id="153580212334603@lid",
        )
        with (
            patch("hermes_cli.profiles.profiles_to_serve", return_value=[("default", Path("/opt/data"))]),
            patch("hermes_cli.profiles.profile_exists", return_value=True),
            patch("hermes_cli.profiles.profile_is_standalone", return_value=True),
            patch("hermes_cli.profiles.get_profile_dir", return_value=Path("/opt/data/profiles/roshi")),
        ):
            assert runner._profile_name_for_source(source) == "roshi"
