"""Pure tool-call loop guardrail primitives.

The controller is side-effect free: it tracks per-turn tool-call observations
and returns decisions. Runtime code decides whether a decision becomes warning
guidance, a synthetic tool result, or a controlled turn halt.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import deque
from dataclasses import asdict, dataclass, field, fields
from typing import Any, Mapping

from utils import safe_json_loads
from agent.tool_result_classification import file_mutation_result_landed, is_guardrail_refusal


IDEMPOTENT_TOOL_NAMES = frozenset({
    "read_file", "search_files", "web_search", "web_extract", "session_search",
    "skill_view", "skills_list", "skill_search", "skill_route",
    "browser_snapshot", "browser_console", "browser_get_images", "mcp_filesystem_read_file",
    "mcp_filesystem_read_text_file", "mcp_filesystem_read_multiple_files", "mcp_filesystem_list_directory",
    "mcp_filesystem_list_directory_with_sizes", "mcp_filesystem_directory_tree", "mcp_filesystem_get_file_info",
    "mcp_filesystem_search_files",
})

MUTATING_TOOL_NAMES = frozenset({
    "terminal", "execute_code", "write_file", "patch", "todo_list", "memory", "skill_manage",
    "browser_click", "browser_type", "browser_press", "browser_scroll", "browser_navigate",
    "send_message", "cronjob_manage", "delegate_task", "process_manage",
})

# Pollers: legitimately re-invoked with identical args; the identical-call NOTICE never fires.
STALL_GUARD_REPEATABLE_TOOLS = frozenset({"process_manage"})
_STALL_GUARD_REPEATABLE_SUFFIXES = ("_get_result", "_poll")  # generated / MCP poller conventions
# Nth consecutive identical (tool, args, result) call that fires the notice; 3 tolerates one double-check.
STALL_GUARD_IDENTICAL_CALL_THRESHOLD = 3
# Repeating multi-call cycles (A,B,A,B,... with identical args AND results) defeat the
# consecutive streak above — every alternation resets it, so a model replaying the same
# 2–4 call batch each iteration ran to the budget unflagged (port of can1357/oh-my-pi#10521,
# which widened their loop guard from single-call turns to whole tool-call batches).
# Longest cycle period detected; laps reuse the streak thresholds (notice at
# STALL_GUARD_IDENTICAL_CALL_THRESHOLD laps, halt at no_progress_block_after laps).
_STALL_GUARD_MAX_CYCLE_PERIOD = 4
# History window: enough for block_after laps of the longest cycle plus slack.
_STALL_GUARD_CYCLE_HISTORY = 64
# From the 2nd byte-identical repeat the duplicate payload becomes a reference stub; smaller results
# aren't worth it, errors never are. The args preview keeps WHAT was called if compression evicts the original.
IDENTICAL_RESULT_STUB_MIN_CHARS = 512
_RESULT_STUB_ARGS_PREVIEW_CHARS = 120

# Tools whose "failure" is normal work output (red test run, empty grep, page timeout).
# same_tool_failure (DIFFERENT commands) never halts these; only an exact-args replay with
# no intervening change, or an identical-result streak, can.
FAILURE_TOLERANT_TOOL_NAMES = frozenset({
    "terminal", "execute_code", "process_manage", "process", "browser_navigate", "web_extract",
})

# A successful call to one of these marks progress for every failing signature still counted
# this turn: the next retry is a new experiment (edit -> re-run), not a replay.
PROGRESS_RESET_TOOL_NAMES = frozenset({
    "write_file", "patch", "terminal", "execute_code", "browser_click", "browser_type", "browser_press",
    "browser_navigate", "process_manage", "process", "delegate_task", "send_message", "cronjob",
    "cronjob_manage", "todo", "todo_list", "memory", "skill_manage",
})

_BOOL_FIELDS = ("warnings_enabled", "hard_stop_enabled", "non_interactive_hard_stop_enabled")
# Threshold field -> (nested section, nested key). The flat legacy key is the field name itself.
_THRESHOLD_SOURCES: dict[str, tuple[str, str]] = {
    "exact_failure_warn_after": ("warn_after", "exact_failure"),
    "same_tool_failure_warn_after": ("warn_after", "same_tool_failure"),
    "no_progress_warn_after": ("warn_after", "idempotent_no_progress"),
    "exact_failure_block_after": ("hard_stop_after", "exact_failure"),
    "same_tool_failure_halt_after": ("hard_stop_after", "same_tool_failure"),
    "no_progress_block_after": ("hard_stop_after", "idempotent_no_progress"),
}

# Per-turn caps on runaway-prone tools (counters reset in reset_for_turn).
_DEFAULT_MAX_WEB_SEARCHES_PER_TURN = 50
_DEFAULT_MAX_SUBAGENTS_PER_TURN = 50

# Interactive surfaces plus bounded supervised task loops (subagent stopped by its parent;
# api_server has a live client) doing real edit -> re-run work keep the warn-only default.
_ATTENDED_PLATFORMS = frozenset({"cli", "tui", "desktop", "acp", "subagent", "api_server"})


def is_stall_guard_repeatable(tool_name: str) -> bool:
    """Whether a tool is exempt from the identical-call loop notice."""
    return tool_name in STALL_GUARD_REPEATABLE_TOOLS or tool_name.endswith(_STALL_GUARD_REPEATABLE_SUFFIXES)


def _is_non_interactive_platform(platform: str | None) -> bool:
    """True for gateway/cron sessions where tool loops are unattended."""
    if not isinstance(platform, str) or not platform.strip():
        return False
    return platform.strip().lower() not in _ATTENDED_PLATFORMS


@dataclass(frozen=True)
class LoopCapConfig:
    """Per-turn hard ceilings on web_search calls / subagent spawns; count total calls (not
    repeats), fire regardless of ``hard_stop_enabled``; ``0`` disables a cap."""

    max_web_searches: int = _DEFAULT_MAX_WEB_SEARCHES_PER_TURN
    max_subagents: int = _DEFAULT_MAX_SUBAGENTS_PER_TURN

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None) -> LoopCapConfig:
        """Build config from the ``tool_loop_guardrails.loop_caps`` section."""
        if not isinstance(data, Mapping):
            return cls()
        return cls(**{f.name: _int_at_least(data.get(f.name), f.default, 0) for f in fields(cls)})


@dataclass(frozen=True)
class ToolCallGuardrailConfig:
    """Thresholds for per-turn tool-call loop detection. Warnings never prevent execution; hard
    stops are opt-in on interactive platforms, default on for unattended gateway/cron platforms."""

    warnings_enabled: bool = True
    hard_stop_enabled: bool = False
    non_interactive_hard_stop_enabled: bool = True
    exact_failure_warn_after: int = 2
    exact_failure_block_after: int = 5
    same_tool_failure_warn_after: int = 3
    same_tool_failure_halt_after: int = 8
    no_progress_warn_after: int = 2
    no_progress_block_after: int = 5
    idempotent_tools: frozenset[str] = field(default_factory=lambda: IDEMPOTENT_TOOL_NAMES)
    mutating_tools: frozenset[str] = field(default_factory=lambda: MUTATING_TOOL_NAMES)
    loop_caps: LoopCapConfig = field(default_factory=LoopCapConfig)

    @classmethod
    def from_mapping(
        cls, data: Mapping[str, Any] | None, *, platform: str | None = None,
    ) -> ToolCallGuardrailConfig:
        """Build config from `tool_loop_guardrails`; nested ``warn_after`` / ``hard_stop_after`` win over flat legacy keys."""
        if not isinstance(data, Mapping):
            data = {}
        d = cls()
        flags = {name: _as_bool(data.get(name), getattr(d, name)) for name in _BOOL_FIELDS}
        if flags["non_interactive_hard_stop_enabled"] and _is_non_interactive_platform(platform):
            flags["hard_stop_enabled"] = True

        def threshold(name: str, section_name: str, key: str) -> int:
            section = data.get(section_name)
            nested = section.get(key, data.get(name)) if isinstance(section, Mapping) else data.get(name)
            return _int_at_least(nested, getattr(d, name), 1)

        thresholds = {name: threshold(name, *src) for name, src in _THRESHOLD_SOURCES.items()}
        return cls(loop_caps=LoopCapConfig.from_mapping(data.get("loop_caps")), **flags, **thresholds)


@dataclass(frozen=True)
class IdenticalCallObservation:
    """``notice`` is appended after the result, ``stub`` replaces a byte-identical duplicate result;
    ``kind`` names the detector behind the notice (``identical_call_streak`` / ``identical_cycle``)."""

    notice: str | None = None
    stub: str | None = None
    kind: str | None = None


@dataclass(frozen=True)
class ToolCallSignature:
    """Stable, non-reversible identity for a tool name plus canonical args."""

    tool_name: str
    args_hash: str

    @classmethod
    def from_call(cls, tool_name: str, args: Mapping[str, Any] | None) -> ToolCallSignature:
        return cls(tool_name=tool_name, args_hash=_sha256(canonical_tool_args(args or {})))

    def to_metadata(self) -> dict[str, str]:
        """Return public metadata without raw argument values."""
        return asdict(self)


@dataclass(frozen=True)
class ToolGuardrailDecision:
    """Decision returned by the tool-call guardrail controller."""

    action: str = "allow"  # allow | warn | block | halt
    code: str = "allow"
    message: str = ""
    tool_name: str = ""
    count: int = 0
    signature: ToolCallSignature | None = None

    @property
    def allows_execution(self) -> bool:
        return self.action in {"allow", "warn"}

    @property
    def should_halt(self) -> bool:
        return self.action in {"block", "halt"}

    def to_metadata(self) -> dict[str, Any]:
        data = asdict(self)
        if data["signature"] is None:
            del data["signature"]
        return data


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def canonical_tool_args(args: Mapping[str, Any]) -> str:
    """Return sorted compact JSON for parsed tool arguments."""
    if not isinstance(args, Mapping):
        raise TypeError(f"tool args must be a mapping, got {type(args).__name__}")
    return _canonical_json(args)


def classify_tool_failure(tool_name: str, result: str | None) -> tuple[bool, str]:
    """Fallback classifier used only when callers don't pass ``failed``; mirrors
    ``agent.display._detect_tool_failure`` so the guardrail never disagrees with the CLI's ``[error]`` tag."""
    if result is None or file_mutation_result_landed(tool_name, result):
        return False, ""

    # A harness REFUSAL of a redundant call (repeated identical read/search) carries
    # ``"error"`` for the model's benefit -- exactly what the substring test below keys
    # on -- but nothing failed; counting it lets the cheap refusal feed the streak that
    # fires the next, harder one. Mirrored in ``agent.display._detect_tool_failure``.
    if is_guardrail_refusal(result):
        return False, ""

    if tool_name == "terminal":
        data = safe_json_loads(result)
        exit_code = data.get("exit_code") if isinstance(data, dict) else None
        return (True, f" [exit {exit_code}]") if exit_code is not None and exit_code != 0 else (False, "")

    if tool_name == "memory":
        data = safe_json_loads(result)
        if isinstance(data, dict) and data.get("success") is False and "exceed the limit" in data.get("error", ""):
            return True, " [full]"
    lower = result[:500].lower()
    return (True, " [error]") if '"error"' in lower or '"failed"' in lower or result.startswith("Error") else (False, "")


# Guardrail verdict text injected into the conversation, keyed by decision code.
# ``same_tool_failure_warning`` is built by _tool_failure_recovery_hint (tool-specific).
_DECISION_MESSAGES: dict[str, str] = {
    "repeated_exact_failure_block": (
        "Blocked {tool_name}: the same tool call failed {count} times with identical arguments. "
        "Stop retrying it unchanged; change strategy or explain the blocker."
    ),
    "idempotent_no_progress_block": (
        "Blocked {tool_name}: this read-only call returned the same result {count} times. "
        "Stop repeating it unchanged; use the result already provided or try a different query."
    ),
    "same_tool_failure_halt": (
        "Stopped {tool_name}: it failed {count} times this turn. "
        "Stop retrying the same failing tool path and choose a different approach."
    ),
    "repeated_exact_failure_warning": (
        "{tool_name} has failed {count} times with identical arguments. This looks like a loop; "
        "inspect the error and change strategy instead of retrying it unchanged."
    ),
    "idempotent_no_progress_warning": (
        "{tool_name} returned the same result {count} times. Use the result already provided "
        "or change the query instead of repeating it unchanged."
    ),
    "identical_call_streak_halt": (
        "Stopped {tool_name}: the same call with identical arguments returned the same result "
        "{count} times in a row. Stop repeating it unchanged; use the result already provided or change strategy."
    ),
    "identical_cycle_halt": (
        "Stopped {tool_name}: the same repeating cycle of tool calls (period {period}) with identical "
        "arguments and identical results has run {count} times. Repeating the batch unchanged is not "
        "progress; use the results already provided or change strategy."
    ),
    "loop_web_search_cap": (
        "Blocked web_search: this turn has already made {cap} web searches, the per-turn limit. "
        "This looks like a runaway search loop. Work with the results you already have and give the user your answer."
    ),
    "loop_subagent_cap": (
        "Blocked delegate_task: this turn has already spawned {count} subagents (limit {cap}). "
        "This looks like a runaway delegation loop. Finish the work with the results you have and answer the user."
    ),
}

_IDENTICAL_CALL_NOTICE = (
    "[hermes note: this is the {ordinal} consecutive identical call to "
    "{tool_name} with identical arguments returning the same result. "
    "Do not repeat it — change arguments, use a different tool, or "
    "proceed with what you have.]"
)

_IDENTICAL_CYCLE_NOTICE = (
    "[hermes note: the last {count} rounds repeated the same cycle of {period} tool calls "
    "(ending with {tool_name}) with identical arguments and identical results. "
    "Do not repeat the batch — change arguments, use a different tool, or "
    "proceed with what you have.]"
)

# tool -> (LoopCapConfig field, controller counter attribute, decision code)
_LOOP_CAPS: dict[str, tuple[str, str, str]] = {
    "web_search": ("max_web_searches", "_turn_web_search_count", "loop_web_search_cap"),
    "delegate_task": ("max_subagents", "_turn_subagent_count", "loop_subagent_cap"),
}


class ToolCallGuardrailController:
    """Per-turn controller for repeated failed/non-progressing tool calls."""

    def __init__(self, config: ToolCallGuardrailConfig | None = None):
        self.config = config or ToolCallGuardrailConfig()
        self.reset_for_turn()

    def reset_for_turn(self) -> None:
        self._exact_failure_counts: dict[ToolCallSignature, int] = {}
        self._same_tool_failure_counts: dict[str, int] = {}
        # signature -> a mutating call succeeded since its last failure
        self._progress_since_failure: dict[ToolCallSignature, bool] = {}
        self._no_progress: dict[ToolCallSignature, tuple[str, int]] = {}
        self._halt_decision: ToolGuardrailDecision | None = None
        # Identical-call streak: CONSECUTIVE identical (tool, args, result) calls; any different call or
        # result resets it, so re-reads after edits and varied polling are never flagged.
        # Identical-call loop-breaker state (agent.stall_guards): tracks the CONSECUTIVE streak of identical
        # (tool, canonical args) calls whose results were also identical. Per-turn, like everything else
        # here. NOTE: open PR #85352 (patrykkopycinski) tracks no-progress loops ACROSS turns via a
        # detection window — a different mechanism from this per-turn consecutive streak. Coordinate future
        # work there.
        self._identical_streak_sig: ToolCallSignature | None = None
        self._identical_streak_result_hash: str = ""
        self._identical_streak_count: int = 0
        self._identical_streak_first_call_id: str = ""
        # Batch-cycle loop breaker (port of can1357/oh-my-pi#10521): sequence of
        # (signature, result_hash, repeatable) for every observed call this turn, so a repeating
        # multi-call cycle (A,B,A,B,...) is caught even though it resets the consecutive streak above.
        self._call_history: deque[tuple[ToolCallSignature, str, bool]] = deque(maxlen=_STALL_GUARD_CYCLE_HISTORY)
        # tool_call_id -> spillover path, so a stub referencing a persisted-output preview can't dangle.
        self._persisted_result_paths: dict[str, str] = {}
        self._turn_web_search_count = 0
        self._turn_subagent_count = 0

    @property
    def halt_decision(self) -> ToolGuardrailDecision | None:
        return self._halt_decision

    def _decide(
        self, action: str, code: str, tool_name: str, count: int, signature: ToolCallSignature,
        *, message: str | None = None, **fmt: Any,
    ) -> ToolGuardrailDecision:
        """Build a warn/block/halt decision; block/halt is also recorded as the turn's halt decision."""
        if message is None:
            message = _DECISION_MESSAGES[code].format(tool_name=tool_name, count=count, **fmt)
        decision = ToolGuardrailDecision(action, code, message, tool_name, count, signature)
        if decision.should_halt:
            self._halt_decision = decision
        return decision

    def before_call(self, tool_name: str, args: Mapping[str, Any] | None) -> ToolGuardrailDecision:
        args = _coerce_args(args)
        signature = ToolCallSignature.from_call(tool_name, args)
        allow = ToolGuardrailDecision(tool_name=tool_name, signature=signature)

        # Loop caps apply regardless of hard_stop_enabled (which only governs the detector).
        cap_block = self._check_loop_cap(tool_name, args, signature)
        if cap_block is not None or not self.config.hard_stop_enabled:
            return cap_block or allow
        # A mutation since this call last failed makes the retry a new experiment.
        exact_count = 0 if self._progress_since_failure.get(signature) else self._exact_failure_counts.get(signature, 0)
        if exact_count >= self.config.exact_failure_block_after:
            return self._decide("block", "repeated_exact_failure_block", tool_name, exact_count, signature)
        record = self._no_progress.get(signature) if self._is_idempotent(tool_name) else None
        if record is not None and record[1] >= self.config.no_progress_block_after:
            return self._decide("block", "idempotent_no_progress_block", tool_name, record[1], signature)
        return allow

    def after_call(
        self, tool_name: str, args: Mapping[str, Any] | None, result: str | None,
        *, failed: bool | None = None,
    ) -> ToolGuardrailDecision:
        args = _coerce_args(args)
        signature = ToolCallSignature.from_call(tool_name, args)
        if failed is None:
            failed, _ = classify_tool_failure(tool_name, result)
        warnings = self.config.warnings_enabled

        if failed:
            # An identical failing call is only a REPLAY if nothing landed in between;
            # a mutation since the last identical failure restarts the exact-args streak.
            if self._progress_since_failure.pop(signature, False):
                self._exact_failure_counts.pop(signature, None)
            exact_count = self._exact_failure_counts[signature] = self._exact_failure_counts.get(signature, 0) + 1
            same_count = self._same_tool_failure_counts[tool_name] = self._same_tool_failure_counts.get(tool_name, 0) + 1
            self._no_progress.pop(signature, None)
            # same_tool_failure counts DIFFERENT args on one tool; for failure-tolerant
            # tools a run of distinct red commands is diagnosis, not a loop — warn, never halt.
            if (
                # Hard-stop widening (#89069 / #100849 bundle): the per-turn no-progress BLOCK above only
                # covers tools in idempotent_tools, so a model replaying the same successful
                # `terminal`/`skill_view` call with a byte-identical result ran until the iteration budget.
                # The consecutive-identical streak is tool-agnostic; when hard stops are enabled, halt at
                # the same idempotent_no_progress threshold. Pollers stay exempt (an unchanged poll is
                # progress).
                self.config.hard_stop_enabled
                and tool_name not in FAILURE_TOLERANT_TOOL_NAMES
                and same_count >= self.config.same_tool_failure_halt_after
            ):
                return self._decide("halt", "same_tool_failure_halt", tool_name, same_count, signature)
            if warnings and exact_count >= self.config.exact_failure_warn_after:
                return self._decide("warn", "repeated_exact_failure_warning", tool_name, exact_count, signature)
            if warnings and same_count >= self.config.same_tool_failure_warn_after:
                return self._decide(
                    "warn", "same_tool_failure_warning", tool_name, same_count, signature,
                    message=_tool_failure_recovery_hint(tool_name, same_count),
                )
            return ToolGuardrailDecision(tool_name=tool_name, count=exact_count, signature=signature)

        self._exact_failure_counts.pop(signature, None)
        self._same_tool_failure_counts.pop(tool_name, None)
        # A successful mutation is progress for every failing signature still counted
        # this turn. Pure loops never mutate between attempts, so the replay detector keeps its teeth.
        if tool_name in PROGRESS_RESET_TOOL_NAMES or file_mutation_result_landed(tool_name, result):
            self._progress_since_failure.update(dict.fromkeys(self._exact_failure_counts, True))
            self._same_tool_failure_counts.clear()
        if not self._is_idempotent(tool_name):
            self._no_progress.pop(signature, None)
            return ToolGuardrailDecision(tool_name=tool_name, signature=signature)

        result_hash = _result_hash(result, tool_name)
        previous = self._no_progress.get(signature)
        repeat_count = previous[1] + 1 if previous is not None and previous[0] == result_hash else 1
        self._no_progress[signature] = (result_hash, repeat_count)
        if warnings and repeat_count >= self.config.no_progress_warn_after:
            return self._decide("warn", "idempotent_no_progress_warning", tool_name, repeat_count, signature)
        return ToolGuardrailDecision(tool_name=tool_name, count=repeat_count, signature=signature)

    def _is_idempotent(self, tool_name: str) -> bool:
        return tool_name not in self.config.mutating_tools and tool_name in self.config.idempotent_tools

    def observe_call(
        self, tool_name: str, args: Mapping[str, Any] | None, result: str | None,
        *, tool_call_id: str = "", failed: bool = False,
    ) -> IdenticalCallObservation:
        """Track consecutive identical calls; return notice + dedupe stub info.

        ``notice`` fires from the threshold-th consecutive identical (tool, args, result) call
        (observational, pollers exempt). ``stub`` replaces the CURRENT result from the 2nd byte-identical
        repeat — the tool still executed, only the context representation is deduplicated, so polling
        semantics survive; pollers are NOT exempt here since an unchanged poll is where it saves most.
        """
        is_plain_str = isinstance(result, str)
        signature = ToolCallSignature.from_call(tool_name, _coerce_args(args))
        result_hash = _result_hash(result, tool_name) if is_plain_str else ""

        if is_plain_str and (signature, result_hash) == (self._identical_streak_sig, self._identical_streak_result_hash):
            self._identical_streak_count += 1
        else:
            # New streak; non-string (multimodal) results never form one.
            self._identical_streak_sig = signature if is_plain_str else None
            self._identical_streak_result_hash = result_hash
            self._identical_streak_count = 1 if is_plain_str else 0
            self._identical_streak_first_call_id = tool_call_id or ""
        count = self._identical_streak_count

        notice = kind = None
        if not is_stall_guard_repeatable(tool_name) and count >= STALL_GUARD_IDENTICAL_CALL_THRESHOLD:
            notice, kind = _IDENTICAL_CALL_NOTICE.format(ordinal=_ordinal(count), tool_name=tool_name), "identical_call_streak"
            # The no-progress BLOCK in before_call only covers idempotent_tools; this streak
            # is tool-agnostic, so with hard stops on, halt at the same threshold (a model
            # replaying a successful `terminal` call otherwise runs to the budget).
            if self.config.hard_stop_enabled and count >= self.config.no_progress_block_after and self._halt_decision is None:
                self._decide("halt", "identical_call_streak_halt", tool_name, count, signature)

        # Batch-cycle detection (oh-my-pi#10521): a repeating multi-call cycle resets the
        # consecutive streak on every alternation, so check the call history for a period-p lap.
        if is_plain_str:
            self._call_history.append((signature, result_hash, is_stall_guard_repeatable(tool_name)))
        else:
            self._call_history.clear()
        if notice is None and is_plain_str:
            cycle = self._detect_identical_cycle()
            if cycle is not None:
                period, laps = cycle
                notice, kind = _IDENTICAL_CYCLE_NOTICE.format(count=laps, period=period, tool_name=tool_name), "identical_cycle"
                if self.config.hard_stop_enabled and laps >= self.config.no_progress_block_after and self._halt_decision is None:
                    self._decide("halt", "identical_cycle_halt", tool_name, laps, signature, period=period)

        stub = None
        if is_plain_str and count >= 2 and not failed and len(result) >= IDENTICAL_RESULT_STUB_MIN_CHARS:
            stub = self._build_result_reference_stub(tool_name, args)
        return IdenticalCallObservation(notice=notice, stub=stub, kind=kind)

    def _detect_identical_cycle(self) -> tuple[int, int] | None:
        """Detect a repeating identical-call cycle ending at the latest observed call.

        Returns ``(period, laps)`` for the smallest period 2..max whose trailing laps
        (identical signature AND result per position) reach the notice threshold, else None.
        Period 1 is the consecutive streak's job. A cycle made ONLY of poller-exempt tools
        is exempt (an unchanged poll loop is legitimate waiting); one non-exempt call in
        the cycle keeps the guard armed, matching the single-call exemption semantics.
        """
        history = self._call_history
        for period in range(2, _STALL_GUARD_MAX_CYCLE_PERIOD + 1):
            if len(history) < period * STALL_GUARD_IDENTICAL_CALL_THRESHOLD:
                continue
            laps = 1
            # Count how many consecutive trailing laps equal the final lap.
            while True:
                base = len(history) - period * (laps + 1)
                if base < 0:
                    break
                lap_equal = all(
                    history[base + i][:2] == history[len(history) - period + i][:2]
                    for i in range(period)
                )
                if not lap_equal:
                    break
                laps += 1
            if laps >= STALL_GUARD_IDENTICAL_CALL_THRESHOLD:
                tail = [history[len(history) - period + i] for i in range(period)]
                if all(repeatable for _, _, repeatable in tail):
                    continue
                # A constant sub-cycle would already have fired at a smaller period.
                return period, laps
        return None

    def record_persisted_result(self, tool_call_id: str, file_path: str) -> None:
        """Remember the spillover path a persisted result was saved to."""
        if tool_call_id and file_path:
            self._persisted_result_paths[tool_call_id] = file_path

    def _build_result_reference_stub(self, tool_name: str, args: Mapping[str, Any] | None) -> str:
        """Reference stub for a byte-identical duplicate result (tool + args preview)."""
        args_preview = canonical_tool_args(_coerce_args(args))
        if len(args_preview) > _RESULT_STUB_ARGS_PREVIEW_CHARS:
            args_preview = args_preview[:_RESULT_STUB_ARGS_PREVIEW_CHARS] + "…"
        first_id = self._identical_streak_first_call_id
        ref = f" (tool_call_id {first_id})" if first_id else ""
        stub = (
            f"[hermes note: this result is byte-identical to the {tool_name} "
            f"result earlier this turn{ref}. Refer to that result; it has not "
            f"changed. Args: {args_preview}]"
        )
        spill_path = self._persisted_result_paths.get(first_id) if first_id else None
        if spill_path:
            stub += f"\n[The referenced result was persisted to: {spill_path} — page through it with read_file if you need the full content.]"
        return stub

    def _check_loop_cap(
        self, tool_name: str, args: Mapping[str, Any], signature: ToolCallSignature,
    ) -> ToolGuardrailDecision | None:
        """Block once a per-turn cap is reached (BEFORE the call, so the (cap+1)-th is refused), else advance
        the counter and return None. delegate_task control actions spawn nothing and keep working after the cap."""
        spec = _LOOP_CAPS.get(tool_name)
        if spec is None:
            return None
        cap_field, count_attr, code = spec
        cap, count = getattr(self.config.loop_caps, cap_field), getattr(self, count_attr)
        increment = 1 if tool_name == "web_search" else (_subagent_spawn_count(args) if cap else 0)
        if increment and cap and count >= cap:
            return self._decide("block", code, tool_name, count, signature, cap=cap)
        setattr(self, count_attr, count + increment)
        return None


def toolguard_synthetic_result(decision: ToolGuardrailDecision) -> str:
    """Build a synthetic role=tool content string for a blocked tool call."""
    return json.dumps({"error": decision.message, "guardrail": decision.to_metadata()}, ensure_ascii=False)


def append_toolguard_guidance(result: str, decision: ToolGuardrailDecision) -> str:
    """Append runtime guidance to the current tool result content."""
    if decision.action not in {"warn", "halt"} or not decision.message:
        return result
    label = "Tool loop hard stop" if decision.action == "halt" else "Tool loop warning"
    return (result or "") + f"\n\n[{label}: {decision.code}; count={decision.count}; {decision.message}]"


def _tool_failure_recovery_hint(tool_name: str, count: int) -> str:
    """Action-oriented guidance for recovering from repeated tool failures."""
    common = (
        f"{tool_name} has failed {count} times this turn. This looks like a loop. "
        "Do not switch to text-only replies; keep using tools, but diagnose before retrying. "
        "First inspect the latest error/output and verify your assumptions. "
    )
    if tool_name == "terminal":
        return common + (
            "For terminal failures, run a small diagnostic such as `pwd && ls -la` "
            "in the same tool, then try an absolute path, a simpler command, a different "
            "working directory, or a different tool such as read_file/write_file/patch."
        )
    return common + (
        "Try different arguments, a narrower query/path, an absolute path when relevant, "
        "or a different tool that can make progress. If the blocker is external, report "
        "the blocker after one diagnostic attempt instead of repeating the same failing path."
    )


def _ordinal(count: int) -> str:
    return f"{count}{'th' if 11 <= count % 100 <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(count % 10, 'th')}"


def _coerce_args(args: Mapping[str, Any] | None) -> Mapping[str, Any]:
    return args if isinstance(args, Mapping) else {}


# execute_code reports per-call kernel bookkeeping — a running `kernel.execution_count` and wall-clock
# `duration_seconds` — that changes on every invocation even when the code did the same thing. Hashed
# as-is, every replay of an identical empty probe looks new and the identical-call streak never forms
# (a model re-ran one empty execute_code call 147 times unflagged). Only these known locations in
# execute_code's own result shape are dropped: for any other tool the same key names can be real output.
def _without_execute_code_metadata(parsed: Any) -> Any:
    if not isinstance(parsed, dict):
        return parsed
    cleaned = {k: v for k, v in parsed.items() if k != "duration_seconds"}
    kernel = cleaned.get("kernel")
    if isinstance(kernel, dict):
        cleaned["kernel"] = {k: v for k, v in kernel.items() if k != "execution_count"}
    return cleaned


def _result_hash(result: str | None, tool_name: str = "") -> str:
    parsed = safe_json_loads(result or "")
    if parsed is None:
        return _sha256(result or "")
    if tool_name == "execute_code":
        parsed = _without_execute_code_metadata(parsed)
    return _sha256(_canonical_json(parsed))


_BOOL_WORDS = {w: True for w in ("1", "true", "yes", "on", "enabled")} | {w: False for w in ("0", "false", "no", "off", "disabled")}


def _as_bool(value: Any, default: bool) -> bool:
    if isinstance(value, (bool, int, float)):
        return bool(value)
    if isinstance(value, str):
        return _BOOL_WORDS.get(value.strip().lower(), default)
    return default


def _int_at_least(value: Any, default: int, minimum: int) -> int:
    """junk/None/below-minimum fall back to default (caps use minimum 0 so 0 = disabled)."""
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed >= minimum else default


def _subagent_spawn_count(args: Mapping[str, Any]) -> int:
    """Subagents one delegate_task call spawns: ``len(tasks)`` for a non-empty batch, else 1; control actions 0."""
    if str(args.get("action") or "").strip().lower() in ("list", "steer", "stop"):
        return 0
    tasks = args.get("tasks")
    return len(tasks) if isinstance(tasks, list) and tasks else 1


def _sha256(value: str) -> str:
    # surrogatepass: web-scraped results can carry unpaired UTF-16 surrogates; a
    # strict encode would raise and take down the conversation loop.
    return hashlib.sha256(value.encode("utf-8", "surrogatepass")).hexdigest()


# ---------------------------------------------------------------------------
# Progressive Evaluation & Multi-Level Authorization Guardrails (Req 1, 3, 6, 14)
# ---------------------------------------------------------------------------

_GREETING_WORDS = frozenset({
    "hola", "buenos dias", "buenos días", "buenas tardes", "buenas noches",
    "hey", "hi", "hello", "que tal", "qué tal", "como estas", "cómo estás",
    "saludos", "buenas", "que mas", "qué más"
})

_GREETING_PATTERN = re.compile(
    r"\b(?:" + "|".join(re.escape(g) for g in sorted(_GREETING_WORDS, key=len, reverse=True)) + r")\b",
    re.IGNORECASE
)

_ACK_WORDS = frozenset({
    "gracias", "muchas gracias", "ok", "okay", "vale", "entendido", "perfecto",
    "buenísimo", "buenisimo", "de acuerdo", "excelente", "dale", "listo"
})

_SPEED_OR_PING_PATTERN = re.compile(
    r"\b(?:prueba|test|testear|probar)\s+(?:de\s+|tu\s+|su\s+|la\s+|el\s+)?(?:velocidad|latencia|respuesta|tiempo)|"
    r"(?:medir|mide)\s+(?:el\s+)?tiempo|\bping\b|\bpong\b",
    re.IGNORECASE
)

_FUTURE_INTENTION_PATTERN = re.compile(
    r"\b(?:mañana|luego|después|despues|más tarde|mas tarde|la próxima semana|proxima semana)\s+"
    r"(?:quiero|vamos|hacemos|trabajamos|revisamos|veremos|vemos)\b",
    re.IGNORECASE
)

_FILE_OR_URL_PATTERN = re.compile(
    r"https?://|\b[\w\-\./]+\.(?:py|sh|json|yaml|yml|md|txt|csv|pdf|docx|xlsx|png|jpg|jpeg|mp3|mp4|log|ts|js|html|css)\b|"
    r"(?:^|\s)(?:/[a-zA-Z0-9_\-\.]+)+",
    re.IGNORECASE
)

_ACTION_DIRECTIVES = re.compile(
    r"\b(?:crea|crear|haz|hacer|modifica|modificar|edita|editar|actualiza|actualizar|"
    r"borra|borrar|elimina|eliminar|ejecuta|ejecutar|instala|instalar|configura|configurar|"
    r"busca|buscar|encuentra|analiza|analizar|revisa|revisar|lee|leer|escribe|escribir|"
    r"redacta|redactar|traduce|traducir|optimiza|optimizar|audita|auditar|diseña|diseñar|"
    r"planifica|planificar|estructura|estructurar|genera|generar|explícame|explicame|explica|explicar|"
    r"ayúdame|ayudame|ayuda|propuesta|campaña|guion|copy|contrato|sorteo|coljuegos|arquitectura|protocolo|skill|"
    r"recuerda|recuerdas|acuerda|acuerdas|recuerde|recuerden|"
    r"despliega|deploy|repara|arregla|corrige|reinicia|reiniciar|"
    r"procede|proceder|continua|continúa|continuar|sigue|seguir|adelante|"
    r"proceso|procesos|tarea|tareas|avance|avances|progreso|estado|status|reporte|reportes|medir|mide|cuéntame|cuenta|novedad|novedades)\b",
    re.IGNORECASE
)

_SYSTEM_METADATA_WRAPPER_PATTERN = re.compile(
    r"\[System:.*?\]",
    re.DOTALL | re.IGNORECASE
)

_CONFIRMATION_PATTERNS = re.compile(
    r"\b(?:si|sí|dale|adelante|procede|proceder|confirmo|confirmado|hazlo|ejecuta|ejecútalo|"
    r"yes|ok|okay|proceed|go ahead|aplica|aplicalo|aplícalo|de acuerdo|perfecto procede)\b",
    re.IGNORECASE
)

_MUTATING_OR_DESTRUCTIVE_COMMANDS = re.compile(
    r"""(?:^|\s|&&|\|\||;|`)(?:
        rm\s|rmdir\s|mv\s|cp\s|install\s|sed\s+-i|truncate\s|dd\s|shred\s|
        git\s+(?:commit|push|reset|clean|checkout|rebase|merge)\s|
        docker\s+(?:rm|kill|stop|restart|build|run|compose\s+(?:down|up))\s|
        systemctl\s|service\s|kill\s|pkill\s|shutdown\s|reboot\s|
        pip\s+install|npm\s+(?:install|run\s+build)|apt-get|apt\s
    )""",
    re.VERBOSE | re.IGNORECASE
)

_IMPERATIVE_COMMANDS = re.compile(
    r"\b(?:crea|escribe|modifica|edita|actualiza|borra|elimina|ejecuta|instala|despliega|agrega|cambia|aplica|haz)\b",
    re.IGNORECASE
)

_CASUAL_INQUIRY_PATTERN = re.compile(
    r"^(?:(?:hola|hey|buenas|buenos dias|buenas tardes|buenas noches)\b(?:\s+\w+)?\s*)?"
    r"(?:"
    r"qui[eé]n\s+(?:eres|sos)|"
    r"c[oó]mo\s+(?:est[aá]s|andas|te\s+va)|"
    r"c[oó]mo\s+va(?:\s+(?:todo|la\s+cosa))?\s*$|"
    r"qu[eé]\s+(?:haces|tal|cuentas|hac[eé]s)|"
    r"me\s+(?:escuchas|o[yí]es)|"
    r"pod[eé]s\s+hablar|puedes\s+hablar"
    r")\b",
    re.IGNORECASE
)


def classify_turn_intent(message_text: str) -> str:
    """Classify the user turn intent as 'conversational' or 'action'.

    Tier 0 (Fast-path): File attachments, URLs, file paths, ping tests, explicit action directives.
    Tier 1 (Semantic ONNX Triage): Evaluates message embedding on CPU.
    Tier 2 (Heuristic Fallback): Safe heuristic rules if ONNX runtime is unavailable.
    """
    if not message_text or not isinstance(message_text, str):
        return "action"

    # Strip synthetic system injection wrappers before intent classification
    stripped = _SYSTEM_METADATA_WRAPPER_PATTERN.sub("", message_text).strip()
    if not stripped:
        return "action"

    text = stripped

    # 1. Any file attachment, local path, or URL is an action turn
    if _FILE_OR_URL_PATTERN.search(text):
        return "action"

    # 2. Response speed / latency / ping tests are strictly conversational
    if _SPEED_OR_PING_PATTERN.search(text):
        return "conversational"

    # 3. Statements of future intention without immediate command -> conversational (Plan Req 3)
    if _FUTURE_INTENTION_PATTERN.search(text):
        return "conversational"

    # 3b. Explicit action/editorial/domain directives must keep tools (including skill_route) available
    has_action = bool(_ACTION_DIRECTIVES.search(text))
    if has_action:
        return "action"

    # 4. Semantic ONNX Intent Triage (Fast CPU probe)
    try:
        from agent.semantic_triage import classify_semantic_intent
        semantic_res = classify_semantic_intent(text)
        if semantic_res is not None:
            return semantic_res
    except Exception as e:
        logger.debug("Semantic intent triage unavailable or failed: %s; falling back to heuristics", e)

    # 5. Clean string for keyword analysis fallback
    clean = re.sub(r"[^\w\s]", " ", text).lower().strip()
    words = clean.split()
    if not words:
        return "action"

    # 7. Acknowledgements or greetings without actions -> conversational
    has_greeting = bool(_GREETING_PATTERN.search(clean))
    has_ack = any(clean == ack or clean.startswith(ack + " ") or clean.endswith(" " + ack) for ack in _ACK_WORDS)

    if (has_greeting or has_ack) and not has_action:
        return "conversational"

    # 8. Casual questions without action verbs (e.g. "¿cómo estás?", "¿quién eres?")
    is_casual_inquiry = bool(_CASUAL_INQUIRY_PATTERN.match(clean))
    if is_casual_inquiry and not has_action:
        return "conversational"

    # Default to action if intent is ambiguous or complex
    return "action"


def is_conversational_turn(message_text: str) -> bool:
    """Check if the user message is a pure greeting or casual chit-chat without an actionable task."""
    return classify_turn_intent(message_text) == "conversational"


def should_decouple_tools_for_turn(
    messages: list[Any],
    tool_turns: int = 0,
    agent: Any = None,
) -> bool:
    """Determine whether tool schemas should be decoupled (tools_for_api = []) for this turn.

    Decoupling saves ~13,600 tokens and ~8-10 seconds of provider latency on conversational turns.
    """
    # 1. Mid-turn tool responses MUST keep tools available (call count > 1)
    if tool_turns > 1:
        return False

    if not messages:
        return False

    # 2. Never decouple for cronjobs or autonomous subagents
    if agent is not None:
        if getattr(agent, "is_cron", False) or getattr(agent, "_delegate_depth", 0) > 0:
            return False

    # 3. Check the last message in history
    last_msg = messages[-1]
    last_role = getattr(last_msg, "role", None) if not isinstance(last_msg, dict) else last_msg.get("role")
    if last_role in ("tool", "function"):
        return False
    if last_role == "assistant":
        # If assistant just called a tool, we cannot decouple
        if isinstance(last_msg, dict) and last_msg.get("tool_calls"):
            return False
        if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
            return False

    # 4. Extract last user text
    last_user_text = ""
    for msg in reversed(messages):
        role = getattr(msg, "role", None) if not isinstance(msg, dict) else msg.get("role")
        if role == "user":
            content = getattr(msg, "content", None) if not isinstance(msg, dict) else msg.get("content")
            if isinstance(content, str):
                last_user_text = content
            elif isinstance(content, list):
                # Multipart content (e.g. image, document attachment) -> Keep tools!
                for part in content:
                    if isinstance(part, dict):
                        if part.get("type") != "text":
                            return False
                        last_user_text += " " + part.get("text", "")
            break

    if not last_user_text:
        return False

    return classify_turn_intent(last_user_text) == "conversational"


def has_user_confirmation(messages: list[Any]) -> bool:
    """Check if recent user turns contain explicit confirmation or direct imperative command."""
    if not messages:
        return False
    user_turns: list[str] = []
    for msg in reversed(messages):
        role = getattr(msg, "role", None) if not isinstance(msg, dict) else msg.get("role")
        if role == "user":
            content = getattr(msg, "content", None) if not isinstance(msg, dict) else msg.get("content")
            if isinstance(content, str):
                user_turns.append(content)
            elif isinstance(content, list):
                text_parts = [c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"]
                user_turns.append(" ".join(text_parts))
            if len(user_turns) >= 3:
                break

    for turn in user_turns:
        clean_turn = turn.strip().lower()
        if _CONFIRMATION_PATTERNS.search(clean_turn):
            return True
        # If the turn is an open question or inquiry, it is NOT an authorization
        is_question = "?" in turn or "¿" in turn or bool(
            re.match(r"^(?:qué|que|cómo|como|cuál|cual|por qué|será|podríamos|podemos)\b", clean_turn)
        )
        if is_question:
            continue
        # Check for direct imperative action command
        if _IMPERATIVE_COMMANDS.search(clean_turn) and len(clean_turn.split()) >= 3:
            return True
    return False


def check_runtime_execution_guardrails(
    agent: Any,
    tool_name: str,
    tool_args: Mapping[str, Any] | None,
    messages: list[Any] | None = None,
) -> tuple[bool, str | None]:
    """Universal runtime interceptor enforcing 5-State Progressive Evaluation and Multi-Level Authorization.

    Enforces:
    - State 1: Suppresses tool executions on pure greetings/chit-chat for immediate conversational Fast Ack (<2s).
    - State 4: Intercepts high-impact mutating actions (file/system edits) until explicit user confirmation is present.
    """
    # 1. Bypass guardrails for cronjobs and autonomous subagent execution
    if getattr(agent, "is_cron", False) or getattr(agent, "_delegate_depth", 0) > 0:
        return False, None

    tool_args = tool_args or {}
    messages = messages or getattr(agent, "messages", []) or []

    # Extract the last user message text
    last_user_text = ""
    for msg in reversed(messages):
        role = getattr(msg, "role", None) if not isinstance(msg, dict) else msg.get("role")
        if role == "user":
            content = getattr(msg, "content", None) if not isinstance(msg, dict) else msg.get("content")
            if isinstance(content, str):
                last_user_text = content
            elif isinstance(content, list):
                parts = [c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"]
                last_user_text = " ".join(parts)
            break

    # 2. State 1 Guardrail: Pure Conversation / Casual Greeting
    if is_conversational_turn(last_user_text):
        if tool_name in MUTATING_TOOL_NAMES or tool_name in ("memory", "search_files"):
            reason = (
                "INTERCEPTED (State 1: Pure Conversation): The user sent a casual greeting or conversational message. "
                "Do NOT execute tools, modify files, or scan memory. Respond conversationally, warmly, and immediately."
            )
            return True, reason

    # 3. State 4 Guardrail: Multi-Level Confirmation for High-Impact Actions
    is_high_impact = False
    if tool_name in ("write_file", "patch", "skill_manage", "cronjob_manage"):
        is_high_impact = True
    elif tool_name == "process_manage":
        if str(tool_args.get("action", "")).lower() in ("kill", "terminate", "stop"):
            is_high_impact = True
    elif tool_name in ("terminal", "execute_code"):
        cmd = str(tool_args.get("command") or tool_args.get("code") or "")
        if _MUTATING_OR_DESTRUCTIVE_COMMANDS.search(cmd):
            is_high_impact = True

    if is_high_impact:
        if not has_user_confirmation(messages):
            reason = (
                f"INTERCEPTED (State 4: High-Impact Action Requires Confirmation): "
                f"Tool '{tool_name}' mutates files, code, or systems. "
                f"You MUST first present your execution plan to the user with the proposed changes, "
                f"explain the expected outcome, and ask for explicit authorization ('dale' / 'sí' / 'procede') before executing."
            )
            return True, reason

    return False, None

