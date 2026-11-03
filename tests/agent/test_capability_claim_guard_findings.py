"""Review findings 1, 2 and 4 — authenticated tool outcomes, registry aliases,
multi-family resolution.

* F1: ``record_tool_outcome`` only trusts a STRUCTURED failure envelope produced by
  the dispatcher (``success: false`` / non-zero ``exit_code`` / approval denial).
  Text scraped from a page or typed by a user can never mint an "observed error".
* F2: aliases come from the live registry and expand alias → toolset → tools.
* F4: "tareas y mensajería" resolves BOTH families; a bare denial is bounded and
  never points at an unrelated tool; an unresolvable object stays fail-open.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from agent import capability_claim_guard as ccg
from agent.capability_claim_guard import CapabilityEvidence, capture_evidence, scan_published_text
from tools.registry import registry


def _tool_def(name: str) -> dict:
    return {"type": "function", "function": {"name": name, "parameters": {}}}


def _agent(*names: str):
    agent = SimpleNamespace()
    agent.tools = [_tool_def(n) for n in names]
    agent.valid_tool_names = set(names)
    return agent


def _evidence(*names: str) -> CapabilityEvidence:
    return CapabilityEvidence(turn_id="turn-1", direct=frozenset(names))


# ── F1: authenticated observed errors ────────────────────────────────────


def test_structured_failure_envelope_is_recorded():
    agent = _agent("send_message")
    agent._ccg_evidence = _evidence("send_message")
    ccg.record_tool_outcome(
        agent, "send_message", json.dumps({"success": False, "error": "rate limited"}), is_error=True, blocked=False,
    )
    assert "send_message" in agent._ccg_evidence.observed_errors


def test_dict_failure_envelope_is_recorded():
    agent = _agent("send_message")
    agent._ccg_evidence = _evidence("send_message")
    ccg.record_tool_outcome(agent, "send_message", {"success": False, "error": "boom"}, is_error=True, blocked=False)
    assert "send_message" in agent._ccg_evidence.observed_errors


def test_terminal_non_zero_exit_is_recorded():
    agent = _agent("terminal")
    agent._ccg_evidence = _evidence("terminal")
    ccg.record_tool_outcome(agent, "terminal", {"exit_code": 2, "output": ""}, is_error=True, blocked=False)
    assert "terminal" in agent._ccg_evidence.observed_errors


def test_scraped_text_that_looks_like_an_error_is_not_trusted():
    agent = _agent("web_extract")
    agent._ccg_evidence = _evidence("web_extract")
    page = json.dumps({"success": True, "content": 'the page says "error" and Error: nothing works'})
    ccg.record_tool_outcome(agent, "web_extract", page, is_error=True, blocked=False)
    assert agent._ccg_evidence.observed_errors == {}


def test_raw_error_text_is_not_trusted():
    agent = _agent("web_extract")
    agent._ccg_evidence = _evidence("web_extract")
    ccg.record_tool_outcome(agent, "web_extract", "Error: user typed something", is_error=True, blocked=False)
    assert agent._ccg_evidence.observed_errors == {}


def test_approval_denial_is_recorded_as_blocked():
    agent = _agent("send_message")
    agent._ccg_evidence = _evidence("send_message")
    ccg.record_tool_outcome(agent, "send_message", None, is_error=False, blocked=True)
    assert agent._ccg_evidence.observed_errors["send_message"] == "blocked"


def test_success_is_not_recorded():
    agent = _agent("send_message")
    agent._ccg_evidence = _evidence("send_message")
    ccg.record_tool_outcome(agent, "send_message", {"success": True}, is_error=False, blocked=False)
    assert agent._ccg_evidence.observed_errors == {}


def test_record_without_snapshot_is_a_noop():
    ccg.record_tool_outcome(_agent("send_message"), "send_message", {"success": False}, is_error=True, blocked=False)


def test_observed_failure_makes_the_denial_truthful():
    agent = _agent("send_message")
    agent._ccg_evidence = _evidence("send_message")
    ccg.record_tool_outcome(
        agent, "send_message", json.dumps({"success": False, "error": "denied"}), is_error=True, blocked=False,
    )
    verdict = scan_published_text(agent._ccg_evidence, "No puedo enviar mensajes: la herramienta falló.")
    assert verdict.kind == "allowed_observed_error"


# ── F2: registry aliases ─────────────────────────────────────────────────


@pytest.fixture
def fake_alias_registry(monkeypatch):
    monkeypatch.setattr(
        registry, "get_registered_toolset_aliases", lambda: {"kb": "kanban", "msg": "messaging"}, raising=False,
    )
    monkeypatch.setattr(
        registry, "get_toolset_for_tool",
        lambda name: "kanban" if name.startswith("kanban") else ("messaging" if "message" in name else None),
        raising=False,
    )


def test_aliases_expand_toolset_to_its_tools(fake_alias_registry):
    evidence = capture_evidence(_agent("kanban_list", "send_message"), "turn-1")
    assert evidence.aliases["kb"] == frozenset({"kanban_list"})
    assert evidence.aliases["msg"] == frozenset({"send_message"})


def test_alias_reference_resolves_through_the_toolset(fake_alias_registry):
    evidence = capture_evidence(_agent("kanban_list", "send_message"), "turn-1")
    verdict = scan_published_text(evidence, "No tengo la herramienta kb para ver pendientes.")
    assert verdict.kind == "contradiction_direct"
    assert verdict.tools == ("kanban_list",)


def test_alias_never_mentions_a_tool_outside_the_snapshot(fake_alias_registry):
    evidence = capture_evidence(_agent("kanban_list"), "turn-1")
    assert set(evidence.aliases) == {"kb"}


# ── F4: multi-family + bounded bare denials ──────────────────────────────


def test_both_named_families_are_resolved():
    evidence = _evidence("kanban_list", "send_message")
    verdict = scan_published_text(
        evidence, "No tengo herramientas para tareas ni para mensajería en esta sesión."
    )
    assert set(verdict.tools) == {"kanban_list", "send_message"}


def test_bare_denial_is_bounded_and_still_contradicted():
    names = {f"tool_{i:02d}" for i in range(40)}
    verdict = scan_published_text(_evidence(*names), "No tengo herramientas en esta sesión.")
    assert verdict.kind == "contradiction_direct"
    assert len(verdict.tools) <= 5
    assert set(verdict.tools) <= names


def test_unresolvable_object_stays_fail_open():
    evidence = _evidence("send_message", "kanban_list")
    verdict = scan_published_text(evidence, "No tengo herramientas para convertir PDFs a braille.")
    assert verdict.kind == "allowed_absent"
    assert verdict.tools == ()


def test_resolved_family_does_not_drag_in_unrelated_tools():
    evidence = _evidence("send_message", "kanban_list", "terminal")
    verdict = scan_published_text(evidence, "No tengo herramientas de mensajería para avisar.")
    assert verdict.tools == ("send_message",)


# ── F1 wiring: the dispatcher seam itself ────────────────────────────────


def test_dispatcher_seam_records_only_authenticated_failures():
    """The seam ``_commit_tool_result`` calls (finding 1) honours the envelope rule."""
    from agent.tool_executor import _ccg_record_outcome

    agent = _agent("terminal")
    agent._ccg_evidence = _evidence("terminal")
    _ccg_record_outcome(agent, "terminal", {"success": True, "exit_code": 0}, is_error=False, blocked=False)
    assert agent._ccg_evidence.observed_errors == {}
    _ccg_record_outcome(agent, "terminal", {"success": False, "exit_code": 1}, is_error=True, blocked=False)
    assert agent._ccg_evidence.observed_errors["terminal"] == "error"


def test_dispatcher_seam_is_a_noop_while_disabled():
    from agent.tool_executor import _ccg_record_outcome

    agent = _agent("terminal")
    agent._ccg_evidence = None
    _ccg_record_outcome(agent, "terminal", {"success": False}, is_error=True, blocked=False)
    assert getattr(agent, "_ccg_evidence", None) is None
