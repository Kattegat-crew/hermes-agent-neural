"""HERMES-DSML-GUARD: DeepSeek DSML tool-call markup leaked into assistant content.

Measured in production (2026-10-14 → 2026-10-25): 56 leaks across 8 profiles, every one
with an empty ``tool_calls`` array — the markup reached users verbatim and zero tools ran.
The guard recovers the call via a bounded re-prompt and strips residue as a firewall.
"""

import json

import pytest
from types import SimpleNamespace

from agent.dsml_guard import apply_dsml_guard, recover_leaked_tool_calls

DOUBLE_FW_CLOSED = (
    'Voy a revisar los servicios.\n'
    '<｜｜DSML｜｜ calls>\n'
    '<｜｜DSML｜｜ invoke name="terminal">\n'
    '<｜｜DSML｜｜ parameter name="command" string="true">'
    'systemctl status nginx\n'
    '</｜｜DSML｜｜ parameter>\n'
    '</｜｜DSML｜｜ invoke>\n'
    '</｜｜DSML｜｜ calls>'
)

SINGLE_FW_TRUNCATED = (
    'Ejecuto la búsqueda.\n'
    '<｜DSML｜ invoke name="web_search">\n'
    '<｜DSML｜ parameter name="query" string="true">deepseek dsml leak'
)

ASCII_DOUBLE = (
    'Ok.\n<||DSML|| invoke name="terminal">\n'
    '<||DSML|| parameter name="command" string="true">date</||DSML|| parameter>\n'
    '</||DSML|| invoke>'
)

TOOLCALLS_TYPO = (
    'Hola.\n<toolcalls>\n<invoke name="terminal">\n'
    '<parameter name="command">uptime</parameter>\n</invoke>\n</toolcalls>'
)

VALID_TOOLS = {"terminal", "web_search", "web_extract"}


def test_clean_text_is_byte_identical_noop():
    text = "Respuesta normal con acentos y código: `x = <y>` sin marcadores."
    g = apply_dsml_guard(text, VALID_TOOLS)
    assert g.leak_found is False
    assert g.response == text
    assert g.reemit_call is None


def test_prose_mention_of_marker_without_invoke_shape_is_not_a_leak():
    # Discussing the bug itself must never trigger the guard.
    text = "El error muestra el token <｜DSML｜ dentro del content y el parser falla."
    g = apply_dsml_guard(text, VALID_TOOLS)
    assert g.leak_found is False
    assert g.response == text


def test_double_fullwidth_closed_block_recovers_call():
    g = apply_dsml_guard(DOUBLE_FW_CLOSED, VALID_TOOLS)
    assert g.leak_found is True
    assert g.reemit_call == {
        "name": "terminal",
        "arguments": {"command": "systemctl status nginx\n"},
    }
    assert "DSML" not in g.response
    assert "Voy a revisar los servicios." in g.response


def test_truncated_unclosed_block_strips_to_end():
    g = apply_dsml_guard(SINGLE_FW_TRUNCATED, VALID_TOOLS)
    assert g.leak_found is True
    assert g.reemit_call == {
        "name": "web_search",
        "arguments": {"query": "deepseek dsml leak"},
    }
    assert "Ejecuto la búsqueda." in g.response
    assert "DSML" not in g.response


def test_ascii_double_pipe_variant_recovers_call():
    g = apply_dsml_guard(ASCII_DOUBLE, VALID_TOOLS)
    assert g.leak_found is True
    assert g.reemit_call["name"] == "terminal"
    assert g.reemit_call["arguments"] == {"command": "date"}
    assert g.response.strip() == "Ok."


def test_toolcalls_typo_variant_recovers_call():
    g = apply_dsml_guard(TOOLCALLS_TYPO, VALID_TOOLS)
    assert g.leak_found is True
    assert g.reemit_call["name"] == "terminal"
    assert g.reemit_call["arguments"] == {"command": "uptime"}


def test_undeclared_tool_yields_no_reemit_call():
    g = apply_dsml_guard(DOUBLE_FW_CLOSED, {"other_tool"})
    assert g.leak_found is True
    assert g.reemit_call is None  # anti-ghost guard: never re-emit an undeclared tool


def test_invalid_json_argument_value_yields_no_reemit_call():
    text = (
        '<｜DSML｜ invoke name="web_search">\n'
        '<｜DSML｜ parameter name="query" string="true">{broken json'
        "</｜DSML｜ parameter>\n</｜DSML｜ invoke>"
    )
    g = apply_dsml_guard(text, VALID_TOOLS)
    assert g.leak_found is True
    assert g.reemit_call is None  # anti-ghost guard: args must be valid JSON


def test_multiple_leaked_blocks_all_stripped():
    text = DOUBLE_FW_CLOSED + "\n\n" + ASCII_DOUBLE
    g = apply_dsml_guard(text, VALID_TOOLS)
    assert g.leak_found is True
    assert "DSML" not in g.response
    assert g.reemit_call is not None


def test_undeclared_tool_still_strips_markup():
    g = apply_dsml_guard(DOUBLE_FW_CLOSED, set())
    assert g.leak_found is True
    assert "DSML" not in g.response
    assert g.reemit_call is None


def test_reemit_call_arguments_are_json_roundtrip_safe():
    g = apply_dsml_guard(DOUBLE_FW_CLOSED, VALID_TOOLS)
    json.dumps(g.reemit_call["arguments"])  # must not raise


# --- Layer 1 (intake): recover_leaked_tool_calls ---


def _fake_agent(tools=VALID_TOOLS):
    return SimpleNamespace(
        valid_tool_names=set(tools), model="glm5.3-flash", provider="custom",
        _dsml_guard_recovered=0,
    )


def _fake_message(content, tool_calls=None, finish_reason="stop"):
    return SimpleNamespace(content=content, tool_calls=tool_calls, finish_reason=finish_reason)


def test_intake_recovers_call_and_injects_tool_calls():
    agent = _fake_agent()
    msg = _fake_message(DOUBLE_FW_CLOSED)
    assert recover_leaked_tool_calls(agent, msg) is True
    assert msg.finish_reason == "tool_calls"
    assert len(msg.tool_calls) == 1
    tc = msg.tool_calls[0]
    assert tc.type == "function"
    assert tc.function.name == "terminal"
    assert json.loads(tc.function.arguments) == {"command": "systemctl status nginx\n"}
    assert "DSML" not in (msg.content or "")
    assert "Voy a revisar los servicios." in (msg.content or "")
    assert agent._dsml_guard_recovered == 1


def test_intake_skips_when_tool_calls_already_present():
    agent = _fake_agent()
    existing = [SimpleNamespace(id="call_1", type="function",
                                function=SimpleNamespace(name="terminal", arguments="{}"))]
    msg = _fake_message(DOUBLE_FW_CLOSED, tool_calls=existing)
    assert recover_leaked_tool_calls(agent, msg) is False
    assert msg.tool_calls is existing  # untouched


def test_intake_refuses_undeclared_tool():
    agent = _fake_agent(tools={"other_tool"})
    msg = _fake_message(DOUBLE_FW_CLOSED)
    assert recover_leaked_tool_calls(agent, msg) is False
    assert not msg.tool_calls
    assert "DSML" in msg.content  # untouched — final-response layer handles it


def test_intake_noop_on_clean_text():
    agent = _fake_agent()
    text = "Respuesta normal sin marcadores."
    msg = _fake_message(text)
    assert recover_leaked_tool_calls(agent, msg) is False
    assert msg.content == text
    assert msg.finish_reason == "stop"
