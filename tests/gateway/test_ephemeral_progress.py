"""TDD Tests for Ephemeral Contextual Progress, Heartbeat, and Thread-Safe Cleanup."""

from __future__ import annotations

import asyncio
import queue
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from agent.display import prepare_tool_preview
from agent.i18n import t
from gateway.activity_labels import activity_label
from gateway.run_turn_runner import TurnRunner


@pytest.fixture(autouse=True)
def _set_spanish_locale(monkeypatch):
    """Default to Spanish for contextual progress testing."""
    monkeypatch.setenv("HERMES_LANGUAGE", "es")


def test_progress_absorb_replace_mode():
    """When tool_progress_grouping is 'replace', _progress_absorb replaces the buffer line instead of appending."""
    class DummyContext:
        progress_grouping = "replace"
        progress_queue = MagicMock()
        last_progress_msg = [None]
        repeat_count = [0]
    
    class DummyState:
        progress_lines = []
        progress_msg_id = "msg-123"
        can_edit = True
        progress_grouping = "replace"

    ctx = DummyContext()
    runner = MagicMock()
    runner_obj = TurnRunner(runner, ctx)

    st = DummyState()
    # First line
    res1 = runner_obj._progress_absorb(st, "⏳ Leyendo archivo config.yaml (5s)")
    assert st.progress_lines == ["⏳ Leyendo archivo config.yaml (5s)"]
    assert res1 == "⏳ Leyendo archivo config.yaml (5s)"

    # Second line: must REPLACE, not append!
    res2 = runner_obj._progress_absorb(st, "⏳ Buscando en la web por \"test\" (12s)")
    assert st.progress_lines == ["⏳ Buscando en la web por \"test\" (12s)"]
    assert len(st.progress_lines) == 1
    assert res2 == "⏳ Buscando en la web por \"test\" (12s)"

    # Deduplicated tuple in replace mode: must also replace
    res3 = runner_obj._progress_absorb(st, ("__dedup__", "⏳ Buscando en la web por \"test\" (12s)", 1))
    assert st.progress_lines == ["⏳ Buscando en la web por \"test\" (12s) (×2)"]
    assert len(st.progress_lines) == 1


def test_progress_absorb_accumulate_mode():
    """In 'accumulate' mode, _progress_absorb appends as before."""
    class DummyContext:
        progress_grouping = "accumulate"
    
    class DummyState:
        progress_lines = []
        progress_grouping = "accumulate"

    ctx = DummyContext()
    runner = MagicMock()
    runner_obj = TurnRunner(runner, ctx)

    st = DummyState()
    runner_obj._progress_absorb(st, "Line 1")
    runner_obj._progress_absorb(st, "Line 2")
    assert st.progress_lines == ["Line 1", "Line 2"]
    assert len(st.progress_lines) == 2


def test_contextual_labels_spanish():
    """Contextual labels provide human-friendly Spanish actions with target resources."""
    # Terminal command: should show inline command without raw fenced code blocks
    prep_term = prepare_tool_preview("terminal", {"command": "git status -s"}, fallback="", max_len=60)
    assert "git status -s" in prep_term.text

    # Read file: shows path or filename
    prep_file = prepare_tool_preview("read_file", {"path": "/opt/hermes-agent/gateway/run_turn.py"}, fallback="", max_len=60)
    assert "run_turn.py" in prep_file.text

    # Web search: shows query
    prep_search = prepare_tool_preview("web_search", {"query": "error discord 404"}, fallback="", max_len=60)
    assert "error discord 404" in prep_search.text


@pytest.mark.asyncio
async def test_discord_delete_thread_aware():
    """Discord adapter delete_message checks thread channel context when given parent or thread id."""
    from plugins.platforms.discord.adapter import DiscordAdapter
    from gateway.config import PlatformConfig

    config = PlatformConfig(enabled=True, token="test-token", extra={})
    adapter = DiscordAdapter(config)
    mock_client = MagicMock()
    adapter._client = mock_client

    mock_channel = MagicMock()
    mock_msg = MagicMock()
    mock_msg.delete = AsyncMock()
    mock_channel.get_partial_message.return_value = mock_msg
    mock_client.get_channel.return_value = mock_channel

    success = await adapter.delete_message(chat_id="123456", message_id="789012")
    assert success is True
    mock_channel.get_partial_message.assert_called_once_with(789012)
    mock_msg.delete.assert_awaited_once()


def test_long_running_i18n_catalog():
    """Verify long_running i18n keys are properly loaded for both English and Spanish."""
    assert t("long_running.action_shell", lang="en") == "running commands"
    assert t("long_running.action_shell", lang="es") == "ejecutando comandos"
    assert t("long_running.action_files", lang="es") == "revisando archivos"
    assert t("long_running.action_writing", lang="es") == "escribiendo cambios"


@pytest.mark.asyncio
async def test_whatsapp_delete_message():
    """WhatsApp adapter delete_message calls bridge POST /delete."""
    from plugins.platforms.whatsapp.adapter import WhatsAppAdapter
    from gateway.config import PlatformConfig

    config = PlatformConfig(enabled=True, extra={})
    adapter = WhatsAppAdapter(config)
    adapter._bridge_unavailable = AsyncMock(return_value=None)
    
    mock_resp = AsyncMock()
    mock_resp.status = 200
    
    class MockContextManager:
        async def __aenter__(self):
            return mock_resp
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    adapter._bridge_req = MagicMock(return_value=MockContextManager())

    success = await adapter.delete_message(chat_id="573107864877", message_id="msg-abc-123")
    assert success is True
    adapter._bridge_req.assert_called_once_with(
        "post", "delete", 15, json={"chatId": "573107864877@s.whatsapp.net", "messageId": "msg-abc-123"}
    )


def test_multi_agent_chat_suppression():
    """Multi-agent chats suppress progress messages to prevent bot-to-bot ping pong loops."""
    from gateway.display_config import is_multi_agent_chat

    class DummySource:
        chat_id = "group-123"
        thread_id = "thread-456"
        platform = MagicMock(value="discord")

    source = DummySource()
    cfg_with_multi = {
        "display": {
            "multi_agent_channels": ["thread-456", "channel-789"]
        }
    }
    assert is_multi_agent_chat(source, user_config=cfg_with_multi) is True

    cfg_other = {
        "display": {
            "multi_agent_channels": ["other-channel"]
        }
    }
    assert is_multi_agent_chat(source, user_config=cfg_other) is False

    assert t("long_running.action_model", lang="es") == "esperando al modelo"


def test_multi_agent_chat_matches_parent_chat_id_and_alias():
    """A configured container parent suppresses child-channel progress too."""
    from gateway.display_config import is_multi_agent_chat

    source = SimpleNamespace(chat_id="child-thread", thread_id="", parent_chat_id="shared-parent")
    assert is_multi_agent_chat(
        source, user_config={"display": {"multi_agent_channels": ["shared-parent"]}},
    ) is True
    assert is_multi_agent_chat(
        source, user_config={"display": {"multi_agent_chats": ["shared-parent"]}},
    ) is True
    assert is_multi_agent_chat(
        source, user_config={"display": {"multi_agent_channels": ["unrelated-parent"]}},
    ) is False


def test_heartbeat_queue_exists_when_tool_progress_is_off(monkeypatch):
    """Heartbeat-only turns still create the existing queue when tool progress is disabled."""
    from gateway.config import Platform
    from gateway.run import GatewayRunner

    runner = GatewayRunner.__new__(GatewayRunner)
    runner._delivery_adapter_for = MagicMock(return_value=SimpleNamespace(supports_status_text=False))
    runner._resolve_turn_toolsets = MagicMock(return_value=([], []))
    monkeypatch.setattr("gateway.run._load_gateway_config", lambda: {"display": {"tool_progress": "off"}})
    monkeypatch.setattr("agent.secret_scope.get_secret", lambda _name: None)

    disp = runner._run_agent_display_settings(SimpleNamespace(platform=Platform.TELEGRAM, chat_id="chat"))

    assert disp.tool_progress_enabled is False
    assert disp.needs_progress_queue is True


@pytest.mark.asyncio
async def test_heartbeat_queues_status_for_shared_progress_writer(monkeypatch):
    """The heartbeat producer queues a typed status update instead of sending independently."""
    from gateway.run import GatewayRunner

    runner = GatewayRunner.__new__(GatewayRunner)
    runner._should_emit_long_running_notification = MagicMock(side_effect=[True, True, False])
    runner._agent_activity_summary = MagicMock(return_value=None)
    class ProgressAdapter:
        name = "fake"

        def __init__(self):
            self.sent = []
            self.edited = []

        async def send(self, **kwargs):
            self.sent.append(kwargs)
            return SimpleNamespace(success=True, message_id="status-1")

        async def edit_message(self, **kwargs):
            self.edited.append(kwargs)
            return SimpleNamespace(success=True, message_id="status-1")

        async def send_typing(self, *_args, **_kwargs):
            return None

    adapter = ProgressAdapter()
    runner._delivery_adapter_for = MagicMock(return_value=adapter)
    progress_queue = queue.Queue()
    turn_ctx = SimpleNamespace(
        source=SimpleNamespace(chat_id="chat", platform=SimpleNamespace(value="telegram")),
        session_key="session", agent_holder=[object()], _status_thread_metadata={"thread_id": "thread"},
        progress_queue=progress_queue, _cleanup_progress=True, _cleanup_msg_ids=[],
    )
    disp = SimpleNamespace(
        user_config={}, platform_key="telegram",
        _display_surface_mode=lambda *args, **kwargs: "generic",
        resolve_display_setting=lambda *args, **kwargs: False,
        _generic_status_phrase=lambda *args, **kwargs: "Still working",
    )

    async def no_wait(_seconds):
        return None

    monkeypatch.setattr(asyncio, "sleep", no_wait)
    from gateway.run import _interim_metadata, _non_conversational_metadata
    monkeypatch.setattr("gateway.run.resolve_gateway_notify_interval", lambda _config: 1)

    await runner._run_agent_notify_long_running(disp, turn_ctx, [object()])

    update = progress_queue.get_nowait()
    assert update.text == "Still working"
    assert update.metadata == _interim_metadata(
        _non_conversational_metadata({"thread_id": "thread"}, platform=turn_ctx.source.platform)
    )
    assert adapter.sent == []
    assert adapter.edited == []
    progress_queue.put(update)

    current_checks = iter([True, True, True, False])
    progress_ctx = SimpleNamespace(
        source=turn_ctx.source, progress_queue=progress_queue, progress_grouping="replace",
        _progress_metadata={"progress": True}, _progress_reply_to=None, _cleanup_progress=True,
        _cleanup_msg_ids=[], _run_still_current=lambda: next(current_checks),
        agent_holder=[object()], _thinking_enabled=False, _native_slack_task_cards=False,
        last_progress_msg=[None], repeat_count=[0],
    )
    monkeypatch.setattr("gateway.run_turn_runner.time.monotonic", lambda: 2.0)
    await TurnRunner(runner, progress_ctx).send_progress_messages()
    assert len(adapter.sent) == 1
    assert adapter.sent[0]["content"] == "Still working"
    assert adapter.sent[0]["metadata"] == update.metadata
    assert progress_ctx._cleanup_msg_ids == ["status-1"]


@pytest.mark.asyncio
async def test_heartbeat_does_not_queue_after_generation_or_cancel_invalidation(monkeypatch):
    """The existing run-ownership guard prevents stale/cancelled heartbeat publication."""
    from gateway.run import GatewayRunner

    runner = GatewayRunner.__new__(GatewayRunner)
    runner._should_emit_long_running_notification = MagicMock(return_value=False)
    progress_queue = queue.Queue()
    turn_ctx = SimpleNamespace(
        source=SimpleNamespace(chat_id="chat", platform=SimpleNamespace(value="telegram")),
        session_key="session", agent_holder=[object()], _status_thread_metadata={},
        progress_queue=progress_queue,
    )
    disp = SimpleNamespace(
        user_config={}, platform_key="telegram",
        _display_surface_mode=lambda *args, **kwargs: "generic",
    )

    async def no_wait(_seconds):
        return None

    monkeypatch.setattr(asyncio, "sleep", no_wait)
    monkeypatch.setattr("gateway.run.resolve_gateway_notify_interval", lambda _config: 1)

    await runner._run_agent_notify_long_running(disp, turn_ctx, [object()])

    assert progress_queue.empty()
    runner._should_emit_long_running_notification.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("event_order", ["heartbeat_first", "tool_first", "concurrent"])
async def test_tool_and_heartbeat_share_one_replace_bubble(monkeypatch, event_order):
    """Tool and heartbeat events serialize through one replace-mode bubble in every arrival order."""
    from gateway.run import GatewayRunner
    from gateway.run_turn_runner import _ProgressStatusUpdate

    class ProgressAdapter:
        name = "fake"

        def __init__(self):
            self.sent = []
            self.edited = []

        async def send(self, **kwargs):
            self.sent.append(kwargs)
            return SimpleNamespace(success=True, message_id="shared-status")

        async def edit_message(self, **kwargs):
            self.edited.append(kwargs)
            return SimpleNamespace(success=True, message_id="shared-status")

        async def send_typing(self, *_args, **_kwargs):
            return None

    adapter = ProgressAdapter()
    runner = GatewayRunner.__new__(GatewayRunner)
    runner._delivery_adapter_for = MagicMock(return_value=adapter)
    progress_queue = queue.Queue()
    heartbeat = _ProgressStatusUpdate("Still working", {"heartbeat": True})
    tool_event = "Reading a file"
    if event_order == "heartbeat_first":
        progress_queue.put(heartbeat)
        progress_queue.put(tool_event)
    elif event_order == "tool_first":
        progress_queue.put(tool_event)
        progress_queue.put(heartbeat)
    else:
        barrier = threading.Barrier(3)

        def publish(item):
            barrier.wait()
            progress_queue.put(item)

        heartbeat_thread = threading.Thread(target=publish, args=(heartbeat,))
        tool_thread = threading.Thread(target=publish, args=(tool_event,))
        heartbeat_thread.start()
        tool_thread.start()
        barrier.wait()
        heartbeat_thread.join()
        tool_thread.join()

    current_checks = iter([True, True, True, True, True, True, False])
    progress_ctx = SimpleNamespace(
        source=SimpleNamespace(chat_id="chat"), progress_queue=progress_queue,
        progress_grouping="replace", _progress_metadata={"tool": True}, _progress_reply_to=None,
        _cleanup_progress=False, _cleanup_msg_ids=[], _run_still_current=lambda: next(current_checks),
        agent_holder=[object()], _thinking_enabled=False, _native_slack_task_cards=False,
        last_progress_msg=[None], repeat_count=[0],
    )
    monkeypatch.setattr(asyncio, "sleep", lambda _seconds: _resolved_future())
    clock_values = iter([2.0, 2.0, 3.5, 4.0])
    monkeypatch.setattr("gateway.run_turn_runner.time.monotonic", lambda: next(clock_values, 4.0))

    await TurnRunner(runner, progress_ctx).send_progress_messages()

    assert len(adapter.sent) == 1
    assert len(adapter.edited) == 1
    assert adapter.edited[0]["content"] in {"Still working", "Reading a file"}


def _resolved_future():
    """Return an awaitable for deterministic progress-consumer polling tests."""
    async def resolve():
        return None

    return resolve()


@pytest.mark.asyncio
@pytest.mark.parametrize("permanent_edit_failure", [False, True])
async def test_replace_heartbeat_degrades_without_accumulating(permanent_edit_failure, monkeypatch):
    """Uneditable/permanently uneditable replace-mode status sends at most one bubble."""
    from gateway.run import GatewayRunner
    from gateway.run_turn_runner import _ProgressStatusUpdate

    class NonEditableAdapter:
        name = "non-editable"

        def __init__(self):
            self.sent = []

        async def send(self, **kwargs):
            self.sent.append(kwargs)
            return SimpleNamespace(success=True, message_id="single-status")

        async def send_typing(self, *_args, **_kwargs):
            return None

    class PermanentlyUneditableAdapter(NonEditableAdapter):
        def __init__(self):
            super().__init__()
            self.edited = []

        async def edit_message(self, **kwargs):
            self.edited.append(kwargs)
            return SimpleNamespace(success=False, retryable=False, error="permission denied")

    adapter = PermanentlyUneditableAdapter() if permanent_edit_failure else NonEditableAdapter()
    runner = GatewayRunner.__new__(GatewayRunner)
    runner._delivery_adapter_for = MagicMock(return_value=adapter)
    progress_queue = queue.Queue()
    progress_queue.put(_ProgressStatusUpdate("Working 1", {"status": True}))
    progress_queue.put(_ProgressStatusUpdate("Working 2", {"status": True}))
    current_checks = iter([True, True, True, True, True, True, False])
    progress_ctx = SimpleNamespace(
        source=SimpleNamespace(chat_id="chat"), progress_queue=progress_queue,
        progress_grouping="replace", _progress_metadata=None, _progress_reply_to=None,
        _cleanup_progress=False, _cleanup_msg_ids=[], _run_still_current=lambda: next(current_checks),
        agent_holder=[object()], _thinking_enabled=False, _native_slack_task_cards=False,
        last_progress_msg=[None], repeat_count=[0],
    )
    monkeypatch.setattr(asyncio, "sleep", lambda _seconds: _resolved_future())
    clock_values = iter([2.0, 2.0, 3.5, 4.0])
    monkeypatch.setattr("gateway.run_turn_runner.time.monotonic", lambda: next(clock_values, 4.0))

    await TurnRunner(runner, progress_ctx).send_progress_messages()

    assert len(adapter.sent) == 1
    assert adapter.sent[0]["content"] == "Working 1"
    if permanent_edit_failure:
        assert len(adapter.edited) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("failed_update", ["heartbeat", "tool"])
async def test_replace_mode_permanent_edit_failure_suppresses_all_later_updates(failed_update):
    """A failed existing replace bubble must not be replaced by a second status bubble."""
    from gateway.run_turn_runner import _ProgressStatusUpdate

    class Adapter:
        name = "fake"

        def __init__(self):
            self.sent = []
            self.edited = []

        async def send(self, **kwargs):
            self.sent.append(kwargs)
            return SimpleNamespace(success=True, message_id="replacement")

        async def edit_message(self, **kwargs):
            self.edited.append(kwargs)
            return SimpleNamespace(success=False, retryable=False, error="permission denied")

        async def send_typing(self, *_args, **_kwargs):
            return None

    adapter = Adapter()
    ctx = SimpleNamespace(
        source=SimpleNamespace(chat_id="chat"), progress_grouping="replace",
        _progress_metadata=None, _progress_reply_to=None, _cleanup_progress=False,
        _cleanup_msg_ids=[],
    )
    turn_runner = TurnRunner(SimpleNamespace(), ctx)
    state = turn_runner._progress_edit_state(adapter)
    state.progress_msg_id = "original"
    state.progress_lines = ["First status"]
    state.can_edit = True

    state.heartbeat_update = failed_update == "heartbeat"
    await turn_runner._progress_send_or_edit(state, "First status")
    assert state.can_edit is False

    for raw in (_ProgressStatusUpdate("Still working", {}), "Reading a file"):
        state.heartbeat_update = isinstance(raw, _ProgressStatusUpdate)
        state.progress_lines = [raw.text if state.heartbeat_update else raw]
        await turn_runner._progress_send_or_edit(state, state.progress_lines[0])

    assert [call["message_id"] for call in adapter.edited] == ["original"]
    assert adapter.sent == []


@pytest.mark.asyncio
async def test_telegram_flood_edit_keeps_existing_bubble_and_backs_off(monkeypatch):
    """Telegram's real flood-cap result preserves the message ID and delays a later edit."""
    from gateway.run_turn_runner import _ProgressStatusUpdate
    from plugins.platforms.telegram.adapter import _flood_cap_result

    class Adapter:
        name = "telegram"

        def __init__(self):
            self.edited = []
            self.sent = []
            self.results = [_flood_cap_result(20), SimpleNamespace(success=True)]

        async def edit_message(self, **kwargs):
            self.edited.append(kwargs)
            return self.results.pop(0)

        async def send(self, **kwargs):
            self.sent.append(kwargs)
            return SimpleNamespace(success=True, message_id="new-message")

    now = [10.0]
    monkeypatch.setattr("gateway.run_turn_runner.time.monotonic", lambda: now[0])
    adapter = Adapter()
    ctx = SimpleNamespace(
        source=SimpleNamespace(chat_id="chat"), progress_grouping="replace",
        _progress_metadata=None, _progress_reply_to=None, _cleanup_progress=False,
        _cleanup_msg_ids=[],
    )
    turn_runner = TurnRunner(SimpleNamespace(), ctx)
    state = turn_runner._progress_edit_state(adapter)
    state.progress_msg_id = "original"
    state.progress_lines = ["Working"]
    state.can_edit = True
    state.heartbeat_update = True

    await turn_runner._progress_send_or_edit(state, "Working")
    assert state.progress_msg_id == "original"
    assert len(adapter.edited) == 1
    assert adapter.sent == []

    now[0] = 29.0
    state.progress_lines = ["Still working"]
    await turn_runner._progress_send_or_edit(state, "Still working")
    assert len(adapter.edited) == 1
    assert adapter.sent == []

    now[0] = 30.0
    await turn_runner._progress_send_or_edit(state, "Still working")
    assert len(adapter.edited) == 2
    assert state.progress_msg_id == "original"
    assert adapter.sent == []


@pytest.mark.asyncio
@pytest.mark.parametrize("native_success", [True, False])
async def test_slack_native_task_card_renders_heartbeat_in_same_lane(native_success):
    """Typed heartbeat updates remain visible through the task-card or its text fallback."""
    from gateway.run_turn_runner import _ProgressStatusUpdate

    class Adapter:
        def __init__(self):
            self.cards = []
            self.sent = []
            self.edited = []
            self.card_result = SimpleNamespace(success=native_success, error="Not connected")

        async def send_native_task_card_progress(self, **kwargs):
            self.cards.append(kwargs)
            return self.card_result

        async def edit_message(self, **kwargs):
            self.edited.append(kwargs)
            return SimpleNamespace(success=True, message_id="fallback-1")

        async def send(self, **kwargs):
            self.sent.append(kwargs)
            return SimpleNamespace(success=True, message_id="fallback-1")

        async def stop_native_task_card_progress(self, *_args, **_kwargs):
            return None

    adapter = Adapter()
    progress_queue = queue.Queue()
    progress_queue.put(_ProgressStatusUpdate("Working for 20 seconds", {"heartbeat": True}))
    progress_queue.put({"type": "tool.started", "tool_call_id": "tool-1", "tool_name": "read_file"})
    checks = iter([True, True, True, False])
    ctx = SimpleNamespace(
        source=SimpleNamespace(chat_id="C1"), progress_queue=progress_queue,
        _native_slack_task_cards=True, _run_still_current=lambda: next(checks),
        _agent_interrupted=lambda: False, _progress_reply_to="thread-1",
        _progress_metadata=None, tool_progress_enabled=True, _cleanup_progress=False,
        _cleanup_msg_ids=[],
    )

    await TurnRunner(SimpleNamespace(), ctx)._send_native_task_card_progress(adapter)

    assert adapter.cards
    assert any(
        task["title"] == "Working for 20 seconds"
        for call in adapter.cards for task in call["tasks"]
    )
    if native_success:
        assert adapter.sent == []
        assert adapter.edited == []
    else:
        assert len(adapter.sent) == 1
        assert "Working for 20 seconds" in adapter.sent[0]["content"]
        assert all(call["message_id"] == "fallback-1" for call in adapter.edited)


def test_working_heartbeat_duration_formatting():
    """Duration formatting in working_heartbeat does not duplicate units."""
    # 20 s should produce '20 s', not '20 s min'
    text_20s = t("gateway.progress.working_heartbeat", duration="20 s", minutes=1, detail=" — revisando", lang="es")
    assert "20 s min" not in text_20s
    assert "20 s — revisando" in text_20s

    # 2 min should produce '2 min', not '2 min min'
    text_2m = t("gateway.progress.working_heartbeat", duration="2 min", minutes=2, detail="", lang="es")
    assert "min min" not in text_2m
    assert "2 min" in text_2m


def test_format_duration_es():
    """format_duration_es returns clean Spanish duration strings."""
    from gateway.run import format_duration_es
    assert format_duration_es(0) == "0 s"
    assert format_duration_es(20) == "20 s"
    assert format_duration_es(59) == "59 s"
    assert format_duration_es(60) == "1 min"
    assert format_duration_es(120) == "2 min"
    assert format_duration_es(3600) == "1 h"
    assert format_duration_es(3660) == "1 h 1 min"
    assert format_duration_es(7320) == "2 h 2 min"


def test_gateway_notify_interval_resolution(monkeypatch):
    """resolve_gateway_notify_interval respects env var overrides, user config, and defaults."""
    from gateway.run import resolve_gateway_notify_interval

    monkeypatch.delenv("HERMES_AGENT_NOTIFY_INTERVAL", raising=False)

    # 1. Default fallback
    assert resolve_gateway_notify_interval() == 20.0

    # 2. Configured user_config positive
    cfg_pos = {"agent": {"gateway_notify_interval": 45}}
    assert resolve_gateway_notify_interval(user_config=cfg_pos) == 45.0

    # 3. Configured user_config zero/negative disables
    cfg_zero = {"agent": {"gateway_notify_interval": 0}}
    assert resolve_gateway_notify_interval(user_config=cfg_zero) == 0.0
    cfg_neg = {"agent": {"gateway_notify_interval": -5}}
    assert resolve_gateway_notify_interval(user_config=cfg_neg) == 0.0

    # 4. Env var overrides config
    monkeypatch.setenv("HERMES_AGENT_NOTIFY_INTERVAL", "15")
    assert resolve_gateway_notify_interval(user_config=cfg_pos) == 15.0

    # 5. Env var <= 0 disables notifications
    monkeypatch.setenv("HERMES_AGENT_NOTIFY_INTERVAL", "0")
    assert resolve_gateway_notify_interval(user_config=cfg_pos) == 0.0
    monkeypatch.setenv("HERMES_AGENT_NOTIFY_INTERVAL", "-1")
    assert resolve_gateway_notify_interval(user_config=cfg_pos) == 0.0


@pytest.mark.asyncio
async def test_whatsapp_delete_disconnected_bridge_contract():
    """WhatsApp delete_message returns boolean False (not a truthy SendResult) when bridge is unavailable."""
    from plugins.platforms.whatsapp.adapter import WhatsAppAdapter
    from gateway.config import PlatformConfig

    config = PlatformConfig(enabled=True, extra={})
    adapter = WhatsAppAdapter(config)
    adapter._bridge_unavailable = AsyncMock(return_value="Bridge unavailable")

    result = await adapter.delete_message("123456", "msg-001")
    assert result is False
    assert type(result) is bool


@pytest.mark.asyncio
async def test_discord_edit_thread_metadata():
    """Discord edit_message honors metadata thread_id and resolves the thread channel."""
    from plugins.platforms.discord.adapter import DiscordAdapter
    from gateway.config import PlatformConfig

    config = PlatformConfig(enabled=True, token="test-token", extra={})
    adapter = DiscordAdapter(config)
    adapter._client = MagicMock()

    mock_thread = MagicMock()
    mock_msg = MagicMock()
    mock_msg.edit = AsyncMock()
    mock_thread.get_partial_message.return_value = mock_msg

    adapter._resolve_channel = AsyncMock(return_value=mock_thread)

    res = await adapter.edit_message("parent-channel", "123456", "New text", metadata={"thread_id": "999888"})
    assert res.success is True
    adapter._resolve_channel.assert_awaited_once_with("999888")
    mock_thread.get_partial_message.assert_called_once_with(123456)
    mock_msg.edit.assert_awaited_once_with(content="New text")


@pytest.mark.asyncio
async def test_bubble_cleanup_uses_source_chat_id_not_thread_id():
    """Cleanup of ephemeral bubbles routes deletion to source.chat_id (the container/supergroup), not thread_id."""
    from gateway.run_turn import TurnContext
    from gateway.run import GatewayRunner

    class MockSource:
        chat_id = "-1001234567890"  # Telegram supergroup
        thread_id = "77"             # Forum topic ID
        platform = MagicMock(value="telegram")

    turn_ctx = TurnContext(
        source=MockSource(),
        session_key="telegram:user:1",
        run_generation=1,
        _cleanup_progress=True,
    )
    turn_ctx._cleanup_msg_ids = ["msg-1", "msg-2"]

    registered_callbacks = []
    cleanup_adapter = MagicMock()
    cleanup_adapter.register_post_delivery_callback = MagicMock(
        side_effect=lambda key, cb, generation: registered_callbacks.append(cb)
    )
    cleanup_adapter.delete_message = AsyncMock(return_value=True)

    runner = GatewayRunner.__new__(GatewayRunner)
    runner._run_agent_schedule_bubble_cleanup(
        response={"final_response": "done"},
        _cleanup_adapter=cleanup_adapter,
        turn_ctx=turn_ctx,
    )

    assert len(registered_callbacks) == 1
    # Invoke the registered post delivery callback
    registered_callbacks[0]()
    # Allow scheduled tasks on the event loop to run
    await asyncio.sleep(0.05)

    assert cleanup_adapter.delete_message.await_count == 2
    # Verify that delete_message was called with source.chat_id ("-1001234567890"), NOT thread_id ("77")
    cleanup_adapter.delete_message.assert_any_await("-1001234567890", "msg-1")
    cleanup_adapter.delete_message.assert_any_await("-1001234567890", "msg-2")


