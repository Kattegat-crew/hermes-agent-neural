"""Localized, human-friendly labels for the gateway long-running heartbeat.

The heartbeat bubble (``"⏳ Working — N min — <action>"``) must never show raw
internal activity strings (``"receiving stream response"``) or bare tool names
(``"terminal"``) to the user.  This module maps the agent activity snapshot
(``AIAgent.get_activity_summary()``) to a short, localized phrase from the
``long_running.*`` i18n catalog.

The mapping is deliberately closed: an unknown tool or an unrecognized
activity description falls back to a generic phrase rather than echoing the
internal string.  The active language follows ``display.language`` (see
:mod:`agent.i18n`).
"""

from __future__ import annotations

from typing import Any, Mapping

from agent.i18n import t

# Tool name -> i18n key.  Families share one phrase; anything not listed falls
# back to ``long_running.action_tools`` (never the raw tool name).
_TOOL_ACTION_KEYS: dict[str, str] = {
    "terminal": "long_running.action_shell",
    "process_manage": "long_running.action_shell",
    "read_file": "long_running.action_files",
    "search_files": "long_running.action_files",
    "session_search": "long_running.action_files",
    "skill_view": "long_running.action_files",
    "skills_list": "long_running.action_files",
    "write_file": "long_running.action_writing",
    "patch": "long_running.action_writing",
    "skill_manage": "long_running.action_writing",
    "web_search": "long_running.action_web",
    "web_extract": "long_running.action_web",
    "browser_navigate": "long_running.action_web",
    "browser_click": "long_running.action_web",
    "browser_type": "long_running.action_web",
    "browser_scroll": "long_running.action_web",
    "browser_snapshot": "long_running.action_web",
    "vision_analyze": "long_running.action_vision",
    "execute_code": "long_running.action_code",
    "delegate_task": "long_running.action_delegation",
}

# Internal activity descriptions -> i18n key, matched as case-insensitive
# substrings in order (most specific first).
_DESC_ACTION_KEYS: tuple[tuple[str, str], ...] = (
    ("receiving stream response", "long_running.action_receiving"),
    ("waiting for provider response", "long_running.action_model"),
    ("waiting for non-streaming api response", "long_running.action_model"),
    ("local model loading", "long_running.action_model"),
    ("starting api call", "long_running.action_model"),
    ("executing tool:", "long_running.action_tools"),
    ("executing ", "long_running.action_tools"),
    ("tool completed:", "long_running.action_working"),
    ("tool results posted", "long_running.action_working"),
    ("api call", "long_running.action_working"),
)

# Activity descriptions that mean the run is parked on the human.  These get a
# dedicated heartbeat template ("⏳ Waiting for your reply — N min") instead of
# the generic "Working" line, so the bubble never claims progress while the
# agent is blocked on user input.
_WAIT_DESC_KINDS: tuple[tuple[str, str], ...] = (
    ("waiting for user clarify response", "clarify"),
    ("waiting for user approval", "approval"),
)


def _activity_desc(activity: Mapping[str, Any] | None) -> str:
    """Return the normalized activity description ('' when absent)."""
    if not activity:
        return ""
    return str(
        activity.get("last_activity_description")
        or activity.get("last_activity_desc")
        or ""
    ).strip().lower()


def wait_kind(activity: Mapping[str, Any] | None) -> str | None:
    """Return ``"clarify"``/``"approval"`` when the agent waits on the user.

    Returns ``None`` for every other activity.  Callers switch to a dedicated
    waiting template instead of the "Working" line — see the heartbeat in
    ``gateway/run.py``.
    """
    desc = _activity_desc(activity)
    for needle, kind in _WAIT_DESC_KINDS:
        if needle in desc:
            return kind
    return None


def activity_label(activity: Mapping[str, Any] | None) -> str:
    """Return a short localized label for the current agent activity.

    ``activity`` is the dict from ``AIAgent.get_activity_summary()`` (aliases
    ``last_activity_description`` / ``last_activity_desc`` are both accepted).
    Returns an empty string when there is nothing worth showing.
    """
    if not activity:
        return ""
    tool = str(activity.get("current_tool") or "").strip()
    if tool:
        key = _TOOL_ACTION_KEYS.get(tool)
        if key is None and tool.startswith("browser_"):
            key = "long_running.action_web"
        return t(key or "long_running.action_tools")
    desc = _activity_desc(activity)
    for needle, key in _DESC_ACTION_KEYS:
        if needle in desc:
            return t(key)
    return ""
