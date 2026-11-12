"""The delivery layer must never hand DSML tool-call markup to a streaming client.

DeepSeek V4 sometimes emits its native DSML markup as plain ``content``. The turn-final
guard (``agent/dsml_guard.py``) recovers it, but only once the turn closes — with
``display.streaming: true`` every token of the block reached the GUI first. The prefix
buffer in ``_deliver_to_stream_callbacks`` holds a response that *opens* like one of the
markers: a partial marker is withheld until it resolves, a response that completes a
marker is held to the response boundary (the turn-final guard owns recovery, so nothing
is shown), and a response that diverges without ever completing a marker is released
exactly once and then passes straight through.

Behaviour contracts only: no source reading, no internals beyond the callbacks the
delivery layer already owns.
"""

from typing import Any

import pytest

from agent import stream_delivery
from agent.stream_delivery import StreamDeliveryMixin

MARKERS = ["<||DSML||", "<｜｜DSML｜｜", "<｜DSML｜", "<toolcalls>", "||DSML||"]


class _Agent(StreamDeliveryMixin):
    """Minimal host: what ``_deliver_to_stream_callbacks`` resolves on a real agent."""

    def __init__(self):
        self.shown: list[str] = []
        self.stream_delta_callback = self.shown.append
        self._stream_callback: Any = None
        self._hold_stream = False


def _feed(agent: _Agent, *deltas: str) -> list[str]:
    for delta in deltas:
        agent._deliver_to_stream_callbacks(delta)
    return agent.shown


# ── CA-4: clean text keeps today's byte-for-byte behaviour ─────────────────────────────


def test_clean_first_delta_is_delivered_immediately():
    agent = _Agent()
    assert _feed(agent, "Hola, esto es normal") == ["Hola, esto es normal"]


def test_clean_stream_after_first_delta_is_passthrough():
    agent = _Agent()
    assert _feed(agent, "Uno ", "dos ", "tres") == ["Uno ", "dos ", "tres"]


def test_empty_delta_is_not_emitted():
    agent = _Agent()
    assert _feed(agent, "") == []


def test_lone_angle_bracket_that_diverges_releases_exactly_once():
    """'<' alone could open a marker; once it clearly cannot, the bytes appear unchanged."""
    agent = _Agent()
    assert _feed(agent, "<", "div>hola", "</div>") == ["<div>hola", "</div>"]


# ── CA-1: marker prefixes are withheld ────────────────────────────────────────────────


@pytest.mark.parametrize("marker", MARKERS)
def test_marker_prefix_is_never_emitted(marker):
    """Every proper prefix of every marker stays invisible, character by character."""
    agent = _Agent()
    for i in range(1, len(marker) + 1):
        assert _feed(agent, marker[i - 1]) == [], f"prefix {marker[:i]!r} leaked to the client"
    # the marker itself is still held: it may yet turn into a block
    assert agent.shown == []


def test_marker_split_across_deltas_is_held():
    agent = _Agent()
    assert _feed(agent, "<", "||DSML||", "invoke") == []


# ── CA-3: a response that becomes a block shows nothing at all ────────────────────────


@pytest.mark.parametrize("marker", MARKERS)
def test_completed_marker_holds_the_whole_response_until_close(marker):
    """Once the opening spells a marker the reply is a leaked block: not one byte escapes,
    and the buffer is discarded at the response boundary so the turn-final guard recovers."""
    agent = _Agent()
    assert _feed(agent, marker[:2], marker[2:], 'invoke name="execute_code"', ">", "</||DSML||>") == []
    agent._reset_stream_delivery_tracking()
    assert agent.shown == []


def test_block_that_arrives_as_one_delta_is_held_too():
    agent = _Agent()
    assert _feed(agent, '<||DSML||invoke name="terminal">') == []
    agent._reset_stream_delivery_tracking()
    assert agent.shown == []


# ── CA-2: a genuine divergence flushes once, then passthrough ─────────────────────────


def test_divergence_flushes_the_buffer_exactly_once():
    agent = _Agent()
    assert _feed(agent, "<", "h1>Título", "</h1>") == ["<h1>Título", "</h1>"]


def test_flush_is_not_repeated_on_later_deltas():
    agent = _Agent()
    _feed(agent, "<", "h1>", "x")
    released = list(agent.shown)
    _feed(agent, "y", "z")
    assert released == ["<h1>", "x"]  # buffer released once, then passthrough
    assert agent.shown == ["<h1>", "x", "y", "z"]


def test_marker_mid_prose_is_not_held():
    """Only the start of a response is a candidate: prose that mentions a marker streams."""
    agent = _Agent()
    assert _feed(agent, "El marcador ", "<||DSML||", " aparece así") == [
        "El marcador ",
        "<||DSML||",
        " aparece así",
    ]


def test_hold_bound_releases_a_pathological_block(monkeypatch):
    """The bound keeps a runaway block from stalling the client forever."""
    monkeypatch.setattr(stream_delivery, "_DSML_STREAM_HOLD_MAX", 20)
    agent = _Agent()
    assert _feed(agent, "<||DSML||", "x" * 40) == ["<||DSML||" + "x" * 40]
    assert _feed(agent, "sigue") == ["<||DSML||" + "x" * 40, "sigue"]


# ── response boundaries ───────────────────────────────────────────────────────────────


def test_pending_partial_marker_that_is_not_a_marker_is_flushed_at_close():
    """A lone '<' at the very end of a reply is real text — closing must not eat it."""
    agent = _Agent()
    _feed(agent, "<")
    agent._reset_stream_delivery_tracking()
    assert agent.shown == ["<"]


def test_buffer_resets_per_response_not_per_session():
    agent = _Agent()
    _feed(agent, "<||DSML||")
    agent._reset_stream_delivery_tracking()
    assert _feed(agent, "Otra respuesta limpia") == ["Otra respuesta limpia"]


# ── hold_stream keeps its contract (nothing leaves at all) ────────────────────────────


def test_hold_stream_still_suppresses_everything():
    agent = _Agent()
    agent._hold_stream = True
    assert _feed(agent, "texto limpio", "<||DSML||") == []
    agent._reset_stream_delivery_tracking()
    assert agent.shown == []


# ── CA-5: identical events for clean text ─────────────────────────────────────────────


def test_clean_text_reaches_every_registered_callback_identically():
    agent = _Agent()
    second: list[str] = []
    agent._stream_callback = second.append
    agent._deliver_to_stream_callbacks("respuesta normal")
    assert agent.shown == second == ["respuesta normal"]


def test_accounting_counts_one_hold_per_buffered_response():
    """Observability: the daily digest can count holds next to recoveries (spec §6)."""
    agent = _Agent()
    _feed(agent, "<", "div")
    assert getattr(agent, "_dsml_stream_held", 0) == 1
    agent._reset_stream_delivery_tracking()
    _feed(agent, "limpio")
    assert getattr(agent, "_dsml_stream_held", 0) == 1
