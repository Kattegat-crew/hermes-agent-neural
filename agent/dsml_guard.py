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

from dataclasses import dataclass, field
import json
import logging
import re
from types import SimpleNamespace
import time
from typing import Any, Iterable, List, Optional

logger = logging.getLogger("agent.conversation_loop")

# Opening shapes only: a DSML marker followed by an invocation keyword (partial
# keywords count — the dominant production leak is TRUNCATED mid-token), or the
# malformed toolcalls wrapper. A bare marker in prose (no invoke/calls shape) is NOT
# a leak.
_LEAK_START_RE = re.compile(
    r"<\s*[｜|]{1,2}\s*DSML\s*[｜|]{1,2}\s*(?:inv(?:ok\w*)?|tool_?calls|calls)"
    r"|<\s*toolcalls\s*>"
)
# Any DSML/toolcalls closing tag (invoke, calls, parameter — the block may end on the
# outermost one, so the caller takes the LAST close before the next block or EOS).
_LEAK_CLOSE_RE = re.compile(
    r"<\s*/\s*[｜|]{1,2}\s*DSML\s*[｜|]{1,2}\s*\w+\s*>"
    r"|<\s*/\s*[｜|]{1,2}\s*DSML\s*[｜|]{1,2}\s*/?\s*>"  # degraded streaming close (empty tag)
    r"|<\s*/\s*toolcalls\s*>"
)
_INVOKE_RE = re.compile(r'invoke\s+name="(?P<name>[^"]+)"')
# Wrapper openers (calls / toolcalls) bound a block; a bare `invoke` opener begins one
# only when no wrapper is present (the common truncated leak) — it must never bound the
# block it belongs to.
_WRAP_START_RE = re.compile(
    r"<\s*[｜|]{1,2}\s*DSML\s*[｜|]{1,2}\s*(?:tool_?calls|calls)"
    r"|<\s*toolcalls\s*>"
)
_LEAK_BLOCK_CLOSE_RE = re.compile(
    r"<\s*/\s*[｜|]{1,2}\s*DSML\s*[｜|]{1,2}\s*(?:invok\w*|tool_?calls|calls)\s*>"
    r"|<\s*/\s*toolcalls\s*>"
)
# Parameter openers (DSML-degraded and XML styles) — attrs captured to read the
# string="false" JSON-scalar flag. Real 47-case corpus (state.db, 14→25 oct): 43/47
# leaks have parameter openers with NO matching close, and the close of parameter N is
# FUSED with the open of N+1 as a hybrid '</…parameter name="k" …>' tag — the leading
# '/' is accepted so the hybrid opens the next parameter (it is also a value boundary
# via the nameless close alternative below). Values are parsed STRUCTURALLY, never by
# demanding </parameter>.
_DSML_PARAM_OPEN_RE = re.compile(
    r'<\s*/?\s*[｜|]{1,2}\s*DSML\s*[｜|]{1,2}\s*parameter\s+name="(?P<name>[^"]+)"(?P<attrs>[^>]*)>'
)
_XML_PARAM_OPEN_RE = re.compile(
    r'<\s*/?\s*parameter\s+name="(?P<name>[^"]+)"(?P<attrs>[^>]*)>'
)
# Where an unclosed parameter's value ends: any close tag (invoke, calls, parameter —
# including the hybrid '</…parameter name="k" …>' shape and the degraded empty
# '</…DSML…>' with NO keyword, real case R37), or the marker prefix of the next
# opener/wrapper.
_PARAM_VALUE_BOUNDARY_RE = re.compile(
    r"<\s*/\s*(?:[｜|]{1,2}\s*DSML\s*[｜|]{1,2}\s*)?(?:(?:invok\w*|tool_?calls|calls|parameter)[^>]*)?>"
    r"|<\s*[｜|]{1,2}\s*DSML\s*[｜|]{1,2}\s*(?:invok\w*|tool_?calls|calls)"
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
    ``reemit_call``: ``{"name", "arguments"}`` of the first safely reconstructable call
    (anti-ghost guards passed), else ``None``;
    ``reemit_calls``: ALL reconstructable calls in block order (a real closed block can
    carry 2–4 invokes; empty when none)."""

    response: str
    leak_found: bool
    reemit_call: Optional[dict]
    reemit_calls: list = field(default_factory=list)


_CODE_FENCE_RE = re.compile(r"```|~~~")
_INLINE_CODE_RE = re.compile(r"`[^`\n]+`")


def _code_fence_spans(text: str) -> list[tuple[int, int]]:
    """Spans of fenced code blocks (``` or ~~~ pairs) and inline code spans (`...`): a
    leak-shaped example inside either is legitimate content (documenting this very bug)
    and must never trigger. Observed live: an agent's own report mentioning the marker
    in inline code was truncated by the strip before inline spans were excluded."""
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
    fenced = list(spans)
    for m in _INLINE_CODE_RE.finditer(text):
        if not _in_spans(m.start(), fenced):
            spans.append((m.start(), m.end()))
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


def _parse_invoke_args(region: str) -> Optional[dict]:
    """Arguments for ONE invoke from its value region (text between the invoke opener
    and the next invoke opener / block end). Structural parsing per the real 47-case
    production corpus: parameters are usually NOT closed, so each value is bounded by
    the next opener or any close tag — never by a required ``</parameter>``. An invoke
    with no parameters is a legal call (arguments ``{}``). Returns ``None`` when a
    JSON-looking object/array value fails to parse (anti-ghost guard)."""
    openers = list(_DSML_PARAM_OPEN_RE.finditer(region))
    if not openers:
        openers = list(_XML_PARAM_OPEN_RE.finditer(region))
    if not openers:
        return {}  # empty invoke (real case R36): execute with empty arguments
    args: dict = {}
    for i, m in enumerate(openers):
        start = m.end()
        limit = openers[i + 1].start() if i + 1 < len(openers) else len(region)
        bm = _PARAM_VALUE_BOUNDARY_RE.search(region, start, limit)
        val = region[start:bm.start()] if bm else region[start:limit]
        stripped = val.lstrip()
        if stripped.startswith(("{", "[")):
            try:
                args[m.group("name")] = json.loads(val)
            except (ValueError, TypeError):
                return None  # broken JSON object/array: never invent a call
        elif 'string="false"' in (m.group("attrs") or ""):
            try:  # JSON scalar coercion ('10' → 10, 'true' → true); fallback str
                args[m.group("name")] = json.loads(val)
            except (ValueError, TypeError):
                args[m.group("name")] = val
        else:
            args[m.group("name")] = val
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
    reemit_calls: list = []
    for start, end, closed in spans:
        if not closed:
            continue  # anti-ghost guard #1: truncated block → layer 2 re-prompt, never execute
        block = text[start:end]
        invs = list(_INVOKE_RE.finditer(block))
        for j, inv in enumerate(invs):
            region_end = invs[j + 1].start() if j + 1 < len(invs) else len(block)
            args = _parse_invoke_args(block[inv.end():region_end])
            if args is None:
                continue  # unparseable JSON-looking args: never invent a call (anti-ghost)
            if inv.group("name") not in allowed:
                continue  # undeclared tool: never re-emit (anti-ghost guard)
            reemit_calls.append({"name": inv.group("name"), "arguments": args})
    reemit = reemit_calls[0] if reemit_calls else None

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
    return DsmlGuardResult(response=out, leak_found=True, reemit_call=reemit, reemit_calls=reemit_calls)


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
    calls: List[dict] = guard.reemit_calls or ([guard.reemit_call] if guard.reemit_call else [])
    if not calls:
        return False  # unrecoverable → the final-response layer re-prompts + strips
    now = int(time.time() * 1000)
    assistant_message.tool_calls = [
        SimpleNamespace(
            id=f"call_dsml_{now}_{i}",
            type="function",
            function=SimpleNamespace(
                name=call["name"],
                arguments=json.dumps(call["arguments"], ensure_ascii=False),
            ),
        )
        for i, call in enumerate(calls)
    ]
    assistant_message.content = guard.response or None
    assistant_message.finish_reason = "tool_calls"
    agent._dsml_guard_recovered = getattr(agent, "_dsml_guard_recovered", 0) + 1
    logger.warning(
        "HERMES-DSML-GUARD: DSML tool-call markup leaked into content — recovered %d "
        "call(s) '%s' from text, executing in-turn (model=%s provider=%s, total recoveries=%d)",
        len(calls), ", ".join(call["name"] for call in calls),
        agent.model, agent.provider, agent._dsml_guard_recovered,
    )
    return True
