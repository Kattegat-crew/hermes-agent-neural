"""Unit tests for turn intent triage and dynamic tool decoupling (TDD).

Enforces:
- Conversational turns (greetings, response speed tests, chit-chat, future work notes)
  are classified as 'conversational' so tool schemas (~13k tokens) can be decoupled.
- Action turns (imperative commands, file inspections, code edits, attachments)
  are classified as 'action' so all tools remain available.
- Mid-turn tool executions never decouple tools.
"""

from agent.tool_guardrails import classify_turn_intent, should_decouple_tools_for_turn


def test_greetings_classified_as_conversational():
    assert classify_turn_intent("Hola") == "conversational"
    assert classify_turn_intent("Buenos días Roshi") == "conversational"
    assert classify_turn_intent("Hola Roshi, ¿cómo estás?") == "conversational"
    assert classify_turn_intent("Qué tal todo por ahí?") == "conversational"
    assert classify_turn_intent("buenas noches!") == "conversational"


def test_speed_and_ping_tests_classified_as_conversational():
    assert classify_turn_intent("Prueba de velocidad de respuesta") == "conversational"
    assert (
        classify_turn_intent(
            "Hola Roshi. Este mensaje es para probar tu velocidad de respuesta"
        )
        == "conversational"
    )
    assert classify_turn_intent("test de velocidad") == "conversational"
    assert classify_turn_intent("ping") == "conversational"


def test_future_work_and_acknowledgements_classified_as_conversational():
    # User Plan Requirement 3: statements of future work are conversational, not immediate execution
    assert (
        classify_turn_intent(
            "Hola Roshi, mañana quiero que trabajemos en los videos de Golden."
        )
        == "conversational"
    )
    assert classify_turn_intent("Perfecto, muchas gracias") == "conversational"
    assert classify_turn_intent("Dale, entendido") == "conversational"
    assert classify_turn_intent("Ok, después vemos eso") == "conversational"


def test_action_tasks_classified_as_action():
    assert classify_turn_intent("Lee el archivo config.yaml") == "action"
    assert classify_turn_intent("Revisa el log /var/log/syslog") == "action"
    assert (
        classify_turn_intent("Crea un script en python para ordenar la lista")
        == "action"
    )
    assert (
        classify_turn_intent("Busca en el proyecto dónde se define AIAgent")
        == "action"
    )
    assert classify_turn_intent("Ejecuta los tests de pytest") == "action"
    assert (
        classify_turn_intent("Hola Roshi, podés editar el archivo index.html?")
        == "action"
    )
    assert (
        classify_turn_intent("Modifica la función de login para validar el email")
        == "action"
    )


def test_attachment_or_file_paths_classified_as_action():
    assert classify_turn_intent("Hola, te paso el archivo reporte.pdf") == "action"
    assert classify_turn_intent("Mirá este archivo: datos.xlsx") == "action"
    assert classify_turn_intent("https://github.com/Kattegat-crew/hermes") == "action"


def test_should_decouple_tools_for_turn_evaluates_conversation_state():
    # Fresh greeting turn with tool_turns=0 or tool_turns=1 (1-indexed api_call_count in conversation loop)
    messages = [{"role": "user", "content": "Hola Roshi!"}]
    assert should_decouple_tools_for_turn(messages, tool_turns=0) is True
    assert should_decouple_tools_for_turn(messages, tool_turns=1) is True

    # Speed test with tool_turns=1
    messages = [
        {"role": "user", "content": "Prueba de velocidad de respuesta"}
    ]
    assert should_decouple_tools_for_turn(messages, tool_turns=0) is True
    assert should_decouple_tools_for_turn(messages, tool_turns=1) is True

    # Action task
    messages = [{"role": "user", "content": "Leé el archivo README.md"}]
    assert should_decouple_tools_for_turn(messages, tool_turns=0) is False
    assert should_decouple_tools_for_turn(messages, tool_turns=1) is False

    # Mid-turn tool execution (even if previous user message was conversational)
    messages = [
        {"role": "user", "content": "Hola"},
        {"role": "assistant", "content": None, "tool_calls": [{"id": "1", "function": {"name": "read_file"}}]},
        {"role": "tool", "tool_call_id": "1", "content": "file contents"},
    ]
    assert should_decouple_tools_for_turn(messages, tool_turns=1) is False

    # Subsequent API call within the same turn (tool_turns > 1)
    messages = [{"role": "user", "content": "Hola Roshi!"}]
    assert should_decouple_tools_for_turn(messages, tool_turns=2) is False

    # Multi-turn conversation with prior assistant reply MUST NOT decouple tools (preserves KV-cache prefix)
    multi_turn_messages = [
        {"role": "user", "content": "Revisa el estado del servidor"},
        {"role": "assistant", "content": "El servidor está activo."},
        {"role": "user", "content": "Perfecto, muchas gracias"},
    ]
    assert should_decouple_tools_for_turn(multi_turn_messages, tool_turns=0) is False
    assert should_decouple_tools_for_turn(multi_turn_messages, tool_turns=1) is False


def test_dynamic_turn_tiering_and_failover_awareness():
    from types import SimpleNamespace
    from agent.tool_guardrails import apply_dynamic_turn_tiering, classify_turn_complexity

    assert classify_turn_complexity([{"role": "user", "content": "Hola Roshi!"}], tool_turns=0) == "l1"
    assert classify_turn_complexity([{"role": "user", "content": "Revisa los logs de nginx"}], tool_turns=0) == "l2"
    assert (
        classify_turn_complexity(
            [{"role": "user", "content": "Diseña la arquitectura SDD y plan maestro para la migración multi-agente"}],
            tool_turns=0,
        )
        == "l3"
    )

    agent = SimpleNamespace(
        model="deepseek-v4-flash",
        provider="custom:nan-builders",
        requested_provider="NaN-Builders",
        reasoning_config={"enabled": True, "effort": "medium"},
        _dynamic_tiering_cfg={
            "enabled": True,
            "l1_conversational_model": "glm5.3-flash",
            "l1_reasoning_effort": "low",
            "l2_operational_model": "deepseek-v4-flash",
            "l2_reasoning_effort": "medium",
            "l3_architecture_model": "deepseek-v4-flash",
            "l3_reasoning_effort": "high",
            "fallback_go_model": "mimo-v2.6-flash",
        },
        _fallback_activated=False,
        _session_model_pinned=False,
        is_cron=False,
        _delegate_depth=0,
    )

    res_l1 = apply_dynamic_turn_tiering(agent, [{"role": "user", "content": "Hola!"}], tool_turns=0)
    assert res_l1["tier"] == "l1"
    assert agent.model == "glm5.3-flash"
    assert agent.reasoning_config["effort"] == "low"

    res_l3 = apply_dynamic_turn_tiering(
        agent,
        [{"role": "user", "content": "Realiza una auditoría de arquitectura y causa raíz del sistema"}],
        tool_turns=0,
    )
    assert res_l3["tier"] == "l3"
    assert agent.model == "deepseek-v4-flash"
    assert agent.reasoning_config["effort"] == "high"

    # Failover active -> keeps OpenCode-Go model (mimo-v2.6-flash)
    agent._fallback_activated = True
    agent.provider = "custom:opencode-go"
    res_failover = apply_dynamic_turn_tiering(
        agent,
        [{"role": "user", "content": "Revisa el servicio docker"}],
        tool_turns=0,
    )
    assert res_failover["model"] == "mimo-v2.6-flash"
    assert agent.model == "mimo-v2.6-flash"


def test_action_directives_include_continuation_and_confirmation():
    assert classify_turn_intent("listo procede") == "action"
    assert classify_turn_intent("dale continúa") == "action"
    assert classify_turn_intent("continua") == "action"
    assert classify_turn_intent("procede") == "action"
    assert classify_turn_intent("sigue adelante") == "action"


def test_system_metadata_and_substring_greetings_do_not_decouple_tools():
    # Words like 'this', 'which', 'history' must NOT trigger 'hi'
    assert classify_turn_intent("This is an important test") == "action"
    assert classify_turn_intent("Which directory contains the logs?") == "action"
    assert classify_turn_intent("History shows earlier errors") == "action"

    # Injected system wrapper + action command
    sys_msg = (
        "[System: The active model for this chat has changed to deepseek-v4-flash "
        "via provider custom:nan-builders. From this point forward, use this runtime metadata "
        "when answering questions about what model/provider is active.]\n\ncontinua"
    )
    assert classify_turn_intent(sys_msg) == "action"

    messages = [{"role": "user", "content": sys_msg}]
    assert should_decouple_tools_for_turn(messages, tool_turns=0) is False


def test_open_ended_technical_questions_do_not_decouple_tools():
    # Questions starting with cómo / qué that are technical tasks must remain 'action'
    assert classify_turn_intent("cómo soluciono este bug?") == "action"
    assert classify_turn_intent("qué falla en el log del servidor?") == "action"
    assert classify_turn_intent("cómo hago para levantar el contenedor?") == "action"
    assert classify_turn_intent("cómo podemos encarar esto?") == "action"
    assert classify_turn_intent("qué opciones tengo?") == "action"

    # Genuine casual inquiries about the bot remain 'conversational'
    assert classify_turn_intent("Hola Roshi, ¿cómo estás?") == "conversational"
    assert classify_turn_intent("¿Quién eres?") == "conversational"
    assert classify_turn_intent("me escuchas?") == "conversational"
    assert classify_turn_intent("¿cómo andas?") == "conversational"


