"""Regression coverage for the 2026-09-30 Telegram edit-flood livelock.

Root cause (bitacora brain/ops/incidente-telegram-livelock-2026-09-30.md):
parallel-delegation progress edits saturated the bot-wide rate limit; the
edit path slept the full server `retry_after` inline, and the post-wait
retry classified `BadRequest: Message is not modified` as a hard failure.
The streaming loop kept re-issuing identical edits at ~5/s, each 429
re-extending the punishment (764s -> 6563s) for ~11 hours.

Protections asserted here:
1. `retry_after > _FLOOD_ABANDON_WAIT_SECS` on a progress edit is abandoned
   immediately (never slept, never re-fired) and opens a per-chat cooldown.
2. A post-flood-wait retry that answers "message is not modified" is an
   idempotent success, not a failure.
3. Consecutive short flood waits trip the same per-chat cooldown so a storm
   cannot keep burning flood budget.
4. While a chat is in edit-cooldown, further progress edits are skipped
   locally at zero API cost.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram.error import BadRequest, RetryAfter

from gateway.config import PlatformConfig
from plugins.platforms.telegram.adapter import (
    _FLOOD_ABANDON_WAIT_SECS,
    _FLOOD_EDIT_COOLDOWN_SECS,
    _FLOOD_EDIT_FAILURE_LIMIT,
    TelegramAdapter,
)


@pytest.fixture
def telegram_adapter() -> TelegramAdapter:
    adapter = TelegramAdapter(PlatformConfig(enabled=True, token="fake-token"))
    adapter._bot = MagicMock()
    return adapter


def _flood(wait: float) -> RetryAfter:
    err = RetryAfter(int(wait))
    err.args = (f"Too Many Requests: retry after {int(wait)}",)
    return err


@pytest.mark.asyncio
async def test_long_flood_wait_on_progress_edit_is_abandoned_not_slept(telegram_adapter):
    """retry_after >> cap: fail closed without any inline sleep (D-fix #3)."""
    telegram_adapter._bot.edit_message_text = AsyncMock(side_effect=_flood(764.0))

    result = await telegram_adapter.edit_message("123", "456", "progress update")

    assert result.success is False
    assert "flood_control" in (result.error or "")
    assert (result.retry_after or 0) >= _FLOOD_ABANDON_WAIT_SECS
    # exactly one API call: no inline sleep + retry on a 764s penalty
    assert telegram_adapter._bot.edit_message_text.await_count == 1


@pytest.mark.asyncio
async def test_not_modified_after_flood_wait_is_idempotent_success(telegram_adapter):
    """The storm driver: a 4s wait, then identical content -> not modified."""
    telegram_adapter._bot.edit_message_text = AsyncMock(
        side_effect=[_flood(4.0), BadRequest("Message is not modified")]
    )

    result = await telegram_adapter.edit_message("123", "456", "progress update")

    assert result.success is True
    assert result.message_id == "456"


@pytest.mark.asyncio
async def test_short_flood_storm_opens_chat_cooldown_and_skips_further_edits(telegram_adapter):
    """N consecutive short flood waits -> cooldown; next edit costs 0 API calls."""
    telegram_adapter._bot.edit_message_text = AsyncMock(side_effect=_flood(4.0))

    results = []
    for i in range(_FLOOD_EDIT_FAILURE_LIMIT + 1):
        results.append(
            await telegram_adapter.edit_message("123", "456", f"progress {i}")
        )

    # capped storm: API calls never exceed the failure limit
    assert telegram_adapter._bot.edit_message_text.await_count <= _FLOOD_EDIT_FAILURE_LIMIT
    last = results[-1]
    assert last.success is True  # skipped locally, treated as visual no-op
    assert "cooldown" in (last.raw_response or {}).get("skipped_reason", "")

    # a genuinely different chat is unaffected
    telegram_adapter._bot.edit_message_text = AsyncMock(return_value=True)
    other = await telegram_adapter.edit_message("999", "456", "progress update")
    assert other.success is True
    assert telegram_adapter._bot.edit_message_text.await_count == 1


@pytest.mark.asyncio
async def test_finalize_edit_still_delivers_despite_chat_cooldown(telegram_adapter):
    """Cooldown suppresses PROGRESS edits only; final delivery must go through."""
    telegram_adapter._bot.edit_message_text = AsyncMock(side_effect=_flood(4.0))
    for i in range(_FLOOD_EDIT_FAILURE_LIMIT + 1):
        await telegram_adapter.edit_message("123", "456", f"progress {i}")
    # cooldown must be engaged by now (a skipped edit costs zero API calls)
    assert telegram_adapter._edit_flood_cooldown_active("123")
    assert telegram_adapter._bot.edit_message_text.await_count <= _FLOOD_EDIT_FAILURE_LIMIT

    telegram_adapter._bot.edit_message_text = AsyncMock(return_value=True)
    result = await telegram_adapter.edit_message("123", "456", "FINAL answer", finalize=True)

    assert result.success is True
    assert telegram_adapter._bot.edit_message_text.await_count == 1


@pytest.mark.asyncio
async def test_flood_cooldown_expires(telegram_adapter, monkeypatch):
    """The cooldown is a rate brake, not a permanent kill switch."""
    telegram_adapter._bot.edit_message_text = AsyncMock(side_effect=_flood(4.0))
    for i in range(_FLOOD_EDIT_FAILURE_LIMIT + 1):
        await telegram_adapter.edit_message("123", "456", f"progress {i}")

    import plugins.platforms.telegram.adapter as mod

    real_monotonic = mod.time.monotonic
    monkeypatch.setattr(
        mod.time, "monotonic",
        lambda: real_monotonic() + mod._FLOOD_EDIT_COOLDOWN_SECS + 1,
    )
    telegram_adapter._bot.edit_message_text = AsyncMock(return_value=True)
    result = await telegram_adapter.edit_message("123", "456", "progress after expiry")
    assert result.success is True
    assert telegram_adapter._bot.edit_message_text.await_count == 1
