"""Presence: el cliente debe anunciarse ONLINE al conectar.

Regresión del cambio en ``DiscordAdapter.connect``: sin el ``status`` explícito
el bot hereda el estado por defecto de discord.py (offline/idle hasta el primer
opcode), así que los humanos ven el bot apagado mientras ya responde.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from gateway.config import PlatformConfig
import plugins.platforms.discord.adapter as discord_platform
from plugins.platforms.discord.adapter import DiscordAdapter

ONLINE = "online-marker"


class _Tree:
    def __init__(self):
        self.sync = AsyncMock(return_value=[])

    def command(self, *args, **kwargs):
        return lambda fn: fn

    def get_commands(self):
        return []


class _Bot:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self._events = {}
        self.tree = _Tree()
        self.application_id = 1
        self.user = SimpleNamespace(id=1, name="Hermes")
        self.change_presence = AsyncMock()

    def event(self, fn):
        self._events[fn.__name__] = fn
        return fn

    def is_closed(self):
        return False

    async def start(self, token):
        await self._events["on_ready"]()

    async def close(self):
        return None


@pytest.mark.asyncio
async def test_connect_announces_online_presence(monkeypatch):
    """El Bot se construye con status online y on_ready lo reafirma."""
    monkeypatch.setattr(
        discord_platform.discord,
        "Status",
        SimpleNamespace(online=ONLINE),
    )
    adapter = DiscordAdapter(PlatformConfig(enabled=True, token="test-token"))

    monkeypatch.setattr(
        "gateway.status.acquire_scoped_lock", lambda *a, **k: (True, None)
    )
    monkeypatch.setattr(
        "gateway.status_scoped_locks.release_scoped_lock", lambda *a, **k: None
    )
    monkeypatch.setattr(
        discord_platform.Intents,
        "default",
        lambda: SimpleNamespace(
            message_content=False,
            dm_messages=False,
            guild_messages=False,
            members=False,
            voice_states=False,
        ),
    )

    created = []

    def factory(**kwargs):
        bot = _Bot(**kwargs)
        created.append(bot)
        return bot

    monkeypatch.setattr(discord_platform.commands, "Bot", factory)
    monkeypatch.setattr(adapter, "_resolve_allowed_usernames", AsyncMock())

    assert await adapter.connect() is True
    assert len(created) == 1
    bot = created[0]

    assert bot.kwargs.get("status") == ONLINE, (
        "el cliente debe nacer online; sin status el bot aparece apagado "
        "mientras ya responde mensajes"
    )
    assert bot.change_presence.await_count == 1, (
        "on_ready debe reafirmar la presencia: discord.py puede resetearla "
        "tras una reconexión del gateway"
    )
    assert bot.change_presence.await_args.kwargs.get("status") == ONLINE
