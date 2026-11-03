"""Unit tests for Model-Driven Routing (Option 2: Native Self-Escalation) and KV-Cache Stability."""

from types import SimpleNamespace

import agent.tool_guardrails as tg
from agent.tool_guardrails import apply_dynamic_turn_tiering, should_decouple_tools_for_turn


def test_no_keyword_classifiers_in_tool_guardrails():
    """Verify static regex/keyword classifiers are removed in favor of native model reasoning."""
    assert not hasattr(tg, "_L3_COMPLEXITY_PATTERNS")
    assert not hasattr(tg, "classify_turn_complexity")
    assert not hasattr(tg, "classify_turn_intent")
    assert not hasattr(tg, "check_runtime_execution_guardrails")


def test_should_decouple_tools_for_turn_always_preserves_kv_cache():
    """Verify tool schemas are never decoupled mid-session or on Turn 1 so KV-cache stays intact."""
    for content in (
        "Hola Roshi!",
        "Prueba de velocidad de respuesta",
        "El balance de ventas de ayer no cuadra con Stripe",
        "Diseña la arquitectura SDD para la migración multi-agente",
    ):
        messages = [{"role": "user", "content": content}]
        assert should_decouple_tools_for_turn(messages, tool_turns=0) is False
        assert should_decouple_tools_for_turn(messages, tool_turns=1) is False
        assert should_decouple_tools_for_turn(messages, tool_turns=2) is False


def test_native_self_escalation_keeps_primary_model_and_honors_failover():
    """Verify primary model stays constant across turns and only switches on active OpenCode-Go failover."""
    agent = SimpleNamespace(
        model="deepseek-v4-flash",
        provider="custom:nan-builders",
        requested_provider="NaN-Builders",
        reasoning_config={"enabled": True, "effort": "medium"},
        _dynamic_tiering_cfg={
            "fallback_go_model": "mimo-v2.6-flash",
        },
        _fallback_activated=False,
        _session_model_pinned=False,
        is_cron=False,
        _delegate_depth=0,
    )

    # Normal operation: model never swaps on short or long messages (preserves KV-cache)
    for text in (
        "Hola!",
        "El balance de ayer no cuadra",
        "Realiza una auditoría de arquitectura y causa raíz del sistema",
    ):
        res = apply_dynamic_turn_tiering(agent, [{"role": "user", "content": text}], tool_turns=0)
        assert res is None
        assert agent.model == "deepseek-v4-flash"
        assert agent.reasoning_config["effort"] == "medium"

    # Active failover to OpenCode-Go -> pins model to mimo-v2.6-flash so it does not bounce back
    agent._fallback_activated = True
    agent.provider = "custom:opencode-go"
    res_failover = apply_dynamic_turn_tiering(
        agent,
        [{"role": "user", "content": "Revisa el servicio systemd"}],
        tool_turns=0,
    )
    assert res_failover is not None
    assert res_failover["model"] == "mimo-v2.6-flash"
    assert res_failover["failover"] == "True"
    assert agent.model == "mimo-v2.6-flash"
