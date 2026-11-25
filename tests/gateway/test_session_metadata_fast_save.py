"""set_session_metadata must persist through the single-row UPSERT path.

Regression for the 2026-11-23 outage: every inbound gateway message stamped
session metadata through ``pre_gateway_dispatch`` -> ``set_session_metadata``
-> ``_update_entry`` -> ``_save()``, which rewrote the whole routing index
(DELETE + INSERT of ~28.8k rows plus a multi-MB sessions.json mirror) inside
the event loop. The loop stalled 10-40 s per message, Discord's heartbeat went
stale and Telegram stopped consuming updates.
"""
from __future__ import annotations

import threading

import hermes_state
from gateway.config import GatewayConfig, Platform
from gateway.session import SessionSource, SessionStore


def _source(user_id: str = "user-1") -> SessionSource:
    return SessionSource(
        platform=Platform.LOCAL,
        chat_id="cli",
        chat_name="CLI",
        chat_type="dm",
        user_id=user_id,
    )


def _make_store(tmp_path, monkeypatch) -> SessionStore:
    monkeypatch.setattr(hermes_state, "DEFAULT_DB_PATH", tmp_path / "state.db")
    import hermes_constants

    monkeypatch.setattr(hermes_constants, "get_hermes_home", lambda: str(tmp_path))
    return SessionStore(
        sessions_dir=tmp_path / "sessions",
        config=GatewayConfig(),
    )


def _count_saves(monkeypatch, store):
    calls = {"fast": 0, "full": 0}
    orig_fast, orig_full = store._save_entry, store._save

    def _fast(key, **kwargs):
        calls["fast"] += 1
        return orig_fast(key, **kwargs)

    def _full():
        calls["full"] += 1
        return orig_full()

    monkeypatch.setattr(store, "_save_entry", _fast)
    monkeypatch.setattr(store, "_save", _full)
    return calls


def test_set_session_metadata_never_rewrites_full_index(tmp_path, monkeypatch):
    store = _make_store(tmp_path, monkeypatch)
    entry = store.get_or_create_session(_source())
    calls = _count_saves(monkeypatch, store)

    assert store.set_session_metadata(entry.session_key, "reset_clock", "2026-11-23T12:00:00") is True

    assert calls["fast"] >= 1, "metadata write bypassed the single-row UPSERT"
    assert calls["full"] == 0, "metadata write triggered a full routing-index rewrite"
    store._db.close()


def test_set_session_metadata_is_durable_across_reload(tmp_path, monkeypatch):
    store = _make_store(tmp_path, monkeypatch)
    entry = store.get_or_create_session(_source())

    assert store.set_session_metadata(entry.session_key, "reset_clock", "2026-11-23T12:00:00") is True
    store._db.close()

    reloaded = _make_store(tmp_path, monkeypatch)
    assert reloaded.get_session_metadata(entry.session_key, "reset_clock") == "2026-11-23T12:00:00"
    reloaded._db.close()


def test_set_session_metadata_does_not_touch_activity_clock(tmp_path, monkeypatch):
    store = _make_store(tmp_path, monkeypatch)
    entry = store.get_or_create_session(_source())
    before = entry.updated_at

    assert store.set_session_metadata(entry.session_key, "reset_clock", "2026-11-23T12:00:00") is True
    assert entry.updated_at == before
    store._db.close()


def test_set_session_metadata_persists_under_the_mutation_lock(tmp_path, monkeypatch):
    """The snapshot and its routing generation must be captured atomically.

    ``_save_entry`` assigns the routing revision when it runs. If it runs after
    ``_lock`` is released, a concurrent scalar mutation (updated_at,
    active_turn_token, model_override) can be ordered before this write in
    memory but after it in the generation counter, so the older snapshot wins
    in state.db. Persisting under the mutation lock closes that window.
    """
    store = _make_store(tmp_path, monkeypatch)
    entry = store.get_or_create_session(_source())
    seen = {}
    orig = store._save_entry

    def _probe(key, **kwargs):
        seen["lock_held"] = kwargs.get("lock_held", False)
        seen["locked"] = store._lock.locked()
        return orig(key, **kwargs)

    monkeypatch.setattr(store, "_save_entry", _probe)
    assert store.set_session_metadata(entry.session_key, "reset_clock", "2026-11-23T12:00:00") is True

    assert seen["lock_held"] is True, "_save_entry must run with lock_held=True"
    assert seen["locked"] is True, "metadata was persisted outside the mutation lock"
    store._db.close()


def test_set_session_metadata_without_db_does_not_deadlock(tmp_path, monkeypatch):
    """No-DB (or failed-UPSERT) fallback must not re-acquire the non-reentrant mutation lock.

    ``_save_entries`` takes ``_lock``. Reaching it from ``_save_entry(lock_held=True)``
    deadlocks the gateway thread forever, which is worse than the stall being fixed.
    """
    store = _make_store(tmp_path, monkeypatch)
    entry = store.get_or_create_session(_source())
    db = store._db
    store._db = None  # force the fallback branch
    result: dict = {}

    def _run():
        result["ok"] = store.set_session_metadata(entry.session_key, "reset_clock", "2026-11-23T13:00:00")

    worker = threading.Thread(target=_run, daemon=True)
    worker.start()
    worker.join(10)
    assert not worker.is_alive(), "set_session_metadata deadlocked on the no-DB fallback"
    assert result.get("ok") is True
    if db is not None:
        db.close()


def test_other_update_entry_callers_keep_the_full_rewrite(tmp_path, monkeypatch):
    """fast=True is opt-in: structural / lane writes keep their current persistence."""
    store = _make_store(tmp_path, monkeypatch)
    entry = store.get_or_create_session(_source())
    calls = _count_saves(monkeypatch, store)

    assert store.set_session_yolo(entry.session_key, True) is True

    assert calls["full"] == 1, "non-metadata writes must keep the full routing rewrite"
    assert calls["fast"] == 0
    store._db.close()


def test_set_session_metadata_missing_entry_returns_false(tmp_path, monkeypatch):
    store = _make_store(tmp_path, monkeypatch)
    assert store.set_session_metadata("agent:main:local:nope", "k", "v") is False
    store._db.close()
