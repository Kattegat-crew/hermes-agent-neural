# 02-design — HERMES-DSML-GUARD

## Componentes
- `agent/dsml_guard.py` (nuevo, puro y sin dependencias del loop): detección por spans,
  parseo de invocaciones, guardias anti-fantasma, limpieza, recuperación. API:
  - `apply_dsml_guard(response, valid_tool_names) -> DsmlGuardResult(response, leak_found, reemit_call)`
  - `build_reemit_nudge(reemit_call) -> str`
  - `recover_leaked_tool_calls(agent, assistant_message) -> bool` (capa 1)
- `agent/turn_response_intake.py` — **capa 1 (nota de revisión Roshi)**: hook en
  `normalize_model_response` justo tras la coerción de contenido y ANTES del dispatch
  `run_tool_round if assistant_message.tool_calls else finish_text_response`
  (`conversation_loop.py:1685`): si el leak es reconstruible, se inyectan `tool_calls`
  reales (SimpleNamespace id/type/function{name, arguments JSON}, misma forma que el
  adaptador bedrock) → la herramienta corre EN EL MISMO TURNO a 0 tokens extra, y
  `validate_tool_calls` la valida como cualquier llamada del proveedor. El contenido
  queda con el markup strippeado antes de cualquier display/hook.
- `agent/turn_final_response.py` — capas 2 y 3 para lo que la capa 1 no recupera:
  1. Re-prompt acotado (2): assistant efímero (`_dsml_guard_nudge`, en
     `_EPHEMERAL_SCAFFOLDING_FLAGS`) + nudge user con la llamada reconstruida (o
     genérico) → `verdict("continue")`.
  2. Firewall: presupuesto agotado → `final_response` con markup eliminado + log con
     contador acumulado. El usuario nunca ve markup.

## Decisiones
- Capa 1 en el intake (no ejecución directa desde el ramal de texto): reusa el dispatch
  existente y `validate_tool_calls`; cero llamadas API extra para el caso reconstruible.
- Detección = marcador + forma de invocación (`invoke|calls`): texto limpio pasa byte a
  byte; la prosa que menciona el marcador (este hilo incluido) no dispara.
- Bloque truncado (dominante en producción): corte desde el primer marcador hasta el
  último cierre o EOS; no se exige bloque balanceado.
- Variantes: `｜｜DSML｜｜`, `｜DSML｜`, `||DSML||`, `<toolcalls>`; cierre con `/` antes de
  las barras (`</｜｜DSML｜｜ invoke>`).
- Guardias anti-fantasma (vllm #51914): herramienta declarada en `valid_tool_names`,
  argumentos capturados, valores con forma JSON parseables; si falla → nudge genérico /
  no recuperación, nunca llamada inventada.

## Rollback
Revert de los commits del guard (aditivo, sin reescritura de funciones existentes).

## Observabilidad
`logger.warning("HERMES-DSML-GUARD: ...")` con modelo/proveedor + contadores
`agent._dsml_guard_recovered` / `_dsml_guard_retries` / `_dsml_guard_strips` +
`_emit_diagnostic_status` visible durante la recuperación.
