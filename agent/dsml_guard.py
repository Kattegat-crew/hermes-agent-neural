"""HERMES-DSML-GUARD: detect, recover and strip DeepSeek DSML tool-call markup that
leaked into assistant ``content`` as plain text.

DeepSeek V4 behind the NaN Builders proxy occasionally emits its native DSML tool-call
markup in ``content`` with an empty ``tool_calls`` array. Measured in production
(2026-10-14 → 2026-10-25): 56 leaks across 8 profiles, every one ending the turn with
zero tools executed while the user received raw markup. The proxy cannot be fixed
server-side (SSE rewrite), so the client filters here, at the single final-text choke
point (``agent.turn_final_response``).

Marker variants covered (upstream evidence: vllm #55954/#51914, sglang #40236,
openclaw #128858): double fullwidth ``<｜｜DSML｜｜`` (the production variant), single
fullwidth ``<｜DSML｜``, ASCII ``<||DSML||``, and the malformed ``<toolcalls>`` wrapper.
The dominant production shape is TRUNCATED (no closing tag), so detection cuts from the
first marker to the end of the text instead of requiring a balanced block.

A leak is only detected when a marker is followed by an invocation shape (``invoke`` or
``calls``), so prose that merely mentions the marker never triggers the guard.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import re
from types import SimpleNamespace
import time
from typing import Any, Iterable, Optional

logger = logging.getLogger("agent.conversation_loop")

# Opening shapes only: a DSML marker followed by an invocation keyword (partial
# keywords count — the dominant production leak is TRUNCATED mid-token), or the
# malformed toolcalls wrapper. A bare marker in prose (no invoke/calls shape) is NOT
# a leak.
_LEAK_START_RE = re.compile(
    r"<\s*[｜|]{1,2}\s*DSML[｜|]{1,2}\s*(?:inv(?:ok\w*)?|calls)"
    r"|<\s*toolcalls\s*>"
)
# Any DSML/toolcalls closing tag (invoke, calls, parameter — the block may end on the
# outermost one, so the caller takes the LAST close before the next block or EOS).
_LEAK_CLOSE_RE = re.compile(
    r"<\s*/\s*[｜|]{1,2}\s*DSML[｜|]{1,2}\s*\w+\s*>"
    r"|<\s*/\s*toolcalls\s*>"
)
_INVOKE_RE = re.compile(r'invoke\s+name="(?P<name>[^"]+)"')
# Wrapper openers (calls / toolcalls) bound a block; a bare `invoke` opener begins one
# only when no wrapper is present (the common truncated leak) — it must never bound the
# block it belongs to.
_WRAP_START_RE = re.compile(
    r"<\s*[｜|]{1,2}\s*DSML[｜|]{1,2}\s*calls"
    r"|<\s*toolcalls\s*>"
)
_LEAK_BLOCK_CLOSE_RE = re.compile(
    r"<\s*/\s*[｜|]{1,2}\s*DSML[｜|]{1,2}\s*(?:invok\w*|calls)\s*>"
    r"|<\s*/\s*toolcalls\s*>"
)
_DSML_PARAM_RE = re.compile(
    r'<\s*[｜|]{1,2}\s*DSML[｜|]{1,2}\s*parameter\s+name="(?P<name>[^"]+)"[^>]*>'
    r"(?P<val>.*?)"
    r"<\s*/\s*[｜|]{1,2}\s*DSML[｜|]{1,2}\s*parameter\s*>",
    re.S,
)
_XML_PARAM_RE = re.compile(
    r'<\s*parameter\s+name="(?P<name>[^"]+)"[^>]*>'
    r"(?P<val>.*?)"
    r"<\s*/\s*parameter\s*>",
    re.S,
)

# Re-prompt nudges: the model re-issues the call through the structured tool-call
# mechanism one API round later; the markup itself is never repeated back to the user.
DSML_REEMIT_NUDGE = (
    "Your previous response leaked a raw tool-call markup block (DSML) as plain text, "
    "so the tool was NOT executed. Re-issue exactly this call through the proper "
    "tool-call mechanism (structured call only, never as text): "
    'tool: "{name}", arguments: {arguments}. Do not repeat the markup.'
)
DSML_GENERIC_REEMIT_NUDGE = (
    "Your previous response leaked a raw tool-call markup block (DSML) as plain text "
    "and it could not be safely reconstructed, so the tool was NOT executed. Re-issue "
    "your intended tool call through the proper tool-call mechanism (structured call "
    "only, never markup). If no tool is needed, answer normally."
)


@dataclass
class DsmlGuardResult:
    """``response``: text with every leaked block removed (byte-identical when clean);
    ``leak_found``: whether any invocation-shaped DSML markup was present;
    ``reemit_call``: ``{"name", "arguments"}`` when a call was safely reconstructable
    (anti-ghost guards passed), else ``None``."""

    response: str
    leak_found: bool
    reemit_call: Optional[dict]


_CODE_FENCE_RE = re.compile(r"```|~~~")


def _code_fence_spans(text: str) -> list[tuple[int, int]]:
    """Spans of fenced code blocks (``` or ~~~ pairs): a leak-shaped example inside a
    fence is legitimate content (documenting this very bug) and must never trigger."""
    spans: list[tuple[int, int]] = []
    open_idx: Optional[int] = None
    fence: Optional[str] = None
    for m in _CODE_FENCE_RE.finditer(text):
        tok = m.group(0)
        if open_idx is None:
            open_idx, fence = m.start(), tok
        elif tok == fence:
            spans.append((open_idx, m.end()))
            open_idx, fence = None, None
    if open_idx is not None:
        spans.append((open_idx, len(text)))
    return spans


def _in_spans(idx: int, spans: list[tuple[int, int]]) -> bool:
    return any(start <= idx < end for start, end in spans)


def _leak_spans(text: str) -> list[tuple[int, int, bool]]:
    """Spans (start, end, closed) of every leaked block; a truncated block runs to EOS
    with ``closed=False``. ``closed`` requires a block-level close (``</…invoke>`` /
    ``</…calls>`` / ``</toolcalls>``) — a dangling parameter close alone means the
    invocation never completed, so nothing inside may be executed."""
    fences = _code_fence_spans(text)
    spans: list[tuple[int, int, bool]] = []
    pos = 0
    while True:
        m = _LEAK_START_RE.search(text, pos)
        if m is None:
            break
        if _in_spans(m.start(), fences):
            pos = m.end()
            continue
        nxt_wrap = _WRAP_START_RE.search(text, m.end())
        limit = nxt_wrap.start() if nxt_wrap else len(text)
        all_closes = list(_LEAK_CLOSE_RE.finditer(text, m.end(), limit))
        if all_closes:
            end = all_closes[-1].end()
            closed = bool(_LEAK_BLOCK_CLOSE_RE.search(text, m.end(), end))
            spans.append((m.start(), end, closed))
            pos = end
            continue
        spans.append((m.start(), len(text), False))
        break
    return spans


def _parse_params(block: str) -> Optional[dict]:
    """Parameter dict from a leaked block (DSML style first, XML style fallback), or
    ``None`` when any JSON-looking value fails to parse (anti-ghost guard)."""
    pairs = _DSML_PARAM_RE.findall(block) or _XML_PARAM_RE.findall(block)
    if not pairs:
        return None
    args: dict = {}
    for name, val in pairs:
        if val.lstrip().startswith(("{", "[")):
            try:
                args[name] = json.loads(val)
            except (ValueError, TypeError):
                return None
        else:
            args[name] = val
    return args


def apply_dsml_guard(response: str, valid_tool_names: Iterable[str]) -> DsmlGuardResult:
    """Detect leaked DSML blocks in ``response``; return the stripped text and, when a
    structurally CLOSED block reconstructs into a call whose tool is declared in
    ``valid_tool_names`` with JSON-safe arguments, the re-emit payload. Truncated blocks
    (the dominant production shape — a value cut mid-string must never be executed) are
    stripped but never re-emitted. Clean text passes through byte-identical."""
    text = response or ""
    spans = _leak_spans(text)
    if not spans:
        return DsmlGuardResult(response=text, leak_found=False, reemit_call=None)

    allowed = set(valid_tool_names or ())
    reemit: Optional[dict] = None
    for start, end, closed in spans:
        if not closed:
            continue  # anti-ghost guard #1: truncated block → layer 2 re-prompt, never execute
        block = text[start:end]
        inv = _INVOKE_RE.search(block)
        if inv is None:
            continue
        args = _parse_params(block)
        if args is None:
            continue  # unparseable args: never invent a call (anti-ghost guard)
        if inv.group("name") not in allowed:
            continue  # undeclared tool: never re-emit (anti-ghost guard)
        reemit = {"name": inv.group("name"), "arguments": args}
        break

    parts: list[str] = []
    cursor = 0
    for i, (start, end, _closed) in enumerate(spans):
        left = text[cursor:start].rstrip("\n")
        if left:
            parts.append(left)
        tail = text[end:]
        skipped = len(tail) - len(tail.lstrip("\n"))
        if left and tail.lstrip("\n"):
            parts.append("\n")
        cursor = end + skipped
        if i == len(spans) - 1:
            parts.append(text[cursor:])
    out = "".join(parts)
    return DsmlGuardResult(response=out, leak_found=True, reemit_call=reemit)


def build_reemit_nudge(reemit_call: Optional[dict]) -> str:
    """The user-role nudge for the bounded re-prompt: exact recovered call when the
    anti-ghost guards passed, generic otherwise."""
    if reemit_call:
        return DSML_REEMIT_NUDGE.format(
            name=reemit_call["name"],
            arguments=json.dumps(reemit_call["arguments"], ensure_ascii=False),
        )
    return DSML_GENERIC_REEMIT_NUDGE


def recover_leaked_tool_calls(agent: Any, assistant_message: Any) -> bool:
    """Layer 1 (intake): a response that leaked DSML markup into ``content`` with an
    EMPTY ``tool_calls`` array gets the reconstructed call injected as real
    ``tool_calls``, so the loop's tool dispatch (``run_tool_round``) executes it in the
    SAME turn at zero extra tokens. ``validate_tool_calls`` then treats it like any
    provider-emitted call (id uniquified, name checked against ``valid_tool_names``,
    args normalized). Returns ``True`` when a call was injected; content is left with
    the markup stripped so the user never sees it."""
    if getattr(assistant_message, "tool_calls", None):
        return False
    content = getattr(assistant_message, "content", None)
    if not isinstance(content, str) or not content:
        return False
    allowed = set(getattr(agent, "valid_tool_names", None) or ())
    guard = apply_dsml_guard(content, allowed)
    if not guard.leak_found or not guard.reemit_call:
        return False  # unrecoverable → the final-response layer re-prompts + strips
    assistant_message.tool_calls = [
        SimpleNamespace(
            id=f"call_dsml_{int(time.time() * 1000)}",
            type="function",
            function=SimpleNamespace(
                name=guard.reemit_call["name"],
                arguments=json.dumps(guard.reemit_call["arguments"], ensure_ascii=False),
            ),
        )
    ]
    assistant_message.content = guard.response or None
    assistant_message.finish_reason = "tool_calls"
    agent._dsml_guard_recovered = getattr(agent, "_dsml_guard_recovered", 0) + 1
    logger.warning(
        "HERMES-DSML-GUARD: DSML tool-call markup leaked into content — recovered call "
        "'%s' from text, executing in-turn (model=%s provider=%s, total recoveries=%d)",
        guard.reemit_call["name"], agent.model, agent.provider, agent._dsml_guard_recovered,
    )
    return True
