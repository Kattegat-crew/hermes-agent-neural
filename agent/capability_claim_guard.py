"""Capability Claim Guard (CCG) — deterministic core.

F2 scope: evidence snapshot (T1), claim detector (T2), per-turn wiring (T3).
F3 scope: S1 delta holdback (T4), S2 interim gate (T5), S3 final seal + bounded
repair (T6), profile-scoped config (T7).
Spec: ``.specs/capability-claim-guard/01-spec.md`` (approved); design
``02-design.md`` §3-§6.

The guard answers one question deterministically: *can this session actually
reach the capability the model just denied having?* It never interprets
semantics — every decision is a set operation over a per-turn evidence
snapshot, and every failure mode is fail-open (no verdict, no intervention).

Lifecycle: one snapshot per turn (``agent._ccg_evidence``), captured at turn
start from the SESSION capability (``agent.tools`` — AC2: never the per-payload
``tools=``), reset on every turn even when disabled so nothing leaks across
turns or profiles.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional

log = logging.getLogger(__name__)

__all__ = [
    "CapabilityEvidence",
    "Verdict",
    "capture_evidence",
    "flush_stream_holdback",
    "interim_gate",
    "is_enabled",
    "record_observed_error",
    "record_tool_outcome",
    "repair_nudge",
    "scan_published_text",
    "seal_final_text",
    "stream_gate",
    "wire_turn",
]


# ── Evidence snapshot (T1) ───────────────────────────────────────────────


@dataclass
class CapabilityEvidence:
    """What this session can reach, for exactly one turn.

    ``holdback_chars``/``repair_limit``/``profile_home`` are captured WITH the
    snapshot so every later surface reads the options of the profile that owns
    the turn, never the ambient launch config (review finding 3).
    """

    turn_id: Any
    direct: frozenset = frozenset()
    deferred: frozenset = frozenset()
    aliases: dict = field(default_factory=dict)
    observed_errors: dict = field(default_factory=dict)
    holdback_chars: int = 200
    repair_limit: int = 2
    profile_home: Optional[str] = None


def _def_names(tool_defs) -> set:
    names = set()
    for td in tool_defs or ():
        if isinstance(td, dict):
            fn = td.get("function") or {}
            name = fn.get("name")
            if name:
                names.add(name)
    return names


def _known_registry_names() -> frozenset:
    """Registered tool names — a read of the registry's own bookkeeping, never
    a new global (E5) and never a definition/check call (E7)."""
    try:
        from tools.registry import registry

        return frozenset(getattr(registry, "_tools", {}))
    except Exception:
        log.debug("capability_claim_guard: registry read failed", exc_info=True)
        return frozenset()


def _deferrable_from_registry() -> frozenset:
    """Names tool_search could reach if they were not visible directly."""
    try:
        from tools.tool_search import is_deferrable_tool_name

        return frozenset(
            name for name in _known_registry_names() if is_deferrable_tool_name(name)
        )
    except Exception:
        log.debug("capability_claim_guard: deferrable scan failed", exc_info=True)
        return frozenset()


def _bridge_active(names: set) -> bool:
    from tools.tool_labels import BRIDGE_TOOL_NAMES

    return bool(names & BRIDGE_TOOL_NAMES)


def _session_aliases(universe) -> dict:
    """Alias → toolset → the session tools it names (review finding 2).

    Read from the live registry (no hardcoded table): an alias is only kept when
    it expands to at least one tool of THIS session's snapshot.
    """
    if not universe:
        return {}
    try:
        from tools.registry import registry

        get_aliases = getattr(registry, "get_registered_toolset_aliases", None)
        get_toolset = getattr(registry, "get_toolset_for_tool", None)
        if get_aliases is None or get_toolset is None:
            return {}
        by_toolset: dict = {}
        for name in universe:
            toolset = get_toolset(name)
            if toolset:
                by_toolset.setdefault(toolset, set()).add(name)
        aliases = {}
        for alias, toolset in dict(get_aliases() or {}).items():
            names = by_toolset.get(toolset)
            if names:
                aliases[str(alias)] = frozenset(names)
        return aliases
    except Exception:
        log.debug("capability_claim_guard: alias lookup failed", exc_info=True)
        return {}


def capture_evidence(
    agent,
    turn_id,
    tool_defs=None,
    deferred_names=None,
    aliases=None,
    holdback_chars=None,
    repair_limit=None,
    profile_home=None,
) -> Optional[CapabilityEvidence]:
    """Snapshot the session capability for one turn (fail-open: returns None
    instead of raising — AC7).

    ``tool_defs`` is a DI/fallback used ONLY when the agent exposes no
    ``.tools``; a per-payload tool list never narrows the session capability
    (AC2 decoupling).
    """
    try:
        session_tools = getattr(agent, "tools", None)
        defs = session_tools if session_tools is not None else (tool_defs or [])
        names = _def_names(defs)
        valid = getattr(agent, "valid_tool_names", None)
        direct = frozenset(valid) if valid else frozenset(names)
        if deferred_names is not None:
            deferred = frozenset(deferred_names)
        elif _bridge_active(names):
            deferred = _deferrable_from_registry() - direct
        else:
            deferred = frozenset()
        options = _guard_options(agent)
        if aliases is None:
            aliases = _session_aliases(direct | deferred)
        return CapabilityEvidence(
            turn_id=turn_id,
            direct=direct,
            deferred=deferred,
            aliases=dict(aliases or {}),
            holdback_chars=(
                _as_int(holdback_chars, options[1])
            ),
            repair_limit=_as_int(repair_limit, options[2]),
            profile_home=(
                str(profile_home)
                if profile_home is not None
                else (str(options[3]) if options[3] else None)
            ),
        )
    except Exception:
        log.warning("capability_claim_guard: evidence capture failed", exc_info=True)
        return None


def _as_int(value, fallback: int) -> int:
    try:
        if value is None:
            return fallback
        return max(0, int(value))
    except (TypeError, ValueError):
        return fallback


def record_observed_error(agent, tool_name: str, error) -> None:
    """Attach a real tool failure from this turn to the current snapshot
    (AC8). No-op without a snapshot."""
    evidence = getattr(agent, "_ccg_evidence", None)
    if evidence is not None:
        evidence.observed_errors[tool_name] = str(error)[:300]


def record_tool_outcome(agent, tool_name: str, result, *, is_error: bool, blocked: bool = False) -> None:
    """Record only a failure the DISPATCHER itself authenticated (finding 1).

    A page the model fetched, or text a user typed, can make ``_detect_tool_failure``
    fire on a substring; minting an "observed error" from that would let untrusted
    content authorize a false capability claim. Trust is therefore limited to the
    tool's own structured envelope: ``success: false``, a non-zero ``exit_code``,
    or an approval denial (``blocked``) — never free text.
    """
    evidence = getattr(agent, "_ccg_evidence", None)
    if evidence is None:
        return
    marker = "blocked" if blocked else _authenticated_failure(result, is_error)
    if marker is None:
        return
    try:
        evidence.observed_errors[str(tool_name)] = marker
    except Exception:  # pragma: no cover - snapshot is a plain dict
        log.debug("capability_claim_guard: outcome record failed", exc_info=True)


def _authenticated_failure(result, is_error: bool) -> Optional[str]:
    if not is_error:
        return None
    payload = result
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except (TypeError, ValueError):
            return None  # free text is not authenticated evidence
    if not isinstance(payload, Mapping):
        return None
    if payload.get("success") is False:
        return "error"
    exit_code = payload.get("exit_code")
    if isinstance(exit_code, int) and exit_code != 0:
        return "exit"
    return None


# ── Config gate (T7) ─────────────────────────────────────────────────────

_DEFAULT_HOLDBACK_CHARS = 200
_DEFAULT_REPAIR_LIMIT = 2


def _agent_home(agent):
    """Hermes home that owns this agent's session DB (``None`` when unknown).

    ``SessionDB`` lives at ``<hermes_home>/state.db``, so its parent IS the
    owning profile — the identity a multiplexed process cannot fake with ambient
    config or an inherited ``os.environ``.
    """
    db = getattr(agent, "_session_db", None)
    db_path = getattr(db, "db_path", None) if db is not None else None
    if not db_path:
        return None
    try:
        from pathlib import Path

        return Path(str(db_path)).expanduser().resolve().parent
    except (TypeError, ValueError, OSError):
        return None


def _load_config_for_home(home):
    from hermes_cli.config import load_config_readonly

    if home is None:
        return load_config_readonly()
    from hermes_constants import reset_hermes_home_override, set_hermes_home_override

    token = set_hermes_home_override(str(home))
    try:
        return load_config_readonly()
    finally:
        reset_hermes_home_override(token)


def _guard_options(agent=None):
    """``(enabled, holdback_chars, repair_limit, profile_home)`` for the
    profile that owns ``agent``. Unreadable config = all defaults = OFF.

    Read once per turn (the only caller is the turn hook), so the guard costs
    one config load per turn and nothing per delta: measured ~32 ms, against
    the multi-hundred-ms provider round trip each turn already pays. No module
    cache — a config edit, a test double or a second profile must be seen
    immediately, and gates read the per-turn snapshot instead of the config.
    """
    home = _agent_home(agent)
    fallback = (False, _DEFAULT_HOLDBACK_CHARS, _DEFAULT_REPAIR_LIMIT, home)
    try:
        config = _load_config_for_home(home)
        section = config.get("agent", {}) if isinstance(config, Mapping) else {}
        guard = section.get("capability_claim_guard", {}) if isinstance(section, Mapping) else {}
        if not isinstance(guard, Mapping):
            return fallback
        return (
            bool(guard.get("enabled", False)),
            _as_int(guard.get("holdback_chars"), _DEFAULT_HOLDBACK_CHARS),
            _as_int(guard.get("repair_limit"), _DEFAULT_REPAIR_LIMIT),
            home,
        )
    except Exception:
        log.warning(
            "capability_claim_guard: config read failed; guard disabled",
            exc_info=True,
        )
        return fallback


def is_enabled(agent=None) -> bool:
    """Config gate: ``agent.capability_claim_guard.enabled`` of the OWNING
    profile. Default off — an unreadable config is off (byte-identical runtime,
    AC1)."""
    return _guard_options(agent)[0]


def wire_turn(agent, turn_id) -> None:
    """Per-turn hook called from the conversation loop: reset any stale
    snapshot and turn state, then capture fresh evidence when the guard is
    enabled.

    Fail-open by construction (AC7) and always resets — a disabled turn must
    not inherit the previous turn's evidence.
    """
    agent._ccg_evidence = None
    _reset_agent_state(agent, turn_id)
    from agent.capability_claim_guard import capture_evidence, _guard_options  # patchable seam

    # One config read per turn: the options (enabled/holdback/repair_limit/profile home) are
    # resolved once here and travel INSIDE the snapshot, so no gate re-reads config per delta.
    enabled, holdback_chars, repair_limit, profile_home = _guard_options(agent)
    if not enabled:
        return
    try:
        agent._ccg_evidence = capture_evidence(
            agent,
            turn_id,
            holdback_chars=holdback_chars,
            repair_limit=repair_limit,
            profile_home=profile_home,
        )
    except Exception:
        agent._ccg_evidence = None
        log.warning(
            "capability_claim_guard: per-turn capture failed", exc_info=True
        )


def _reset_agent_state(agent, turn_id) -> None:
    agent._ccg_hold_parts = []
    agent._ccg_published_tail = ""
    agent._ccg_tainted = None
    agent._ccg_repairs = 0
    agent._ccg_repair_turn = turn_id

# ── Detector (T2) ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Verdict:
    kind: str
    tools: tuple = ()
    surface: str = "final"

    @property
    def intervene(self) -> bool:
        return self.kind.startswith("contradiction")


_CLEAN = Verdict("clean")

# Exempt spans, stripped before any matching (design §4 order): fenced code,
# structured tool_call envelopes, inline code, quoted speech.
_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
_ENVELOPE_RE = re.compile(r"\{(?:[^{}]|\{[^{}]*\})*\"name\"(?:[^{}]|\{[^{}]*\})*\}")
_INLINE_CODE_RE = re.compile(r"`[^`\n]+`")
_QUOTE_RE = re.compile(
    r"\"[^\n\"]+\"|«[^\n»]*»|“[^\n”]*”|‘[^\n’]*’"
)
# Sentences end on terminal punctuation only — a claim fragmented across
# streaming deltas may contain newlines, and it is scanned as one sentence.
_SENTENCE_SPLIT_RE = re.compile(r"[.!?]+")

# Hypothesis and permission/data speech-acts are never capability claims (R4.1).
_HYPOTHESIS_MARKERS = (
    "si tuviera", "si tuvies", "si contara", "si dispusi", "si dispon",
    "supongamos", "como si", "hipotetic", "en un mundo",
    "if i had", "if we had", "as if", "suppose", "supposing", "hypothetic",
    "were available",
)
_PERMISSION_MARKERS = (
    "permiso", "permission", "autorizad", "authorized", "credencial",
    "credential", "contraseña", "password", "tus datos", "sus datos",
    "your data", "acceso a tus", "acceso a sus", "api key", "api-key",
)

# Speech-act patterns: tool-availability negations, ES + EN (R4.2/R4.3).
_NEGATION_PATTERNS = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bno\s+(?:tengo|dispongo\s+de|cuento\s+con|hay|existe)\b[^.!?]*\bherramientas?\b",
        r"\bno\s+(?:tengo|dispongo\s+de|cuento\s+con)\b[^.!?]*\btools?\b",
        r"\bno\s+(?:tengo|dispongo\s+de|cuento\s+con)\b[^.!?]*\bfunciones?\b",
        r"\bno\s+(?:existe|hay)\s+(?:una\s+|un\s+|el\s+|la\s+|ninguna?\s+)?(?:herramienta|tool|funci[óo]n)\b",
        r"\bno\s+puedo\s+(?:enviar|leer|escribir|ejecutar|crear|buscar|acceder|usar|utilizar|programar|listar)\b",
        r"\bno\s+(?:me\s+)?es\s+posible\s+(?:enviar|leer|escribir|ejecutar|crear|buscar|usar)\b",
        r"\bi\s+(?:don't|do\s+not|cannot|can't)\s+have\b",
        r"\bthere(?:'s|\s+is|\s+are)\s+no\s+tools?\b",
        r"\bno\s+tools?\s+exists?\b",
        r"\bi\s+(?:cannot|can't)\s+(?:send|read|write|run|create|search|access|use|schedule|list)\b",
        r"\bi\s+don't\s+have\s+(?:any\s+)?(?:tools?|access)\b",
        r"\bwe\s+(?:don't|do\s+not)\s+have\s+(?:any\s+)?tools?\b",
    )
)

# "…herramienta de/para/que X" / "…tool for/to/that X" — the negation has a
# domain object; an object our lexicon cannot resolve is treated as absent
# (fail-open) instead of a generic denial.
_OBJECT_MARKER_RE = re.compile(
    r"herramientas?\s+(?:de|para|con|que)\b|\btools?\s+(?:for|to|that)\b"
)

# Specific terms → tool-name substrings: a concrete noun beats its family.
_SPECIFIC_TERMS = {
    "correo": ("email", "mail", "gmail"),
    "correos": ("email", "mail", "gmail"),
    "email": ("email", "mail", "gmail"),
    "emails": ("email", "mail", "gmail"),
    "gmail": ("gmail", "mail"),
    "telegram": ("telegram",),
    "whatsapp": ("whatsapp",),
    "slack": ("slack",),
    "discord": ("discord",),
    "tarea": ("kanban", "task", "todo"),
    "tareas": ("kanban", "task", "todo"),
    "kanban": ("kanban",),
    "task": ("task", "todo", "kanban"),
    "tasks": ("task", "todo", "kanban"),
    "programar": ("cron", "schedul", "job"),
    "programada": ("cron", "schedul", "job"),
    "programadas": ("cron", "schedul", "job"),
    "cron": ("cron", "job"),
    "schedule": ("schedul", "cron", "job"),
    "scheduled": ("schedul", "cron", "job"),
    "archivo": ("file", "read", "write", "edit"),
    "archivos": ("file", "read", "write", "edit"),
    "file": ("file",),
    "files": ("file",),
    "buscar": ("search",),
    "búsqueda": ("search",),
    "busqueda": ("search",),
    "search": ("search",),
    "memoria": ("memory",),
    "memory": ("memory",),
    "remember": ("memory",),
    "recordar": ("memory",),
    "navegador": ("browser", "navigate"),
    "browser": ("browser", "navigate"),
    "navigate": ("navigate", "browser"),
    "terminal": ("terminal", "shell", "exec", "command"),
    "comando": ("command", "terminal", "exec"),
    "comandos": ("command", "terminal", "exec"),
    "ejecutar": ("exec", "terminal", "shell", "command"),
    "shell": ("shell", "terminal"),
    "imagen": ("vision", "image"),
    "imágenes": ("vision", "image"),
    "imagenes": ("vision", "image"),
    "image": ("image", "vision"),
    "images": ("image", "vision"),
    "voz": ("tts", "speech", "voice"),
    "audio": ("audio", "tts", "voice"),
    "tts": ("tts", "speech"),
    "delegar": ("delegat", "subagent"),
    "delegación": ("delegat", "subagent"),
    "subagente": ("subagent", "delegat"),
    "subagentes": ("subagent", "delegat"),
    "subagent": ("subagent", "delegat"),
}

# Generic family terms → tool-name substrings (fallback when no specific term
# resolved a candidate). "mensajería" has no direct name, but its family does.
_FAMILY_TERMS = {
    "messaging": (
        "mensajería", "mensajeria", "mensajes", "mensaje", "messaging",
        "sms", "chat",
    ),
    "tasks": ("pendientes", "pending"),
    "terminal": ("código", "codigo", "code", "script"),
    "search": ("búsqueda", "busqueda"),
}
_FAMILY_TOOL_SUBSTRINGS = {
    "messaging": (
        "send", "message", "messaging", "mail", "email", "gmail", "telegram",
        "whatsapp", "slack", "discord", "sms", "notify", "notification",
    ),
    "tasks": ("kanban", "task", "todo", "schedul", "cron"),
    "terminal": ("terminal", "shell", "exec", "command", "code"),
    "search": ("search",),
    "files": ("file", "read", "write", "edit"),
    "memory": ("memory", "remember"),
    "browser": ("browser", "navigate", "web"),
    "vision": ("vision", "image"),
    "voice": ("tts", "speech", "voice", "audio"),
    "delegation": ("delegat", "subagent"),
}

# Specific term → its family: when a concrete noun resolves no tool directly
# ("telegram" names no registered tool), the family still does.
_TERM_FAMILY = {
    "correo": "messaging", "correos": "messaging", "email": "messaging",
    "emails": "messaging", "gmail": "messaging", "telegram": "messaging",
    "whatsapp": "messaging", "slack": "messaging", "discord": "messaging",
    "tarea": "tasks", "tareas": "tasks", "kanban": "tasks", "task": "tasks",
    "tasks": "tasks", "programar": "tasks", "programada": "tasks",
    "programadas": "tasks", "cron": "tasks", "schedule": "tasks",
    "scheduled": "tasks",
    "archivo": "files", "archivos": "files", "file": "files", "files": "files",
    "buscar": "search", "búsqueda": "search", "busqueda": "search",
    "search": "search",
    "memoria": "memory", "memory": "memory", "remember": "memory",
    "recordar": "memory",
    "navegador": "browser", "browser": "browser", "navigate": "browser",
    "terminal": "terminal", "comando": "terminal", "comandos": "terminal",
    "ejecutar": "terminal", "shell": "terminal",
    "imagen": "vision", "imágenes": "vision", "imagenes": "vision",
    "image": "vision", "images": "vision",
    "voz": "voice", "audio": "voice", "tts": "voice",
    "delegar": "delegation", "delegación": "delegation",
    "subagente": "delegation", "subagentes": "delegation",
    "subagent": "delegation",
}


def _strip_exempt_spans(text: str) -> str:
    text = _FENCE_RE.sub(" ", text)
    text = _ENVELOPE_RE.sub(" ", text)
    text = _INLINE_CODE_RE.sub(" ", text)
    text = _QUOTE_RE.sub(" ", text)
    return text


def _alias_tool_names(entry) -> tuple:
    """Alias payload: a tool name (legacy/DI) or a frozenset of tool names."""
    if isinstance(entry, str):
        return (entry,)
    try:
        return tuple(entry)
    except TypeError:
        return ()


def _resolve_candidates(low, universe, aliases, universe_direct=frozenset()):
    """Candidates a negated sentence refers to.

    Two layers, in this order:

    * **Concrete** — explicit tool names, registry aliases and ``_SPECIFIC_TERMS``
      (correo, tarea, archivo…). This is what the model actually named, so it wins.
    * **Family** — a family noun ("mensajería", "pendientes", "chat"…) names a
      capability the session may reach even when no concrete term resolved it. A
      sentence that denies two capabilities ("tareas ni mensajería") must answer
      both (review finding 4), so family hits STACK onto a concrete hit; a concrete
      hit with no family noun stays narrow ("programar correos" → the mail tool,
      never the chat one).

    Family hits prefer direct tools, because the family describes what the session
    visibly offers over the per-payload wire.
    """
    referenced = {name for name in universe if name in low}
    for alias, entry in aliases.items():
        if re.search(rf"\b{re.escape(str(alias))}\b", low):
            referenced |= {name for name in _alias_tool_names(entry) if name in universe}

    terms = [term for term in _SPECIFIC_TERMS if term in low]
    specific: set = set()
    if terms:
        subs = {sub for term in terms for sub in _SPECIFIC_TERMS[term]}
        specific = {name for name in universe if any(sub in name for sub in subs)}

    families = {
        family for term in terms if (family := _TERM_FAMILY.get(term))
    } | {
        family
        for family, terms_ in _FAMILY_TERMS.items()
        if any(term in low for term in terms_)
    }

    named = specific | referenced
    # Family-level nouns ("mensajería", "pendientes", "chat"…) name a capability the
    # session may reach even when their specific resolution found nothing; they stack
    # onto a concrete hit, because a sentence that denies two capabilities must answer
    # both (review finding 4). These never fire on their own when nothing else resolved
    # — that case is handled by the ``_TERM_FAMILY`` fallback below.
    explicit = [
        family for family, family_terms in _FAMILY_TERMS.items()
        if any(re.search(rf"\b{re.escape(term)}\b", low) for term in family_terms)
    ]
    if named and explicit:
        for family in explicit:
            subs = _FAMILY_TOOL_SUBSTRINGS.get(family, ())
            named |= {name for name in universe if any(sub in name for sub in subs)}
        return named, True
    if named:
        return named, bool(terms) or bool(families)

    family_candidates: set = set()
    for family in families:
        subs = _FAMILY_TOOL_SUBSTRINGS.get(family, ())
        family_candidates |= {name for name in universe if any(sub in name for sub in subs)}
    if family_candidates:
        direct_only = family_candidates & universe_direct
        if direct_only:
            family_candidates = direct_only
    return family_candidates, bool(terms) or bool(families)


def scan_published_text(evidence, text: str, surface: str = "final") -> Verdict:
    """Judge published assistant text against the turn's evidence snapshot.

    Fail-open everywhere (AC7): no snapshot, empty text, or an internal error
    all return a passing verdict.
    """
    if evidence is None or not isinstance(text, str) or not text.strip():
        return _CLEAN
    try:
        return _scan(evidence, text, surface)
    except Exception:
        log.warning("capability_claim_guard: scan failed", exc_info=True)
        return Verdict("clean", surface=surface)


def _scan(evidence, text: str, surface: str) -> Verdict:
    from tools.tool_labels import BRIDGE_TOOL_NAMES

    direct = frozenset(getattr(evidence, "direct", ()) or ()) - BRIDGE_TOOL_NAMES
    deferred = frozenset(getattr(evidence, "deferred", ()) or ())
    aliases = dict(getattr(evidence, "aliases", {}) or {})
    observed = getattr(evidence, "observed_errors", {}) or {}
    universe = direct | deferred

    for sentence in _SENTENCE_SPLIT_RE.split(_strip_exempt_spans(text)):
        low = sentence.lower()
        if not sentence.strip():
            continue
        if any(marker in low for marker in _HYPOTHESIS_MARKERS):
            continue
        if any(marker in low for marker in _PERMISSION_MARKERS):
            continue
        if not any(pattern.search(sentence) for pattern in _NEGATION_PATTERNS):
            continue

        candidates, had_terms = _resolve_candidates(
            low, universe, aliases, universe_direct=direct
        )
        if candidates:
            errored = {name for name in candidates if name in observed}
            remaining = candidates - errored
            if remaining & direct:
                return Verdict(
                    "contradiction_direct", tuple(sorted(remaining & direct)), surface
                )
            if remaining & deferred:
                return Verdict(
                    "contradiction_deferred",
                    tuple(sorted(remaining & deferred)),
                    surface,
                )
            return Verdict(
                "allowed_observed_error", tuple(sorted(errored)), surface
            )
        # Negation with no resolvable capability: a domain object we cannot
        # resolve is treated as genuinely absent (fail-open); a bare "I have
        # no tools" against a non-empty session contradicts the snapshot, and
        # the evidence is bounded so an unrelated tool can never be implied
        # (review finding 4).
        if _OBJECT_MARKER_RE.search(low) or had_terms or not direct:
            return Verdict("allowed_absent", (), surface)
        return Verdict("contradiction_direct", tuple(sorted(direct)[:5]), surface)

    return _CLEAN


# ── F3 surfaces: S1 delta holdback / S2 interim / S3 seal + repair ───────

# Cheap prefilter so an enabled-but-quiet stream never pays for the full scan:
# a window without any of these anchors cannot contain a capability negation.
_STREAM_ANCHORS = (
    "no tengo", "no dispongo", "no cuento", "no puedo", "no hay", "no existe",
    "no es posible", "ninguna herramienta", "ningún tool",
    "i don't", "i do not", "i cannot", "i can't", "there is no", "there's no",
    "no tools",
)
_PUBLISHED_TAIL_CHARS = 400


def _evidence_for(agent):
    return getattr(agent, "_ccg_evidence", None)


def _ensure_state(agent) -> None:
    """Lazily install the per-turn guard state (only reachable while enabled)."""
    if not isinstance(getattr(agent, "_ccg_hold_parts", None), list):
        agent._ccg_hold_parts = []
    if not isinstance(getattr(agent, "_ccg_published_tail", None), str):
        agent._ccg_published_tail = ""
    if not hasattr(agent, "_ccg_tainted"):
        agent._ccg_tainted = None
    if not isinstance(getattr(agent, "_ccg_repairs", None), int):
        agent._ccg_repairs = 0
    if not hasattr(agent, "_ccg_repair_turn"):
        agent._ccg_repair_turn = getattr(agent, "_current_turn_id", None)


def _scan_window(agent, evidence, text: str, surface: str):
    """Scan ``text`` with the already-published tail as context, so a denial
    split across the holdback boundary is still judged as one sentence."""
    tail = getattr(agent, "_ccg_published_tail", "") or ""
    context = tail[-_PUBLISHED_TAIL_CHARS:] + text
    low = context.lower()
    if not any(anchor in low for anchor in _STREAM_ANCHORS):
        return None
    return scan_published_text(evidence, context, surface=surface)


def _note_contradiction(agent, verdict, surface: str, evidence) -> None:
    agent._ccg_tainted = getattr(evidence, "turn_id", None) or getattr(
        agent, "_current_turn_id", None
    )
    agent._ccg_hold_parts = []  # never publish what we judged false
    log.warning(
        "capability_claim_guard: %s contradiction on %s (%s)",
        verdict.kind,
        surface,
        ", ".join(verdict.tools) or "-",
    )


def stream_gate(agent, text: str) -> str:
    """S1: return the prefix that may be published now (``""`` while held).

    Publication is monotonic — a frame is never retracted (prefix stability) —
    so the only safe correction is to stop publishing and let S3 repair.
    """
    if not text:
        return text
    evidence = _evidence_for(agent)
    if evidence is None:
        return text
    _ensure_state(agent)
    if agent._ccg_tainted is not None:
        return ""
    try:
        parts = agent._ccg_hold_parts
        parts.append(text)
        held = "".join(parts)
        window = _as_int(getattr(evidence, "holdback_chars", 0), _DEFAULT_HOLDBACK_CHARS)
        if len(held) <= window:
            return ""
        release, keep = held[:-window], held[-window:]
        agent._ccg_hold_parts = [keep]
        # Judge release + keep together: a denial that straddles the boundary must not be
        # published as two harmless halves (release ends mid-sentence, keep completes it).
        verdict = _scan_window(agent, evidence, release + keep, "stream")
        if verdict is not None and verdict.intervene:
            _note_contradiction(agent, verdict, "stream", evidence)
            return ""
        agent._ccg_published_tail = (
            (getattr(agent, "_ccg_published_tail", "") or "") + release
        )[-_PUBLISHED_TAIL_CHARS:]
        return release
    except Exception:
        log.warning("capability_claim_guard: stream gate failed", exc_info=True)
        held = "".join(getattr(agent, "_ccg_hold_parts", []) or [])
        agent._ccg_hold_parts = []
        return held


def flush_stream_holdback(agent) -> str:
    """End-of-response flush: publish what is still held, unless the turn was
    tainted (then the text is dropped and S3 produces the truthful output)."""
    parts = getattr(agent, "_ccg_hold_parts", None)
    if not parts:
        return ""
    agent._ccg_hold_parts = []
    _ensure_state(agent)
    if agent._ccg_tainted is not None:
        return ""
    held = "".join(part for part in parts if isinstance(part, str))
    if not held:
        return ""
    evidence = _evidence_for(agent)
    if evidence is not None:
        try:
            verdict = _scan_window(agent, evidence, held, "stream")
            if verdict is not None and verdict.intervene:
                _note_contradiction(agent, verdict, "stream", evidence)
                return ""
        except Exception:
            log.warning("capability_claim_guard: flush scan failed", exc_info=True)
    agent._ccg_published_tail = (
        (getattr(agent, "_ccg_published_tail", "") or "") + held
    )[-_PUBLISHED_TAIL_CHARS:]
    return held


def interim_gate(agent, text: str, *, already_streamed: bool = False) -> bool:
    """S2: may this interim/commentary text reach its surface?

    ``False`` suppresses text that was never shown; text already on screen is
    delivered (it cannot be retracted) and only registered as tainted.
    """
    evidence = _evidence_for(agent)
    if evidence is None or not isinstance(text, str) or not text.strip():
        return True
    _ensure_state(agent)
    try:
        verdict = scan_published_text(evidence, text, surface="interim")
    except Exception:
        log.warning("capability_claim_guard: interim scan failed", exc_info=True)
        return True
    if not verdict.intervene:
        return True
    _note_contradiction(agent, verdict, "interim", evidence)
    return bool(already_streamed)


def _repairs_used(agent, evidence) -> int:
    if getattr(agent, "_ccg_repair_turn", None) != getattr(evidence, "turn_id", None):
        agent._ccg_repair_turn = getattr(evidence, "turn_id", None)
        agent._ccg_repairs = 0
    try:
        return int(getattr(agent, "_ccg_repairs", 0) or 0)
    except (TypeError, ValueError):
        return 0


def repair_nudge(agent, text: str, *, surface: str = "final") -> Optional[str]:
    """S3a: a bounded (``repair_limit``) user-role message that forces a real
    verification call on the next loop iteration. ``None`` when the guard is
    off, the text is clean, or the budget is spent."""
    evidence = _evidence_for(agent)
    if evidence is None:
        return None
    _ensure_state(agent)
    try:
        verdict = scan_published_text(evidence, text, surface=surface)
        if not verdict.intervene:
            return None
        limit = _as_int(getattr(evidence, "repair_limit", 0), _DEFAULT_REPAIR_LIMIT)
        used = _repairs_used(agent, evidence)
        if used >= limit:
            return None
        agent._ccg_repairs = used + 1
        agent._ccg_tainted = getattr(evidence, "turn_id", None) or getattr(
            agent, "_current_turn_id", None
        )
        agent._ccg_hold_parts = []
        return _repair_message(verdict)
    except Exception:
        log.warning("capability_claim_guard: repair nudge failed", exc_info=True)
        return None


def seal_final_text(agent, text: str, *, surface: str = "final") -> str:
    """S3b: when the repair budget is spent, append a truthful, evidence-bounded
    verification clause. The model's own claim is never rewritten or hidden."""
    evidence = _evidence_for(agent)
    if evidence is None or not isinstance(text, str) or not text.strip():
        return text
    _ensure_state(agent)
    try:
        verdict = scan_published_text(evidence, text, surface=surface)
        if not verdict.intervene:
            return text
        clause = _seal_clause(verdict)
        if clause in text:
            return text
        agent._ccg_tainted = getattr(evidence, "turn_id", None) or getattr(
            agent, "_current_turn_id", None
        )
        log.warning(
            "capability_claim_guard: sealed final text (%s: %s)",
            verdict.kind,
            ", ".join(verdict.tools) or "-",
        )
        return f"{text.rstrip()}\n\n{clause}"
    except Exception:
        log.warning("capability_claim_guard: seal failed", exc_info=True)
        return text


def _fmt_tools(verdict) -> str:
    return ", ".join(verdict.tools) if verdict.tools else "las herramientas de esta sesión"


def _kind_label(kind: str) -> str:
    if kind == "contradiction_deferred":
        return "alcanzable vía tool_search"
    return "herramienta directa de la sesión"


def _repair_message(verdict) -> str:
    return (
        "Corrección de capacidad — verificación obligatoria. Tu respuesta anterior afirmó "
        "que no dispones de una capacidad que esta sesión sí expone: "
        f"{_fmt_tools(verdict)} ({_kind_label(verdict.kind)}). "
        "No lo repitas sin comprobarlo: verifica con una llamada real (la herramienta "
        "correspondiente, o tool_describe / tool_search para inspeccionar su esquema) y "
        "reporta el resultado exacto. Si el intento falla, comunica el error real; no "
        "anuncies acciones futuras sin ejecutarlas y no inventes herramientas ni "
        "disponibilidad."
    )


def _seal_clause(verdict) -> str:
    tools = _fmt_tools(verdict)
    if verdict.kind == "contradiction_deferred":
        return (
            f"[Verificación de capacidad] {tools} consta entre las herramientas "
            "alcanzables de esta sesión mediante tool_search. Si un intento falla, "
            "comunica el error real."
        )
    return (
        f"[Verificación de capacidad] {tools} consta en la lista de herramientas de "
        "esta sesión; si un intento falla, comunica el error real."
    )
