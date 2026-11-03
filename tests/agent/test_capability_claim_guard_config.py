"""T7 — config gate: profile-scoped flag, default OFF, per-turn options.

Contract (task T7 + review finding 3): ``is_enabled(agent)`` must answer for the
agent's OWN profile (served home), never for the launch/ambient config that a
multiplexed process happens to be sitting in. Default is OFF, so an absent or
unreadable config leaves the runtime byte-identical.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agent import capability_claim_guard as ccg
from hermes_constants import reset_hermes_home_override, set_hermes_home_override


def _write_home(home: Path, text: str) -> Path:
    home.mkdir(parents=True, exist_ok=True)
    (home / "config.yaml").write_text(text, encoding="utf-8")
    return home


class _Agent:
    """Agent double carrying only its owning-profile identity."""

    def __init__(self, home: Path | None = None) -> None:
        if home is not None:
            self._session_db = type("_DB", (), {"db_path": str(home / "state.db")})()
        self.tools = []
        self.valid_tool_names = set()


@pytest.fixture
def home_override():
    tokens = []

    def bind(path):
        tokens.append(set_hermes_home_override(str(path)))

    yield bind
    for token in reversed(tokens):
        reset_hermes_home_override(token)


def test_default_is_off_when_config_absent(tmp_path, home_override):
    launch = _write_home(tmp_path / "launch", "model: x\n")
    home_override(launch)
    assert ccg.is_enabled(_Agent(launch)) is False


def test_enabled_comes_from_the_agents_own_profile(tmp_path, home_override):
    served = _write_home(
        tmp_path / "served",
        "agent:\n  capability_claim_guard:\n    enabled: true\n",
    )
    launch = _write_home(tmp_path / "launch", "agent:\n  capability_claim_guard:\n    enabled: false\n")
    # The process sits in the launch profile; this agent serves another one.
    home_override(launch)
    assert ccg.is_enabled(_Agent(served)) is True


def test_concurrent_profiles_do_not_share_the_flag(tmp_path):
    on_home = _write_home(tmp_path / "on", "agent:\n  capability_claim_guard:\n    enabled: true\n")
    off_home = _write_home(tmp_path / "off", "agent:\n  capability_claim_guard:\n    enabled: false\n")
    assert ccg.is_enabled(_Agent(on_home)) is True
    assert ccg.is_enabled(_Agent(off_home)) is False


def test_unreadable_config_is_off(tmp_path, home_override):
    broken = tmp_path / "broken"
    broken.mkdir()
    (broken / "config.yaml").write_text("agent: [unclosed\n", encoding="utf-8")
    home_override(broken)
    assert ccg.is_enabled(_Agent(broken)) is False


def test_wire_turn_captures_per_turn_options_from_the_owning_profile(tmp_path, home_override):
    served = _write_home(
        tmp_path / "served",
        "agent:\n  capability_claim_guard:\n    enabled: true\n"
        "    holdback_chars: 64\n    repair_limit: 1\n",
    )
    home_override(served)
    agent = _Agent(served)
    ccg.wire_turn(agent, "turn-7")
    evidence = agent._ccg_evidence
    assert evidence is not None
    assert evidence.holdback_chars == 64
    assert evidence.repair_limit == 1
    assert evidence.profile_home == str(Path(served).resolve())


def test_wire_turn_resets_state_every_turn(tmp_path, home_override):
    served = _write_home(tmp_path / "served", "agent:\n  capability_claim_guard:\n    enabled: true\n")
    home_override(served)
    agent = _Agent(served)
    ccg.wire_turn(agent, "turn-1")
    agent._ccg_tainted = "turn-1"
    agent._ccg_repairs = 2
    agent._ccg_hold_parts = ["stale"]
    ccg.wire_turn(agent, "turn-2")
    assert agent._ccg_tainted is None
    assert agent._ccg_repairs == 0
    assert agent._ccg_hold_parts == []
    assert agent._ccg_evidence.turn_id == "turn-2"


def test_wire_turn_without_agent_home_uses_the_bound_scope(tmp_path, home_override):
    served = _write_home(tmp_path / "served", "agent:\n  capability_claim_guard:\n    enabled: true\n")
    home_override(served)
    agent = _Agent(home=None)
    ccg.wire_turn(agent, "turn-1")
    assert agent._ccg_evidence is not None


def test_edited_config_is_seen_on_the_next_turn(tmp_path, home_override):
    """No module cache: a config rewrite takes effect without a restart."""
    home = _write_home(tmp_path / "served", "agent:\n  capability_claim_guard:\n    enabled: false\n")
    home_override(home)
    agent = _Agent(home)
    assert ccg.is_enabled(agent) is False

    _write_home(
        home,
        "agent:\n  capability_claim_guard:\n    enabled: true\n    holdback_chars: 50\n",
    )
    assert ccg.is_enabled(agent) is True
