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

# Opening shapes only: a DSML marker followed by an invocation keyword, or the malformed
# toolcalls wrapper. A bare marker in prose (no invoke/calls) is NOT a leak.
_LEAK_START_RE = re.compile(
    r"<\s*[｜|]{1,2}\s*DSML[｜|]{1,2}\s*(?:invoke|calls)\b"
    r"|<\s*toolcalls\s*>"
)
# Any DSML/toolcalls closing tag (invoke, calls, parameter — the block may end on the
# outermost one, so the caller takes the LAST close before the next block or EOS).
_LEAK_CLOSE_RE = re.compile(
    r"<\s*/\s*[｜|]{1,2}\s*DSML[｜|]{1,2}\s*\w+\s*>"
    r"|<\s*/\s*toolcalls\s*>"
)
_INVOKE_RE = re.compile(r'invoke\s+name="(?P<name>[^"]+)"')
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
# Truncated leak: the param tag never closes and the value runs to the end of the
# block (the dominant production shape — markup cut mid-invocation).
_DSML_PARAM_TRUNC_RE = re.compile(
    r'<\s*[｜|]{1,2}\s*DSML[｜|]{1,2}\s*parameter\s+name="(?P<name>[^"]+)"[^>]*>'
    r"(?P<val>.*)$",
    re.S,
)
_XML_PARAM_TRUNC_RE = re.compile(
    r'<\s*parameter\s+name="(?P<name>[^"]+)"[^>]*>(?P<val>.*)$',
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


def _leak_spans(text: str) -> list[tuple[int, int]]:
    """Spans (start, end) of every leaked block; a truncated block runs to EOS."""
    spans: list[tuple[int, int]] = []
    pos = 0
    while True:
        m = _LEAK_START_RE.search(text, pos)
        if m is None or m.start() < pos:
            break
        nxt = _LEAK_START_RE.search(text, m.end())
        limit = nxt.start() if nxt else len(text)
        closes = list(_LEAK_CLOSE_RE.finditer(text, m.end(), limit))
        if closes:
            spans.append((m.start(), closes[-1].end()))
            pos = closes[-1].end()
        else:
            spans.append((m.start(), len(text)))
            break
    return spans


def _parse_params(block: str) -> Optional[dict]:
    """Parameter dict from a leaked block (DSML style first, XML style fallback), or
    ``None`` when any JSON-looking value fails to parse (anti-ghost guard)."""
    pairs = _DSML_PARAM_RE.findall(block) or _XML_PARAM_RE.findall(block)
    if not pairs:
        m = _DSML_PARAM_TRUNC_RE.search(block) or _XML_PARAM_TRUNC_RE.search(block)
        if m is None:
            return None
        pairs = [(m.group("name"), m.group("val"))]
    args: dict = {}
    for name, val in pairs:
        v = val
        if isinstance(val, tuple):
            # findall with named groups returns tuples; take the val group (last).
            v = val[-1]
        if v.lstrip().startswith(("{", "[")):
            try:
                args[name] = json.loads(v)
            except (ValueError, TypeError):
                return None
        else:
            args[name] = v
    return args


def apply_dsml_guard(response: str, valid_tool_names: Iterable[str]) -> DsmlGuardResult:
    """Detect leaked DSML blocks in ``response``; return the stripped text and, when a
    block reconstructs into a call whose tool is declared in ``valid_tool_names`` with
    JSON-safe arguments, the re-emit payload. Clean text passes through byte-identical."""
    text = response or ""
    spans = _leak_spans(text)
    if not spans:
        return DsmlGuardResult(response=text, leak_found=False, reemit_call=None)

    allowed = set(valid_tool_names or ())
    reemit: Optional[dict] = None
    for start, end in spans:
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

    cleaned = []
    cursor = 0
    for start, end in spans:
        cleaned.append(text[cursor:start])
        cursor = end
    cleaned.append(text[cursor:])
    out = re.sub(r"\n{3,}", "\n\n", "".join(cleaned))
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
