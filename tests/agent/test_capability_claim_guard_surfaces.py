"""T4–T7 cross-surface matrix: the paths the single-seam tests do not cover.

Each test pins one surface the guard must survive without changing it:

* Codex commentary items (``phase=commentary``) reach S2 before publication.
* The suppressed-text route of a tool-call turn is a real publication path and obeys S1.
* A retry that supersedes a stream must not flush the stale attempt's held tail.
* A subagent without its own snapshot is fail-open even when the parent is enabled.
* Two profiles' agents interleaved in one process keep independent gate state.
* The guard never touches history: seal/repair only return text or add a nudge row.
"""

from __future__ import annotations

from agent.capability_claim_guard import CapabilityEvidence
from agent.chat_completion_helpers import _StreamingCall
from agent.stream_delivery import StreamDeliveryMixin

DENIAL = "No tengo herramientas de mensajería, así que no puedo enviar el mensaje."
BENIGN = "Revisé el repositorio y actualicé los dos archivos desactualizados. "


class _Sink:
    def __init__(self) -> None:
        self.parts: list[str] = []

    def __call__(self, text: str) -> None:
        self.parts.append(text)

    @property
    def text(self) -> str:
        return "".join(self.parts)


class _CodexAgent(StreamDeliveryMixin):
    def __init__(self, evidence=None, *, superseded: bool = False) -> None:
        self.interim_assistant_callback = _InterimSink()
        self.stream_delta_callback = _Sink()
        self._stream_callback = None
        self._ccg_evidence = evidence
        self._streamed_assistant_text_parts: list[str] = []
        self._delivered_interim_texts: set[str] = set()
        self._current_turn_id = "turn-1"
        self.show_commentary = True
        self.provider = "codex"
        self._superseded = superseded

    def _stream_writer_superseded(self) -> bool:
        return self._superseded

    def _strip_think_blocks(self, text):
        return text

    def _visible_commentary(self, text):
        return text


class _InterimSink:
    def __init__(self) -> None:
        self.calls: list[tuple[str, bool]] = []

    def __call__(self, text: str, *, already_streamed: bool = False) -> None:
        self.calls.append((text, already_streamed))


class _SuppressedCall:
    """The parts of ``_StreamingCall`` that ``_route_suppressed_text`` touches."""

    def __init__(self, agent) -> None:
        self.agent = agent

    def _quiet(self, fn):
        return fn()


def _evidence(*names: str, holdback: int = 200, turn_id: str = "turn-1") -> CapabilityEvidence:
    return CapabilityEvidence(
        turn_id=turn_id, direct=frozenset(names), holdback_chars=holdback, repair_limit=2
    )


# ── Codex commentary reaches S2 before publication ───────────────────────


def test_codex_commentary_denial_is_suppressed_before_the_callback():
    agent = _CodexAgent(_evidence("send_message"))
    agent._emit_interim_assistant_message(
        {
            "role": "assistant",
            "codex_message_items": [
                {
                    "type": "message",
                    "phase": "commentary",
                    "content": [{"type": "output_text", "text": DENIAL}],
                }
            ],
        }
    )
    assert agent.interim_assistant_callback.calls == []
    assert agent._ccg_tainted == "turn-1"


def test_codex_commentary_clean_text_is_delivered():
    agent = _CodexAgent(_evidence("send_message"))
    agent._emit_interim_assistant_message(
        {
            "role": "assistant",
            "codex_message_items": [
                {
                    "type": "message",
                    "phase": "commentary",
                    "content": [{"type": "output_text", "text": BENIGN.strip()}],
                }
            ],
        }
    )
    assert [c[0] for c in agent.interim_assistant_callback.calls] == [BENIGN.strip()]


# ── Tool-call turns: the suppressed-text route is gated too ──────────────


def test_suppressed_text_route_is_held_back_before_publication():
    agent = _CodexAgent(_evidence("send_message"))
    call = _SuppressedCall(agent)
    _StreamingCall._route_suppressed_text(call, BENIGN)
    assert agent.stream_delta_callback.text == ""  # inside the holdback window
    agent._ccg_stream_flush()
    assert agent.stream_delta_callback.text == BENIGN


def test_suppressed_text_route_never_publishes_a_denial():
    agent = _CodexAgent(_evidence("send_message"))
    call = _SuppressedCall(agent)
    for chunk in [BENIGN * 6, DENIAL]:
        _StreamingCall._route_suppressed_text(call, chunk)
    agent._ccg_stream_flush()
    assert "No tengo" not in agent.stream_delta_callback.text
    assert agent._ccg_tainted == "turn-1"


def test_suppressed_text_route_is_untouched_while_disabled():
    agent = _CodexAgent(None)
    call = _SuppressedCall(agent)
    _StreamingCall._route_suppressed_text(call, BENIGN)
    assert agent.stream_delta_callback.text == BENIGN


# ── Turn retry: a superseded stream never flushes its held tail ──────────


def test_superseded_stream_drops_its_holdback_on_flush():
    agent = _CodexAgent(_evidence("send_message"))
    agent._fire_stream_delta("Respuesta a medias de un intento que será reintentado. ")
    assert agent.stream_delta_callback.text == ""
    agent._superseded = True
    agent._ccg_stream_flush()
    assert agent.stream_delta_callback.text == ""
    assert agent._ccg_hold_parts == []


# ── Subagents: no snapshot, no gate ─────────────────────────────────────


def test_child_agent_without_snapshot_is_fail_open_while_parent_is_enabled():
    parent = _CodexAgent(_evidence("send_message"))
    child = _CodexAgent(None)  # subagents run their own turn/evidence
    child._fire_stream_delta(DENIAL)
    assert child.stream_delta_callback.text == DENIAL
    assert parent.stream_delta_callback.text == ""


# ── Two profiles interleaved in one process ─────────────────────────────


def test_two_profiles_do_not_share_gate_state():
    home_a = _CodexAgent(_evidence("send_message", holdback=40, turn_id="a-1"))
    home_b = _CodexAgent(_evidence("kanban_list", holdback=40, turn_id="b-1"))
    denial_kanban = "No tengo herramientas de kanban para crear la tarjeta."
    parts = ["Revisé el repositorio y ", "actualicé los dos archivos. ", denial_kanban, " luego sigo."]
    for part in parts:
        # A has no kanban tool (allowed); B has kanban_list (contradiction).
        home_a._fire_stream_delta(part)
        home_b._fire_stream_delta(part)
    home_a._ccg_stream_flush()
    home_b._ccg_stream_flush()
    assert home_a._ccg_tainted is None
    assert home_a.stream_delta_callback.text == "".join(parts)
    # B stops publishing before the denial is complete: nothing of it reaches the surface.
    assert home_b._ccg_tainted == "b-1"
    assert "No tengo" not in home_b.stream_delta_callback.text
    assert home_a._ccg_evidence is not home_b._ccg_evidence


def test_denial_straddling_the_holdback_boundary_is_never_half_published():
    agent = _CodexAgent(_evidence("kanban_list", holdback=40))
    for part in ["Revisé el repositorio y ", "actualicé los dos archivos. ", "No tengo herramientas de ", "kanban para crear la tarjeta."]:
        released = agent._ccg_stream_gate(part)
        # Whatever is published is clean: no half sentence, no retraction.
        assert "No tengo" not in agent.stream_delta_callback.text
        assert "No tengo" not in released
    agent._ccg_stream_flush()
    assert agent._ccg_tainted == "turn-1"
    assert "No tengo" not in agent.stream_delta_callback.text


def test_one_profile_tainted_does_not_silence_the_other():
    tainted = _CodexAgent(_evidence("send_message", holdback=40))
    clean = _CodexAgent(_evidence("send_message", holdback=40))
    raw = BENIGN * 4 + DENIAL
    for chunk in [raw[i:i + 20] for i in range(0, len(raw), 20)]:
        tainted._fire_stream_delta(chunk)
    clean._fire_stream_delta(BENIGN)
    clean._ccg_stream_flush()
    assert tainted._ccg_tainted == "turn-1"
    assert clean._ccg_tainted is None
    assert clean.stream_delta_callback.text == BENIGN


# ── History / prompt invariants ─────────────────────────────────────────


def test_seal_and_repair_never_mutate_history_or_prompt(monkeypatch):
    from agent.turn_finalizer import apply_llm_output_transform
    from agent import turn_stop_gates

    monkeypatch.setattr(turn_stop_gates, "_verify_on_stop_nudge", lambda agent: None)
    monkeypatch.setattr(turn_stop_gates, "_pre_verify_nudge", lambda agent, text, attempt: None)
    monkeypatch.setattr(turn_stop_gates, "_kanban_stop_nudge", lambda agent, messages: None)

    class _Agent:
        def __init__(self):
            self._ccg_evidence = _evidence("send_message")
            self._ccg_repairs = 0
            self._ccg_repair_turn = "turn-1"
            self._current_turn_id = "turn-1"
            self._session_messages = [{"role": "system", "content": "prompt"}]
            self.session_id = "s"
            self.model = "m"
            self.provider = "p"
            self.platform = "cli"

        def _interim_content_was_streamed(self, text):
            return False

    agent = _Agent()
    system_before = agent._session_messages[0].copy()
    apply_llm_output_transform(agent, DENIAL, turn_id="turn-1")
    assert agent._session_messages == [system_before]

    final_msg = {"role": "assistant", "content": DENIAL}
    messages = [{"role": "system", "content": "prompt"}, {"role": "user", "content": "hola"}, final_msg]
    turn_stop_gates.apply_stop_gates(
        agent,
        final_msg,
        final_response=DENIAL,
        messages=messages,
        conversation_history=[],
        pending_verification_response=None,
        pending_verification_response_previewed=False,
    )
    # The nudge is a user row after the answer; the system prompt is byte-identical.
    assert messages[0] == {"role": "system", "content": "prompt"}
    assert messages[-1]["role"] == "user"
    assert messages[-2] is final_msg
