"""Listener `threadUpdate` del tablero de tickets: filtrado + ráfaga + corrida."""

from __future__ import annotations

import importlib.util
import subprocess
import threading
import time
from pathlib import Path

_PLUGIN = (Path(__file__).resolve().parents[2] / "plugins" / "ticket-board-sync"
           / "__init__.py")


def _load():
    """Fresh module per test — the listener keeps fire state in module globals."""
    spec = importlib.util.spec_from_file_location("ticket_board_sync_under_test", _PLUGIN)
    assert spec and spec.loader, "no se encontró plugins/ticket-board-sync/__init__.py"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    setattr(mod, "DEBOUNCE_S", 0.05)
    return mod


def _payload(parent: str | None = "1554957746980261938",
             old: tuple = ("1",), new: tuple = ("2",)):
    return {"parent_chat_id": parent, "old_tags": list(old), "new_tags": list(new)}


class TestShouldSync:
    def test_tag_change_in_ticket_forum(self):
        mod = _load()
        assert mod.should_sync("thread_tags_changed", _payload()) is True

    def test_ignores_other_event_types(self):
        mod = _load()
        assert mod.should_sync("thread_renamed", _payload()) is False
        assert mod.should_sync("message_edited", _payload()) is False
        assert mod.should_sync(None, None) is False

    def test_ignores_other_forums(self):
        mod = _load()
        assert mod.should_sync("thread_tags_changed",
                               _payload(parent="1234567890")) is False
        assert mod.should_sync("thread_tags_changed", _payload(parent=None)) is False

    def test_ignores_identical_tags(self):
        mod = _load()
        assert mod.should_sync(
            "thread_tags_changed", _payload(old=("1",), new=("1",))) is False
        # misma lista, distinto orden, sí es un cambio
        assert mod.should_sync(
            "thread_tags_changed", _payload(old=("1", "2"), new=("2", "1"))) is True


class TestDispatch:
    def test_fires_the_regenerador_once_per_flood(self, monkeypatch):
        mod = _load()
        corridas: list[list[str]] = []
        llego = threading.Event()

        def _fake(argv, **kwargs):
            corridas.append(argv)
            llego.set()
            return subprocess.CompletedProcess(argv, 0, stdout="{}", stderr="")

        monkeypatch.setattr(mod.subprocess, "run", _fake)

        for _ in range(5):
            mod._on_platform_event(platform="discord",
                                   event_type="thread_tags_changed",
                                   payload=_payload())
        assert llego.wait(3.0), "el listener no disparó"
        time.sleep(0.25)

        assert corridas == [["python3", mod.SCRIPT, "--publish"]]

    def test_wrong_forum_never_spawns(self, monkeypatch):
        mod = _load()
        llamadas = []
        monkeypatch.setattr(mod.subprocess, "run",
                            lambda *a, **k: llamadas.append(a))
        mod._on_platform_event(platform="discord", event_type="thread_tags_changed",
                               payload=_payload(parent="999"))
        time.sleep(0.2)
        assert llamadas == []

    def test_regenerator_failure_is_contained(self, monkeypatch):
        """A crashing regenerador must not raise into the adapter loop."""
        mod = _load()
        monkeypatch.setattr(
            mod.subprocess, "run",
            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
        mod._on_platform_event(platform="discord", event_type="thread_tags_changed",
                               payload=_payload())
        time.sleep(0.3)
        assert mod._state["running"] is False

    def test_registers_the_expected_hook(self):
        mod = _load()

        class _Ctx:
            def __init__(self):
                self.hooks = {}

            def register_hook(self, name, fn):
                self.hooks[name] = fn

        ctx = _Ctx()
        mod.register(ctx)
        assert list(ctx.hooks) == ["gateway_platform_event"]
        assert ctx.hooks["gateway_platform_event"] is mod._on_platform_event
