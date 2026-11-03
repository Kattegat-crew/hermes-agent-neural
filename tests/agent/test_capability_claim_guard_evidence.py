"""Behaviour contract for the Capability Claim Guard evidence snapshot (F2/T1)
and its per-turn capture wiring (F2/T3).

Spec refs: ``.specs/capability-claim-guard/01-spec.md`` (approved), design
``02-design.md`` §3/§7, tasks ``03-tasks.md`` T1/T3.

Pinned behaviour:

* AC2 (decoupling): the snapshot records the SESSION capability — what the
  agent instance holds (``agent.tools`` / ``agent.valid_tool_names``) — never
  the per-payload ``tools=`` of any single API request.
* E5: no process-global "last resolved tool names"; the snapshot lives on the
  agent instance.
* E6: tool_search-bridge deferrable names are recorded separately from direct
  names, because a not-found there does not imply tool absence (§ R4.5).
* E7: capture never re-probes availability (no check_fn / definition calls).
* Turn scope: the snapshot is captured per turn_id and replaced on the next
  turn; a disabled guard still resets stale evidence so nothing leaks.
* AC7 (fail-open): a snapshot failure must never break the turn.
* Config: default off (byte-identical runtime); ``agent.capability_claim_guard.
  enabled`` turns it on.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


# ── Helpers ──────────────────────────────────────────────────────────────


def _tool_def(name):
    return {"type": "function", "function": {"name": name, "parameters": {"type": "object"}}}


def _make_agent(tools=None, **extra):
    """A minimal stand-in exposing exactly the attributes capture reads."""
    agent = SimpleNamespace()
    agent.tools = tools
    for key, value in extra.items():
        setattr(agent, key, value)
    return agent


def _session_agent():
    """Session capability: two direct tools, one deferred (bridge active)."""
    return _make_agent(
        tools=[
            _tool_def("send_message"),
            _tool_def("kanban_list"),
            _tool_def("tool_search"),
        ],
        valid_tool_names={"send_message", "kanban_list", "tool_search"},
    )


# ── T1: Evidence Snapshot (capture_evidence) ─────────────────────────────


class TestCaptureEvidence:
    def test_records_session_capability_not_payload(self):
        """AC2: the snapshot comes from agent.tools; a per-payload tools=
        (even an empty one) must never narrow or replace it."""
        from agent.capability_claim_guard import capture_evidence

        agent = _session_agent()
        evidence = capture_evidence(agent, "turn-1", tool_defs=[])

        assert evidence is not None
        assert "send_message" in evidence.direct
        assert "kanban_list" in evidence.direct
        assert evidence.turn_id == "turn-1"

    def test_tool_defs_param_is_only_a_fallback(self):
        """Without agent.tools (DI/fallback shape), tool_defs feeds direct."""
        from agent.capability_claim_guard import capture_evidence

        agent = _make_agent(tools=None)
        evidence = capture_evidence(agent, "t", tool_defs=[_tool_def("terminal")])

        assert evidence.direct == frozenset({"terminal"})

    def test_deferred_names_recorded_separately(self):
        """E6: bridge-reachable (deferred) names never mix into direct."""
        from agent.capability_claim_guard import capture_evidence

        evidence = capture_evidence(
            _session_agent(), "t", deferred_names={"email_send"}
        )

        assert evidence.deferred == frozenset({"email_send"})
        assert "email_send" not in evidence.direct

    def test_derives_deferred_when_bridge_active(self):
        """With the bridge in the session tools and no explicit set, deferred
        is derived from the registry's deferrable names minus direct."""
        from agent import capability_claim_guard as ccg

        agent = _session_agent()
        with patch.object(
            ccg, "_deferrable_from_registry",
            return_value={"email_send", "send_message"},
        ):
            evidence = ccg.capture_evidence(agent, "t")

        assert evidence.deferred == frozenset({"email_send"})

    def test_no_bridge_means_no_deferred(self):
        from agent import capability_claim_guard as ccg
        from agent.capability_claim_guard import capture_evidence

        agent = _make_agent(tools=[_tool_def("send_message"), _tool_def("terminal")])
        with patch.object(
            ccg, "_deferrable_from_registry", return_value={"email_send"}
        ):
            evidence = capture_evidence(agent, "t")

        assert evidence.deferred == frozenset()

    def test_aliases_recorded(self):
        from agent.capability_claim_guard import capture_evidence

        evidence = capture_evidence(
            _session_agent(), "t", aliases={"list": "kanban_list"}
        )

        assert dict(evidence.aliases) == {"list": "kanban_list"}

    def test_turn_scope_replaces_previous_snapshot(self):
        """Lifecycle = turn: capturing again for a new turn replaces the old
        snapshot (fresh observed_errors, new turn_id)."""
        from agent.capability_claim_guard import capture_evidence, record_observed_error

        agent = _session_agent()
        first = capture_evidence(agent, "turn-1")
        record_observed_error(agent, "send_message", "boom")
        second = capture_evidence(agent, "turn-2")

        agent._ccg_evidence = second
        assert agent._ccg_evidence.turn_id == "turn-2"
        assert agent._ccg_evidence.observed_errors == {}
        assert first.turn_id == "turn-1"

    def test_profile_isolation(self):
        """Snapshots live on the agent instance: two agents never share one."""
        from agent.capability_claim_guard import capture_evidence, record_observed_error

        a = capture_evidence(_session_agent(), "t")
        b = capture_evidence(_session_agent(), "t")
        assert a is not b

        agent_b = _session_agent()
        agent_b._ccg_evidence = capture_evidence(agent_b, "t")
        record_observed_error(agent_b, "send_message", "x")
        assert agent_b._ccg_evidence.observed_errors == {"send_message": "x"}

    def test_fail_open_on_broken_agent(self):
        """AC7: a capture that cannot read the session capability returns
        None instead of raising."""
        from agent.capability_claim_guard import capture_evidence

        class _Broken:
            @property
            def tools(self):
                raise RuntimeError("session capability unavailable")

        assert capture_evidence(_Broken(), "t") is None

    def test_capture_never_probes_availability(self):
        """E7: capture is pure session reads — no definition/check calls."""
        from agent.capability_claim_guard import capture_evidence

        with patch("model_tools.get_tool_definitions", side_effect=AssertionError):
            capture_evidence(_session_agent(), "t")


# ── T2 support: observed-error recording ─────────────────────────────────


class TestRecordObservedError:
    def test_records_into_current_snapshot(self):
        from agent.capability_claim_guard import capture_evidence, record_observed_error

        agent = _session_agent()
        agent._ccg_evidence = capture_evidence(agent, "t")
        record_observed_error(agent, "send_message", "TimeoutError: upstream")

        assert "send_message" in agent._ccg_evidence.observed_errors

    def test_noop_without_snapshot(self):
        from agent.capability_claim_guard import record_observed_error

        agent = _session_agent()  # no capture performed
        record_observed_error(agent, "send_message", "boom")  # must not raise


# ── Config gate ──────────────────────────────────────────────────────────


class TestEnabledFlag:
    def test_default_off(self):
        from agent.capability_claim_guard import is_enabled

        assert is_enabled(_session_agent()) is False

    def test_config_enabled(self):
        from agent.capability_claim_guard import is_enabled

        config = {"agent": {"capability_claim_guard": {"enabled": True}}}
        with patch(
            "hermes_cli.config.load_config_readonly", return_value=config
        ):
            assert is_enabled(_session_agent()) is True

    def test_unreadable_config_is_disabled(self):
        from agent.capability_claim_guard import is_enabled

        with patch(
            "hermes_cli.config.load_config_readonly",
            side_effect=RuntimeError("config unavailable"),
        ):
            assert is_enabled(_session_agent()) is False


# ── T3: per-turn wiring in the real conversation loop ────────────────────


@pytest.fixture()
def loop_agent():
    """Real AIAgent with a mocked client (mirrors test_outer_error_retry_bound),
    with a session capability containing our probe tools."""
    from run_agent import AIAgent
    from tests.agent.test_run_agent import _mock_response

    probe_tools = [_tool_def("send_message"), _tool_def("kanban_list")]
    with (
        patch("model_tools.get_tool_definitions", return_value=probe_tools),
        patch("model_tools.check_toolset_requirements", return_value={}),
        patch("agent.process_bootstrap.OpenAI"),
    ):
        agent = AIAgent(
            api_key="test-key-1234567890",
            base_url="https://openrouter.ai/api/v1",
            quiet_mode=True,
            skip_context_files=True,
            skip_memory=True,
        )
        agent.client = MagicMock()
        agent._cached_system_prompt = "You are helpful."
        agent._use_prompt_caching = False
        agent.tool_delay = 0
        agent.compression_enabled = False
        agent.save_trajectories = False
        agent.tools = [dict(td) for td in probe_tools]
        agent.valid_tool_names = {"send_message", "kanban_list"}
        agent.client.chat.completions.create.side_effect = (
            lambda *a, **k: _mock_response(content="ok", finish_reason="stop")
        )
        yield agent


class TestTurnWiring:
    def test_capture_runs_at_turn_start_when_enabled(self, loop_agent):
        """With the guard enabled, every turn captures a snapshot keyed by the
        turn id and installs it on the agent."""
        with (
            patch("agent.capability_claim_guard._guard_options", return_value=(True, 200, 2, None)),
            patch(
                "agent.capability_claim_guard.capture_evidence",
                wraps=__import__(
                    "agent.capability_claim_guard", fromlist=["capture_evidence"]
                ).capture_evidence,
            ) as spy,
            patch.object(loop_agent, "_persist_session"),
            patch.object(loop_agent, "_save_trajectory"),
            patch.object(loop_agent, "_cleanup_task_resources"),
        ):
            loop_agent.run_conversation("hello")

        assert spy.called
        args, kwargs = spy.call_args
        assert args[0] is loop_agent
        turn_id = kwargs.get("turn_id", args[1] if len(args) > 1 else None)
        assert turn_id, "capture must receive the current turn id"
        assert loop_agent._ccg_evidence is not None
        assert "send_message" in loop_agent._ccg_evidence.direct

    def test_disabled_by_default_captures_nothing(self, loop_agent):
        """AC1: default config = byte-identical runtime; no snapshot runs."""
        with (
            patch.object(loop_agent, "_persist_session"),
            patch.object(loop_agent, "_save_trajectory"),
            patch.object(loop_agent, "_cleanup_task_resources"),
        ):
            loop_agent.run_conversation("hello")

        assert getattr(loop_agent, "_ccg_evidence", None) is None

    def test_stale_evidence_reset_even_when_disabled(self, loop_agent):
        """Turn-scoped hygiene: a previous turn's evidence cannot leak into a
        turn where the guard is disabled."""
        loop_agent._ccg_evidence = "stale-from-previous-turn"
        with (
            patch.object(loop_agent, "_persist_session"),
            patch.object(loop_agent, "_save_trajectory"),
            patch.object(loop_agent, "_cleanup_task_resources"),
        ):
            loop_agent.run_conversation("hello")

        assert loop_agent._ccg_evidence is None

    def test_capture_failure_is_fail_open(self, loop_agent):
        """AC7: a snapshot crash must never break the turn."""
        with (
            patch("agent.capability_claim_guard._guard_options", return_value=(True, 200, 2, None)),
            patch(
                "agent.capability_claim_guard.capture_evidence",
                side_effect=RuntimeError("snapshot boom"),
            ),
            patch.object(loop_agent, "_persist_session"),
            patch.object(loop_agent, "_save_trajectory"),
            patch.object(loop_agent, "_cleanup_task_resources"),
        ):
            result = loop_agent.run_conversation("hello")

        assert result["final_response"] == "ok"
        assert getattr(loop_agent, "_ccg_evidence", None) is None
