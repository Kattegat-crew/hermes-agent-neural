"""T4 — S1 delta sink: holdback window, prefix stability, taint, flush.

Contract under test (design §2/§5-S1, task T4):

* While the guard is enabled, text emitted through the stream delta sink is held
  back by a bounded window (``holdback_chars``) so a capability denial is judged
  before it reaches a surface.
* Published text is always a PREFIX of the raw stream: frames are never retracted.
* A detected contradiction marks the turn tainted and stops further publication;
  the correction travels through the final seal (T6), never through a retraction.
* Disabled (no evidence snapshot) is byte-identical: every delta is published
  immediately and no guard state is created.
"""

from __future__ import annotations

import pytest

from agent.capability_claim_guard import CapabilityEvidence
from agent.stream_delivery import StreamDeliveryMixin

DENIAL = "No tengo herramientas de mensajería para enviar eso."
BENIGN = "Resumen del turno: revisé los archivos del proyecto y anoté los hallazgos. "


class _Sink:
    def __init__(self) -> None:
        self.parts: list[str] = []

    def __call__(self, text: str) -> None:
        self.parts.append(text)

    @property
    def text(self) -> str:
        return "".join(self.parts)


class _StreamAgent(StreamDeliveryMixin):
    """Minimal agent double: only the attributes the delta sink touches."""

    def __init__(self, evidence=None, *, turn_id="turn-1") -> None:
        self.stream_delta_callback = _Sink()
        self._stream_callback = None
        self.reasoning_callback = None
        self.tool_gen_callback = None
        self.interim_assistant_callback = None
        self._ccg_evidence = evidence
        self._streamed_assistant_text_parts: list[str] = []
        self._stream_needs_break = False
        self._native_reasoning_streamed = False
        self._stream_reasoning_hooks_enabled = False
        self._current_turn_id = turn_id
        self.session_id = "session-1"
        self.model = "model-1"
        self.provider = "provider-1"
        self.platform = "cli"
        self._api_call_count = 0
        self.show_commentary = True

    # Other mixins supply these in production; the sink only needs identity here.
    def _strip_think_blocks(self, text):
        return text

    def _visible_commentary(self, text):
        return text

    def _fire_first_delta(self):
        return None

    @property
    def published(self) -> str:
        return self.stream_delta_callback.text


def _evidence(*names: str, holdback=200, repair_limit=2) -> CapabilityEvidence:
    return CapabilityEvidence(
        turn_id="turn-1",
        direct=frozenset(names),
        holdback_chars=holdback,
        repair_limit=repair_limit,
    )


# ── Disabled: byte-identical runtime ─────────────────────────────────────


def test_disabled_publishes_every_delta_immediately():
    agent = _StreamAgent(evidence=None)
    agent._fire_stream_delta(DENIAL)
    assert agent.published == DENIAL
    assert getattr(agent, "_ccg_hold_parts", None) is None


def test_disabled_does_not_scan(monkeypatch):
    calls = []

    def spy(*args, **kwargs):
        calls.append(args)
        raise AssertionError("scan must not run while the guard is disabled")

    monkeypatch.setattr("agent.capability_claim_guard.scan_published_text", spy)
    agent = _StreamAgent(evidence=None)
    agent._fire_stream_delta("No tengo herramientas de nada.")
    assert calls == []
    assert agent.published == "No tengo herramientas de nada."


# ── Enabled: bounded holdback ────────────────────────────────────────────


def test_holdback_delays_short_text_within_window():
    agent = _StreamAgent(_evidence("send_message"))
    agent._fire_stream_delta("Voy a revisar.")
    assert agent.published == ""  # inside the holdback window
    agent._ccg_stream_flush()
    assert agent.published == "Voy a revisar."


def test_holdback_window_is_bounded():
    agent = _StreamAgent(_evidence("send_message"))
    agent._fire_stream_delta("a" * 5000)
    held = "".join(getattr(agent, "_ccg_hold_parts", []) or [])
    assert len(held) <= 200


def test_clean_stream_is_published_completely_after_flush():
    agent = _StreamAgent(_evidence("send_message"))
    chunks = [BENIGN[i:i + 17] for i in range(0, len(BENIGN), 17)]
    for chunk in chunks:
        agent._fire_stream_delta(chunk)
    agent._ccg_stream_flush()
    assert agent.published == BENIGN


# ── Enabled: contradiction handling ──────────────────────────────────────


def test_contradiction_is_never_published_and_taints_the_turn():
    agent = _StreamAgent(_evidence("send_message"))
    prefix = "Revisé el repositorio y actualicé los dos archivos desactualizados. " * 6
    for chunk in [prefix[i:i + 23] for i in range(0, len(prefix), 23)]:
        agent._fire_stream_delta(chunk)
    published_prefix = agent.published
    assert published_prefix  # the benign head was published live
    for chunk in [DENIAL[i:i + 23] for i in range(0, len(DENIAL), 23)]:
        agent._fire_stream_delta(chunk)
    agent._ccg_stream_flush()  # the held tail is judged before it is published
    assert "No tengo" not in agent.published
    assert "No tengo" not in published_prefix
    assert agent.published.startswith(published_prefix)  # prefix stability: nothing retracted
    assert agent._ccg_tainted == "turn-1"


def test_tainted_turn_publishes_nothing_after_detection():
    agent = _StreamAgent(_evidence("send_message"))
    raw = "Revisé el repositorio y actualicé los dos archivos desactualizados. " * 6 + DENIAL
    for chunk in [raw[i:i + 23] for i in range(0, len(raw), 23)]:
        agent._fire_stream_delta(chunk)
    agent._ccg_stream_flush()
    assert agent._ccg_tainted == "turn-1"
    before = agent.published
    agent._fire_stream_delta("Sigo escribiendo texto adicional después de la negativa. ")
    assert agent.published == before


def test_tainted_flush_publishes_nothing():
    agent = _StreamAgent(_evidence("send_message"))
    raw = "Revisé el repositorio y actualicé los dos archivos desactualizados. " * 6 + DENIAL
    for chunk in [raw[i:i + 23] for i in range(0, len(raw), 23)]:
        agent._fire_stream_delta(chunk)
    agent._ccg_stream_flush()
    assert agent._ccg_tainted == "turn-1"
    before = agent.published
    agent._ccg_stream_flush()
    assert agent.published == before


def test_negation_split_across_deltas_is_detected():
    agent = _StreamAgent(_evidence("send_message"))
    prefix = "Revisé el repositorio y actualicé los dos archivos desactualizados. " * 6
    for chunk in [prefix[i:i + 11] for i in range(0, len(prefix), 11)]:
        agent._fire_stream_delta(chunk)
    for chunk in ["No ten", "go herram", "ientas de mensa", "jería para enviar."]:
        agent._fire_stream_delta(chunk)
    agent._ccg_stream_flush()
    assert agent._ccg_tainted == "turn-1"
    assert "No ten" not in agent.published


def test_code_fence_spanning_deltas_is_exempt():
    agent = _StreamAgent(_evidence("send_message"))
    fenced = "```text\nno tengo herramientas de mensajería\ntool_search falló\n```\n" + BENIGN
    for chunk in [fenced[i:i + 13] for i in range(0, len(fenced), 13)]:
        agent._fire_stream_delta(chunk)
    agent._ccg_stream_flush()
    assert agent._ccg_tainted is None
    assert agent.published == fenced


def test_observed_error_makes_the_denial_truthful():
    evidence = _evidence("send_message")
    evidence.observed_errors["send_message"] = "blocked"
    agent = _StreamAgent(evidence)
    raw = BENIGN + DENIAL
    for chunk in [raw[i:i + 23] for i in range(0, len(raw), 23)]:
        agent._fire_stream_delta(chunk)
    agent._ccg_stream_flush()
    assert agent._ccg_tainted is None
    assert agent.published == raw


@pytest.mark.parametrize("surface_attr", ["stream_delta_callback"])
def test_published_text_matches_streamed_accumulator(surface_attr):
    agent = _StreamAgent(_evidence("send_message"))
    agent._fire_stream_delta(BENIGN)
    agent._ccg_stream_flush()
    assert getattr(agent, surface_attr).text == agent._current_streamed_assistant_text


# ── Provider-agnosticism and the disabled-path spy ───────────────────────


@pytest.mark.parametrize("provider", ["codex", "anthropic", "openai", "local"])
def test_gate_applies_to_every_provider_wire(provider):
    """The sink is provider-agnostic: the gate sits above the wire helper."""
    agent = _StreamAgent(_evidence("send_message"))
    agent.provider = provider
    raw = "Revisé el repositorio y actualicé los dos archivos desactualizados. " * 6 + DENIAL
    for chunk in [raw[i:i + 19] for i in range(0, len(raw), 19)]:
        agent._fire_stream_delta(chunk)
    agent._ccg_stream_flush()
    assert agent._ccg_tainted == "turn-1"
    assert "No tengo" not in agent.published


def test_disabled_path_never_calls_the_guard(monkeypatch):
    """AC1: with no snapshot the sink must not even reach the guard module."""
    import agent.capability_claim_guard as ccg

    def _bomb(*args, **kwargs):  # pragma: no cover - must never run
        raise AssertionError("guard reached while disabled")

    monkeypatch.setattr(ccg, "stream_gate", _bomb)
    monkeypatch.setattr(ccg, "flush_stream_holdback", _bomb)
    agent = _StreamAgent(None)
    agent._fire_stream_delta(BENIGN)
    agent._ccg_stream_flush()
    assert agent.published == BENIGN
    assert not hasattr(agent, "_ccg_tainted")
    assert not hasattr(agent, "_ccg_hold_parts")
