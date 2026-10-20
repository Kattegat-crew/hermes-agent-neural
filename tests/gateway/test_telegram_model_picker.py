"""Tests for Telegram model picker thread fallback."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from gateway.config import PlatformConfig
from plugins.platforms.telegram.adapter import TelegramAdapter


def _make_adapter():
    adapter = TelegramAdapter(PlatformConfig(enabled=True, token="test-token"))
    adapter._bot = AsyncMock()
    adapter._app = MagicMock()
    return adapter


class TestTelegramModelPicker:
    @pytest.mark.asyncio
    async def test_send_model_picker_escapes_dynamic_provider_label(self):
        adapter = _make_adapter()
        sent = {}

        async def mock_send_message(**kwargs):
            sent.update(kwargs)
            return SimpleNamespace(message_id=101)

        adapter._bot.send_message = AsyncMock(side_effect=mock_send_message)

        result = await adapter.send_model_picker(
            chat_id="12345",
            providers=[
                {"slug": "provider_one", "name": "Provider One", "total_models": 1, "is_current": True}
            ],
            current_model="model_1",
            current_provider="provider_one",
            session_key="s",
            on_model_selected=AsyncMock(),
            metadata={"thread_id": "99999"},
        )

        assert result.success is True
        assert "MARKDOWN_V2" in repr(sent["parse_mode"])
        assert "provider\\_one" in sent["text"]
        assert "`model_1`" in sent["text"]

    @pytest.mark.asyncio
    async def test_back_button_escapes_dynamic_provider_label(self):
        adapter = _make_adapter()
        adapter._model_picker_state["12345"] = {
            "providers": [{"slug": "provider_one", "name": "Provider One", "total_models": 1, "is_current": True}],
            "current_model": "model_1",
            "current_provider": "provider_one",
            "session_key": "s",
            "on_model_selected": AsyncMock(),
            "msg_id": 42,
        }

        query = AsyncMock()
        query.data = "mb"
        query.message = MagicMock()
        query.message.chat_id = 12345
        query.from_user = MagicMock()
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()

        await adapter._handle_model_picker_callback(query, "mb", "12345")

        edit_kwargs = query.edit_message_text.call_args[1]
        assert "MARKDOWN_V2" in repr(edit_kwargs["parse_mode"])
        assert "provider\\_one" in edit_kwargs["text"]
        assert "`model_1`" in edit_kwargs["text"]


class TestProviderKeyboardCaseFolding:
    """group_providers() lowercases slugs; the keyboard must still resolve
    user-defined providers whose config key keeps its original case
    (NaN-Builders, B.AI) — regression for the 2026-10-01 picker outage.
    The session conftest mocks the whole ``telegram`` package, so button
    attributes are unreadable MagicMocks; stub the two keyboard classes
    with real lightweight stand-ins to inspect callback_data.
    """

    class _Btn:
        def __init__(self, text, callback_data=None):
            self.text = text
            self.callback_data = callback_data

    class _Markup:
        def __init__(self, rows):
            self.inline_keyboard = rows

    _PROVIDERS = [
        {"slug": "moa", "name": "Mixture of Agents", "total_models": 4, "models": ["a"]},
        {"slug": "NaN-Builders", "name": "NaN-Builders", "total_models": 13, "models": ["glm5.3-flash"]},
        {"slug": "nous", "name": "Nous Portal", "total_models": 56, "models": ["a"]},
        {"slug": "opencode-zen", "name": "OpenCode Zen", "total_models": 21, "models": ["a"]},
        {"slug": "opencode-go", "name": "OpenCode Go", "total_models": 43, "models": ["a"]},
        {"slug": "openai-codex", "name": "ChatGPT or Codex Subscription", "total_models": 9, "models": ["a"]},
        {"slug": "opencode-free", "name": "OpenCode Free", "total_models": 3, "models": ["a"]},
        {"slug": "B.AI", "name": "B.AI", "total_models": 2, "models": ["a"]},
    ]

    def _keyboard_callbacks(self, providers, page=0):
        import plugins.platforms.telegram.adapter as m

        real_btn, real_markup = m.InlineKeyboardButton, m.InlineKeyboardMarkup
        m.InlineKeyboardButton = self._Btn
        m.InlineKeyboardMarkup = self._Markup
        try:
            adapter = _make_adapter()
            keyboard, _ = adapter._build_provider_keyboard(list(providers), page)
        finally:
            m.InlineKeyboardButton = real_btn
            m.InlineKeyboardMarkup = real_markup
        return [b.callback_data for row in keyboard.inline_keyboard for b in row]

    def test_mixed_case_user_defined_providers_get_buttons(self):
        callbacks = self._keyboard_callbacks(self._PROVIDERS)
        assert "mp:NaN-Builders" in callbacks
        assert "mp:B.AI" in callbacks

    def test_group_rows_resolve_lowercase_members_with_raw_slugs(self):
        callbacks = self._keyboard_callbacks(self._PROVIDERS)
        assert "mpg:opencode" in callbacks
        assert "mp:opencode-go" not in callbacks  # folded into the group
        assert "mp:opencode-zen" not in callbacks
        assert "mp:opencode-free" in callbacks  # not a group member: stays single

    def test_group_drill_callback_resolves_mixed_case_members(self):
        # PROVIDER_GROUPS members are lowercase-declared; state providers may
        # keep raw case. The mpg: drill lookup must be case-insensitive too.
        import plugins.platforms.telegram.adapter as m

        from hermes_cli.models_catalog_static import PROVIDER_GROUPS
        assert "opencode-go" in {s for g in PROVIDER_GROUPS.values() for s in g[2]}
        state = {
            "providers": [
                {"slug": "OpenCode-Go", "name": "OpenCode Go", "total_models": 43, "models": ["a"]},
                {"slug": "opencode-free", "name": "OpenCode Free", "total_models": 3, "models": ["a"]},
            ],
            "current_model": "x", "current_provider": "", "session_key": "s",
            "on_model_selected": AsyncMock(), "msg_id": 1,
        }
        adapter = _make_adapter()
        adapter._model_picker_state["1"] = state
        real_btn, real_markup = m.InlineKeyboardButton, m.InlineKeyboardMarkup
        m.InlineKeyboardButton = self._Btn
        m.InlineKeyboardMarkup = self._Markup
        try:
            query = AsyncMock()
            query.data = "mpg:opencode"
            query.answer = AsyncMock()
            query.edit_message_text = AsyncMock()
            import asyncio
            asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
                adapter._handle_model_picker_callback(query, "mpg:opencode", "1")
            )
            kb = query.edit_message_text.call_args[1]["reply_markup"]
        finally:
            m.InlineKeyboardButton = real_btn
            m.InlineKeyboardMarkup = real_markup
        callbacks = [b.callback_data for row in kb.inline_keyboard for b in row]
        assert "mp:OpenCode-Go" in callbacks


def _gateway_wired_adapter():
    """Real adapter with the real gateway auth callback, as ``GatewayRunner`` wires it."""
    from gateway.config import GatewayConfig, Platform
    from gateway.pairing import PairingStore
    from gateway.run import GatewayRunner

    runner = object.__new__(GatewayRunner)
    runner.config = GatewayConfig()
    runner.config.platforms = {Platform.TELEGRAM: PlatformConfig(enabled=True, extra={})}
    runner.pairing_store = PairingStore(profile="default")
    runner.pairing_stores = {"default": runner.pairing_store}
    runner._primary_profile_name = "default"
    adapter = _make_adapter()
    runner.adapters = {Platform.TELEGRAM: adapter}
    adapter.set_authorization_check(runner._make_adapter_auth_check(Platform.TELEGRAM))
    return adapter


@pytest.mark.asyncio
@pytest.mark.parametrize("tapper_id, switches", [("222", False), ("111", True)])
async def test_group_model_picker_switch_follows_callback_allowlist(monkeypatch, tapper_id, switches):
    """Only an allowlisted tapper can switch the model from a group /model picker."""
    for key in ("GATEWAY_ALLOW_ALL_USERS", "GATEWAY_ALLOWED_USERS", "TELEGRAM_ALLOW_ALL_USERS",
                "TELEGRAM_GROUP_ALLOWED_USERS", "TELEGRAM_GROUP_ALLOWED_CHATS"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("TELEGRAM_ALLOWED_USERS", "111")
    import hermes_cli.model_selection_guards as guards
    monkeypatch.setattr(guards, "combined_selection_warning", lambda *a, **k: None)

    adapter = _gateway_wired_adapter()
    on_model_selected = AsyncMock(return_value="Switched to `other-model`")
    adapter._model_picker_state["-100777"] = {
        "providers": [{"slug": "openai", "name": "OpenAI", "total_models": 1}],
        "current_model": "owner-model",
        "current_provider": "openai",
        "session_key": "s",
        "on_model_selected": on_model_selected,
        "selected_provider": "openai",
        "model_list": ["other-model"],
        "msg_id": 42,
    }
    query = SimpleNamespace(
        data="mm:0",
        message=SimpleNamespace(
            chat_id=-100777, chat=SimpleNamespace(type="supergroup"), message_thread_id=None
        ),
        from_user=SimpleNamespace(id=int(tapper_id), first_name="Tapper"),
        answer=AsyncMock(),
        edit_message_text=AsyncMock(),
    )

    await adapter._handle_callback_query(SimpleNamespace(callback_query=query), MagicMock())

    assert on_model_selected.await_count == (1 if switches else 0)
    assert ("-100777" in adapter._model_picker_state) is not switches


