"""The delivery layer must never hand DSML tool-call markup to a streaming client.

DeepSeek V4 sometimes emits its native DSML markup as plain ``content``. The turn-final
guard (``agent/dsml_guard.py``) recovers it, but only once the turn closes — with
``display.streaming: true`` every token of the block reached the GUI first. The prefix
buffer in the delta path holds a response that *opens* like the guard's leak grammar:
a partial marker is withheld until it resolves, a response that completes a marker is
held to the response boundary (the turn-final guard owns recovery, so nothing is shown),
and a response that diverges before completing a marker is released exactly once and
then passes straight through.

Behaviour contracts only: no source reading, no internals beyond the callbacks the
delivery layer already owns.
"""

from typing import Any

import pytest

from agent import stream_delivery
from agent.dsml_guard import apply_dsml_guard
from agent.memory_context import StreamingContextScrubber
from agent.stream_delivery import StreamDeliveryMixin
from agent.think_scrubber import StreamingThinkScrubber

# Every opener the guard's grammar recognises (agent/dsml_guard.py::_LEAK_START_RE).
MARKERS = [
    "<||DSML||",
    "<|DSML|",
    "<||DSML|",
    "<|DSML||",
    "<｜｜DSML｜｜",
    "<｜DSML｜",
    "<toolcalls>",
]


class _Agent(StreamDeliveryMixin):
    """Minimal host: what the delta path resolves on a real agent."""

    def __init__(self):
        self.shown: list[str] = []
        self.stream_delta_callback = self.shown.append
        self._stream_callback: Any = None
        self._hold_stream = False
        self._stream_needs_break = False
        # Real scrubbers: the production delta path always runs them, and their tails are part
        # of the boundary behaviour this file pins.
        self._stream_think_scrubber = StreamingThinkScrubber()
        self._stream_context_scrubber = StreamingContextScrubber()
        self.hooks: list[tuple[str, dict]] = []

    def _enqueue_stream_hook(self, event: str, *, label: str | None = None, **fields: Any) -> None:
        self.hooks.append((event, fields))


def _feed(agent: _Agent, *deltas: str) -> list[str]:
    for delta in deltas:
        agent._fire_stream_delta(delta)
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


def test_none_delta_still_reaches_the_callbacks():
    """TTS consumers treat ``None`` as a tool boundary; the buffer must not swallow it."""
    agent = _Agent()
    agent.stream_delta_callback = lambda text: agent.shown.append(text)
    assert agent._deliver_to_stream_callbacks(None) is True
    assert agent.shown == [None]


def test_lone_angle_bracket_that_diverges_releases_exactly_once():
    """'<' alone could open a marker; once it clearly cannot, the bytes appear unchanged."""
    agent = _Agent()
    assert _feed(agent, "<", "div>hola", "</div>") == ["<div>hola", "</div>"]


# ── CA-1: marker openers are withheld ─────────────────────────────────────────────────


@pytest.mark.parametrize("marker", MARKERS)
def test_marker_prefix_is_never_emitted(marker):
    """Every proper prefix of every opener stays invisible, character by character."""
    agent = _Agent()
    for i in range(1, len(marker) + 1):
        assert _feed(agent, marker[i - 1]) == [], f"prefix {marker[:i]!r} leaked to the client"


def test_marker_split_across_deltas_is_held():
    agent = _Agent()
    assert _feed(agent, "<", "||DSML", "||inv", "oke") == []


@pytest.mark.parametrize("marker", MARKERS)
def test_every_guard_opener_is_recognised(marker):
    """The buffer must know the same openers the guard recovers, or the leak simply moves."""
    agent = _Agent()
    _feed(agent, marker + 'invoke name="execute_code"')
    agent._close_dsml_stream_buffer()
    assert agent.shown == []


# ── CA-3: a response that becomes a block shows nothing at all ────────────────────────


def test_completed_marker_holds_the_whole_response_until_close():
    agent = _Agent()
    assert _feed(agent, "<", "||DSML||", 'invoke name="execute_code"', ">", "</||DSML||>") == []
    agent._close_dsml_stream_buffer()
    assert agent.shown == []


def test_block_that_arrives_as_one_delta_is_held_too():
    agent = _Agent()
    assert _feed(agent, '<||DSML||invoke name="terminal">') == []
    agent._close_dsml_stream_buffer()
    assert agent.shown == []


def test_marker_at_start_of_a_real_answer_is_released_not_swallowed():
    """The guard only recovers marker+invocation; prose that opens with a bare marker is text."""
    agent = _Agent()
    _feed(agent, "<||DSML||", " es el marcador que documentamos")
    agent._close_dsml_stream_buffer()
    assert agent.shown == ["<||DSML|| es el marcador que documentamos"]


def test_truncated_invoke_keyword_is_treated_as_a_block():
    """The dominant production leak is cut mid-token; `inv` alone is what the guard matches."""
    agent = _Agent()
    assert _feed(agent, "<||DSML||inv", ' name="terminal">') == []
    agent._close_dsml_stream_buffer()
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


# ── the synthetic tool-iteration break must not defeat the probe ──────────────────────


def test_tool_break_prefix_does_not_leak_the_markup():
    """`_fire_stream_delta` prepends "\\n\\n" after a tool round; the probe runs on the delta."""
    agent = _Agent()
    agent._stream_needs_break = True
    assert _feed(agent, '<||DSML||invoke name="terminal">') == []
    agent._close_dsml_stream_buffer()
    assert agent.shown == []
    assert agent._stream_needs_break is True  # the break was never emitted


def test_tool_break_is_kept_for_the_next_real_delta():
    agent = _Agent()
    agent._stream_needs_break = True
    assert _feed(agent, "<") == []
    assert _feed(agent, "Aquí está el resumen") == ["\n\n<Aquí está el resumen"]


# ── response boundaries ───────────────────────────────────────────────────────────────


def test_pending_partial_marker_that_is_not_a_marker_is_flushed_at_close():
    """A lone '<' at the very end of a reply is real text — closing must not eat it."""
    agent = _Agent()
    _feed(agent, "<")
    agent._reset_stream_delivery_tracking()
    assert agent.shown == ["<"]


def test_reset_closes_after_the_scrubber_tails():
    """`_reset_stream_delivery_tracking` flushes scrubber tails through the same buffer; the
    boundary must run last so a tail-hold cannot survive into the next response."""
    agent = _Agent()
    _feed(agent, "Hola<")
    agent._reset_stream_delivery_tracking()
    assert "".join(agent.shown) == "Hola<"
    assert agent._dsml_stream_buffer == ""
    before = len(agent.shown)
    _feed(agent, "Mundo")
    assert agent.shown[before:] == ["Mundo"]  # no tail from the previous reply bled in


def test_buffer_resets_per_response_not_per_session():
    agent = _Agent()
    _feed(agent, "<||DSML||invoke")
    agent._reset_stream_delivery_tracking()
    assert _feed(agent, "Otra respuesta limpia") == ["Otra respuesta limpia"]


# ── hold_stream keeps its contract (nothing leaves at all) ────────────────────────────


def test_hold_stream_still_suppresses_everything():
    agent = _Agent()
    agent._hold_stream = True
    assert _feed(agent, "texto limpio", "<||DSML||") == []
    agent._reset_stream_delivery_tracking()
    assert agent.shown == []


# ── CA-5: hooks and the streamed-text record see exactly what was shown ───────────────


def test_clean_text_reaches_every_registered_callback_identically():
    agent = _Agent()
    second: list[str] = []
    agent._stream_callback = second.append
    agent._deliver_to_stream_callbacks("respuesta normal")
    assert agent.shown == second == ["respuesta normal"]


def test_plugin_hook_never_receives_withheld_markup():
    agent = _Agent()
    _feed(agent, "<||DSML||inv")
    agent._close_dsml_stream_buffer()  # a real block: dropped at the boundary
    assert [f["delta"] for e, f in agent.hooks if e == "on_stream_delta"] == []


def test_plugin_hook_receives_the_released_buffer_in_order():
    agent = _Agent()
    _feed(agent, "<", "div>x</div>")
    assert [f["delta"] for e, f in agent.hooks if e == "on_stream_delta"] == ["<div>x</div>"]


def test_released_buffer_is_recorded_as_streamed_text():
    """Interim dedup and final recovery read `_current_streamed_assistant_text`."""
    agent = _Agent()
    _feed(agent, "<｜", "X")
    assert agent.shown == ["<｜X"]
    assert agent._current_streamed_assistant_text == "<｜X"


# ── CA-3, end to end: the guard still owns the block we withheld ──────────────────────


def test_guard_still_recovers_the_block_the_stream_withheld():
    block = '<||DSML||invoke name="execute_code"><||DSML||parameter name="code" string="true">print(1)</||DSML||parameter></||DSML||invoke>'
    agent = _Agent()
    assert _feed(agent, *block) == []
    agent._close_dsml_stream_buffer()
    assert agent.shown == []
    result = apply_dsml_guard("texto antes " + block, ["execute_code"])
    assert "DSML" not in result.response
    assert result.reemit_call and result.reemit_call["name"] == "execute_code"


# ── observability ────────────────────────────────────────────────────────────────────


def test_accounting_counts_one_hold_per_discarded_block():
    agent = _Agent()
    _feed(agent, "<||DSML||invoke")
    assert getattr(agent, "_dsml_stream_held", 0) == 0  # still held, not resolved yet
    agent._close_dsml_stream_buffer()
    assert getattr(agent, "_dsml_stream_held", 0) == 1
    agent._reset_stream_delivery_tracking()
    _feed(agent, "limpio")
    assert getattr(agent, "_dsml_stream_held", 0) == 1  # a clean reply must not count


def test_benign_angle_bracket_is_not_counted_as_a_hold():
    agent = _Agent()
    _feed(agent, "<", "h1>x</h1>")
    assert getattr(agent, "_dsml_stream_held", 0) == 0
