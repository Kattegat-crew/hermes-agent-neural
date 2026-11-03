"""Behaviour contract for the Capability Claim Guard detector (F2/T2).

Spec refs: ``.specs/capability-claim-guard/01-spec.md`` §6 (R4 rules + corpus)
and design ``02-design.md`` §4 (exemption order) / §6 (corpus classes).

Pinned behaviour (corpus classes from the approved spec):

* R4.2/R4.3: broad and specific tool-availability negations over a capability
  that IS in the session snapshot (direct or deferred) contradict the evidence.
* R4.1: permission / data / security negations never count as capability
  claims — quoted, fenced, inline-code, hypothesis and tool_call-envelope text
  is exempt.
* R4.5 (AC10): an empty tool_search result never implies tool absence; the
  detector fires on speech acts, not on lookup outcomes.
* AC8: a real observed error for the tool this turn makes its negation pass.
* AC7: a missing snapshot is fail-open (scan passes, no verdict).
* Claims split across streaming deltas are detected on the accumulated text.
"""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from agent.capability_claim_guard import scan_published_text


# ── Helpers ──────────────────────────────────────────────────────────────


def _tool_def(name):
    return {"type": "function", "function": {"name": name, "parameters": {"type": "object"}}}


def _make_evidence(tools, deferred=(), observed=None):
    from agent.capability_claim_guard import capture_evidence

    agent = SimpleNamespace()
    agent.tools = [_tool_def(name) for name in tools]
    agent.valid_tool_names = set(tools)
    evidence = capture_evidence(agent, "t", deferred_names=set(deferred))
    if observed:
        agent._ccg_evidence = evidence
        for tool, error in observed.items():
            from agent.capability_claim_guard import record_observed_error

            record_observed_error(agent, tool, error)
    return evidence


@pytest.fixture()
def evidence():
    """Standard snapshot: direct = send_message/kanban_list; deferred = email_send."""
    return _make_evidence(
        ["send_message", "kanban_list", "tool_search"], deferred={"email_send"}
    )


def _assert_contradiction(verdict, surface_text=""):
    assert verdict.intervene, (
        f"expected contradiction for {surface_text!r}, got {verdict.kind}"
    )
    assert verdict.tools, "contradiction must name the contradicting tools"


# ── Contradictions (direct capability) ───────────────────────────────────


class TestDirectContradictions:
    @pytest.mark.parametrize(
        "text",
        [
            "No tengo herramientas de mensajería para hacer eso.",
            "I don't have any messaging tools available.",
            "No puedo enviar Telegram desde aquí.",
            "I can't send Telegram messages right now.",
            "Lo siento, no dispongo de herramientas de tareas en esta sesión.",
            "No hay ninguna herramienta para listar tareas.",
        ],
    )
    def test_broad_and_specific_negations_contradict(self, evidence, text):
        _assert_contradiction(scan_published_text(evidence, text), text)

    def test_contradiction_names_direct_tool(self, evidence):
        verdict = scan_published_text(evidence, "No puedo enviar Telegram.")
        assert "send_message" in verdict.tools

    def test_generic_broad_denial_contradicts_nonempty_session(self, evidence):
        _assert_contradiction(scan_published_text(evidence, "No tengo herramientas."))

    def test_claim_split_across_streaming_deltas(self, evidence):
        """Fragmented claim, accumulated then scanned, still contradicts."""
        accumulated = "No tengo herramientas de\n kanban\n para listar tareas."
        _assert_contradiction(scan_published_text(evidence, accumulated), accumulated)

    def test_alias_reference_resolves_to_tool(self):
        ev = _make_evidence(["send_message", "kanban_list"])
        from agent.capability_claim_guard import capture_evidence

        agent = SimpleNamespace()
        agent.tools = [_tool_def("kanban_list")]
        agent.valid_tool_names = {"kanban_list"}
        ev = capture_evidence(agent, "t", aliases={"list": "kanban_list"})

        _assert_contradiction(scan_published_text(ev, "No puedo usar list ahora."))


# ── Contradictions (deferred capability) ─────────────────────────────────


class TestDeferredContradictions:
    @pytest.mark.parametrize(
        "text",
        [
            "No existe la herramienta para programar correos.",
            "There is no tool for sending emails.",
            "I don't have an email tool I could use here.",
        ],
    )
    def test_deferred_negation_contradicts(self, evidence, text):
        verdict = scan_published_text(evidence, text)
        _assert_contradiction(verdict, text)
        assert verdict.tools == ("email_send",)
        assert verdict.kind == "contradiction_deferred"


# ── Demonstrative objects (T10 canary finding E2) ────────────────────────


class TestDemonstrativeObjectIsGenericDenial:
    """A demonstrative after the preposition points back at the turn, not at an
    unresolvable domain object.

    Regression for the T10 canary (finding E2): ``tools for that`` /
    ``herramientas para eso`` matched the object marker, so the fail-open branch
    read the demonstrative as an unknown domain and published the denial raw.
    Against a non-empty snapshot these are generic denials and contradict it.
    """

    @pytest.mark.parametrize(
        "text",
        [
            "I don't have any tools for that.",
            "I don't have the tools for this.",
            "I don't have tools for those.",
            "I don't have any tools to do that.",
            "No tengo herramientas para eso.",
            "No tengo herramientas para hacer eso.",
            "No tengo herramientas para esto.",
            "No dispongo de herramientas de eso.",
            "No cuento con herramientas para esos.",
        ],
    )
    def test_demonstrative_object_contradicts(self, evidence, text):
        verdict = scan_published_text(evidence, text)
        assert verdict.kind == "contradiction_direct", (
            f"demonstrative object must not read as an unknown domain: {text!r} "
            f"-> {verdict.kind}"
        )
        _assert_contradiction(verdict, text)


class TestUnresolvableDomainObjectStaysFailOpen:
    """A named object the lexicon cannot resolve still fails open.

    The E2 fix must not turn every unresolvable subject into a contradiction:
    only a demonstrative erases the domain object.
    """

    @pytest.mark.parametrize(
        "text",
        [
            "No tengo herramientas para pilotar un dron.",
            "I don't have tools for knitting.",
            "No tengo herramientas para hacer pan.",
            "I don't have tools to do knitting.",
            "No tengo herramientas de astrofísica cuántica.",
            "No existe una herramienta que traduzca al klingon.",
            "There is no tool for translating to Klingon.",
        ],
    )
    def test_named_domain_object_stays_allowed_absent(self, evidence, text):
        verdict = scan_published_text(evidence, text)
        assert not verdict.intervene, (
            f"unresolvable domain object must stay fail-open: {text!r} -> {verdict.kind}"
        )
        assert verdict.kind == "allowed_absent"


# ── Allowed: capability genuinely absent ─────────────────────────────────


class TestAllowedAbsent:
    @pytest.mark.parametrize(
        "text",
        [
            "No tengo herramientas de astrofísica cuántica.",
            "No existe una herramienta que traduzca al klingon.",
            "There is no tool for translating to Klingon.",
        ],
    )
    def test_absent_capability_passes(self, evidence, text):
        verdict = scan_published_text(evidence, text)
        assert not verdict.intervene
        assert verdict.kind == "allowed_absent"


# ── Exemptions (R4.1) ────────────────────────────────────────────────────


class TestExemptions:
    @pytest.mark.parametrize(
        "text",
        [
            # quoted speech
            'El usuario dijo "no tengo herramientas de mensajería" y se le corrigió.',
            # inline code
            "Para negar: `no tengo herramientas de mensajería`.",
            # fenced block quoting a claim
            "```json\n{\"name\": \"send_message\", \"note\": \"no tengo herramientas\"}\n```",
            # hypothesis
            "Si tuviera herramientas de mensajería, las usaría.",
            "If I had messaging tools, I would use them.",
            # permission / data / security negations
            "No tengo permiso para usar herramientas de mensajería.",
            "I don't have permission to use messaging tools.",
            "No tengo acceso a tus datos personales.",
            "No tengo las credenciales de esa cuenta.",
            # structured tool_call envelope is not prose
            '{"name": "send_message", "arguments": {"text": "hola"}}',
        ],
    )
    def test_exempt_text_passes(self, evidence, text):
        verdict = scan_published_text(evidence, text)
        assert not verdict.intervene, (
            f"exempt text must pass (R4.1): {text!r} -> {verdict.kind}"
        )

    def test_empty_search_result_is_not_absence(self, evidence):
        """AC10/R4.5: citing an empty tool_search outcome is not a claim."""
        verdict = scan_published_text(
            evidence, "La búsqueda tool_search no encontró resultados para 'telegram api'."
        )
        assert not verdict.intervene


# ── Observed errors (AC8) ────────────────────────────────────────────────


class TestObservedErrors:
    def test_negation_with_real_error_passes(self):
        ev = _make_evidence(
            ["send_message", "kanban_list", "tool_search"],
            deferred={"email_send"},
            observed={"send_message": "TimeoutError: upstream"},
        )
        verdict = scan_published_text(ev, "No puedo enviar Telegram ahora mismo.")

        assert not verdict.intervene
        assert verdict.kind == "allowed_observed_error"


# ── Fail-open and misc ───────────────────────────────────────────────────


class TestFailOpen:
    def test_missing_snapshot_passes(self):
        verdict = scan_published_text(None, "No tengo herramientas de mensajería.")
        assert not verdict.intervene

    def test_empty_text_passes(self, evidence):
        assert not scan_published_text(evidence, "").intervene

    def test_surface_recorded(self, evidence):
        verdict = scan_published_text(
            evidence, "No puedo enviar Telegram.", surface="interim"
        )
        assert verdict.surface == "interim"
