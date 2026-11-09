"""T5 — S2 interim/commentary gate.

Contract (design §2/§5-S2, task T5): commentary/interim text is judged BEFORE it
reaches ``interim_assistant_callback`` (TUI/Desktop/Gateway). A contradiction that
was never streamed is suppressed; one already streamed is only registered (it is on
screen, so the correction travels through the final seal). Nothing here mutates
history or the system prompt.
"""

from __future__ import annotations

from agent.capability_claim_guard import CapabilityEvidence
from agent.stream_delivery import StreamDeliveryMixin

DENIAL = "No tengo herramientas de mensajería, así que no puedo enviar el mensaje."


class _InterimSink:
    def __init__(self) -> None:
        self.calls: list[tuple[str, bool]] = []

    def __call__(self, text: str, *, already_streamed: bool = False) -> None:
        self.calls.append((text, already_streamed))


class _InterimAgent(StreamDeliveryMixin):
    def __init__(self, evidence=None, *, streamed: str = "") -> None:
        self.interim_assistant_callback = _InterimSink()
        self.stream_delta_callback = None
        self._stream_callback = None
        self.reasoning_callback = None
        self.tool_gen_callback = None
        self._ccg_evidence = evidence
        self._streamed_assistant_text_parts = [streamed] if streamed else []
        self._delivered_interim_texts: set[str] = set()
        self._current_turn_id = "turn-1"
        self.session_id = "session-1"
        self.model = "model-1"
        self.provider = "provider-1"
        self.platform = "cli"
        self.show_commentary = True

    def _strip_think_blocks(self, text):
        return text

    def _visible_commentary(self, text):
        return text

    @property
    def calls(self):
        return self.interim_assistant_callback.calls


def _evidence(*names: str) -> CapabilityEvidence:
    return CapabilityEvidence(turn_id="turn-1", direct=frozenset(names))


def test_contradiction_not_streamed_is_suppressed():
    agent = _InterimAgent(_evidence("send_message"))
    agent._deliver_interim(DENIAL, already_streamed=False, record=[DENIAL])
    assert agent.calls == []
    assert agent._ccg_tainted == "turn-1"


def test_contradiction_already_streamed_is_delivered_and_registered():
    agent = _InterimAgent(_evidence("send_message"), streamed=DENIAL)
    agent._deliver_interim(DENIAL, already_streamed=True, record=[DENIAL])
    assert [c[0] for c in agent.calls] == [DENIAL]
    assert agent._ccg_tainted == "turn-1"


def test_clean_interim_is_delivered_unchanged():
    agent = _InterimAgent(_evidence("send_message"))
    text = "Revisé el repositorio y encontré dos archivos desactualizados."
    agent._deliver_interim(text, already_streamed=False, record=[text])
    assert [c[0] for c in agent.calls] == [text]
    assert agent._ccg_tainted is None


def test_disabled_delivers_and_creates_no_state():
    agent = _InterimAgent(evidence=None)
    agent._deliver_interim(DENIAL, already_streamed=False, record=[DENIAL])
    assert [c[0] for c in agent.calls] == [DENIAL]
    assert getattr(agent, "_ccg_tainted", None) is None


def test_suppressed_interim_is_not_marked_delivered():
    agent = _InterimAgent(_evidence("send_message"))
    agent._deliver_interim(DENIAL, already_streamed=False, record=[DENIAL])
    assert agent._interim_text_was_delivered(DENIAL) is False


def test_emit_interim_message_path_is_gated():
    agent = _InterimAgent(_evidence("send_message"))
    agent._emit_interim_assistant_message({"role": "assistant", "content": DENIAL})
    assert agent.calls == []
    assert agent._ccg_tainted == "turn-1"
