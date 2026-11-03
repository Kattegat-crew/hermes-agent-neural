"""T6 — S3 final seal + bounded repair round.

Contract (design §5-S3/§5.3, task T6):

* A contradiction in the final text with budget left injects ONE user-role repair
  nudge and re-enters the existing turn loop (role alternation preserved, history
  rows only, system prompt untouched).
* Budget exhausted (``repair_limit`` per turn) no longer nudges: the seal appends a
  truthful, evidence-bounded verification clause and never hides the model's claim.
* Everything is idempotent per ``turn_id`` and fail-open without an evidence snapshot.
"""

from __future__ import annotations

import pytest

from agent import turn_stop_gates
from agent.capability_claim_guard import CapabilityEvidence
from agent.turn_finalizer import apply_llm_output_transform

DENIAL = "No tengo herramientas de mensajería, así que no puedo enviar el mensaje."
CLEAN = "Revisé el repositorio y actualicé los dos archivos desactualizados."


class _FinalAgent:
    def __init__(self, evidence=None, *, repairs: int = 0, turn_id: str = "turn-1") -> None:
        self._ccg_evidence = evidence
        self._ccg_repairs = repairs
        self._ccg_repair_turn = turn_id
        self._current_turn_id = turn_id
        self._streamed_assistant_text_parts: list[str] = []
        self._session_messages = []
        self.session_id = "session-1"
        self.model = "model-1"
        self.provider = "provider-1"
        self.platform = "cli"

    def _strip_think_blocks(self, text):
        return text

    def _interim_content_was_streamed(self, text):
        return False


def _evidence(*names: str, repair_limit: int = 2) -> CapabilityEvidence:
    return CapabilityEvidence(
        turn_id="turn-1",
        direct=frozenset(names),
        repair_limit=repair_limit,
    )


def _run_gate(agent, text=DENIAL):
    final_msg = {"role": "assistant", "content": text}
    messages = [{"role": "user", "content": "envía el informe por mensajería"}, final_msg]
    verdict = turn_stop_gates.apply_stop_gates(
        agent,
        final_msg,
        final_response=text,
        messages=messages,
        conversation_history=[],
        pending_verification_response=None,
        pending_verification_response_previewed=False,
    )
    return verdict, final_msg, messages


@pytest.fixture
def other_gates_off(monkeypatch):
    monkeypatch.setattr(turn_stop_gates, "_verify_on_stop_nudge", lambda agent: None)
    monkeypatch.setattr(turn_stop_gates, "_pre_verify_nudge", lambda agent, text, attempt: None)
    monkeypatch.setattr(turn_stop_gates, "_kanban_stop_nudge", lambda agent, messages: None)


# ── Repair round ─────────────────────────────────────────────────────────


def test_contradiction_with_budget_continues_the_turn(other_gates_off):
    agent = _FinalAgent(_evidence("send_message"))
    verdict, final_msg, messages = _run_gate(agent)
    assert verdict.continue_turn is True
    assert verdict.final_response is None
    assert messages[-2] is final_msg  # the claim stays in history
    assert messages[-1]["role"] == "user"  # alternation holds
    assert final_msg["finish_reason"] == "capability_claim_repair"
    assert agent._ccg_repairs == 1


def test_repair_nudge_names_the_real_evidence_and_demands_verification(other_gates_off):
    agent = _FinalAgent(_evidence("send_message", "kanban_list"))
    _, _, messages = _run_gate(agent)
    nudge = messages[-1]["content"]
    assert "send_message" in nudge or "kanban_list" in nudge
    assert "tool_describe" in nudge
    assert "no anuncies" in nudge.lower() or "sin ejecutar" in nudge.lower()


def test_repair_counter_is_bounded_by_repair_limit(other_gates_off):
    agent = _FinalAgent(_evidence("send_message"), repairs=2)
    verdict, _, messages = _run_gate(agent)
    assert verdict.continue_turn is False
    assert messages[-1]["role"] == "assistant"
    assert agent._ccg_repairs == 2


def test_no_repair_for_clean_text(other_gates_off):
    agent = _FinalAgent(_evidence("send_message"))
    verdict, _, _ = _run_gate(agent, CLEAN)
    assert verdict.continue_turn is False
    assert agent._ccg_repairs == 0


def test_no_repair_when_disabled(other_gates_off):
    agent = _FinalAgent(evidence=None)
    verdict, _, _ = _run_gate(agent)
    assert verdict.continue_turn is False
    assert getattr(agent, "_ccg_repairs", 0) == 0


# ── Final seal ───────────────────────────────────────────────────────────


def test_seal_appends_truthful_clause_when_budget_is_spent():
    agent = _FinalAgent(_evidence("send_message"), repairs=2)
    text, transformed, pre = apply_llm_output_transform(agent, DENIAL, turn_id="turn-1")
    assert transformed is True
    assert pre == DENIAL
    assert text.startswith(DENIAL)  # the claim is never rewritten or hidden
    assert "Verificación" in text
    assert "send_message" in text


def test_seal_is_idempotent_per_turn():
    agent = _FinalAgent(_evidence("send_message"), repairs=2)
    first, _, _ = apply_llm_output_transform(agent, DENIAL, turn_id="turn-1")
    second, transformed, _ = apply_llm_output_transform(agent, first, turn_id="turn-1")
    assert second == first
    assert transformed is True


def test_seal_leaves_clean_text_untouched():
    agent = _FinalAgent(_evidence("send_message"), repairs=2)
    text, transformed, pre = apply_llm_output_transform(agent, CLEAN, turn_id="turn-1")
    assert (text, transformed, pre) == (CLEAN, False, None)


def test_seal_fails_open_without_evidence():
    agent = _FinalAgent(evidence=None)
    text, transformed, pre = apply_llm_output_transform(agent, DENIAL, turn_id="turn-1")
    assert (text, transformed, pre) == (DENIAL, False, None)


def test_seal_never_invents_unavailable_tools():
    agent = _FinalAgent(_evidence("send_message"), repairs=2)
    text, _, _ = apply_llm_output_transform(agent, DENIAL, turn_id="turn-1")
    assert "trello" not in text.lower()
    assert "jira" not in text.lower()
