# 01 — Spec: buffer de stream para el markup DSML

**Estado:** propuesta (gate de aprobación pendiente)
**Rama:** `feat/dsml-stream-buffer` · worktree `/opt/hermes-agent-data/worktrees/dsml-stream-buffer`
**Base:** `d04667851e` (prod-stable)
**Fecha:** 12-nov-2026 · Autor: Ragnar

## 1. Problema (evidencia)

El proveedor DeepSeek V4 emite a veces su DSL de tool-calls como texto plano. El
`HERMES-DSML-GUARD` ya lo recupera (capa 1: `agent/dsml_guard.py` + `turn_response_intake.py`;
capas 2-3: `turn_final_response.py`), pero **solo actúa al cerrar el turno**.

Medición real del 12-nov-2026 en `logs/agent.log`: 5 llamadas recuperadas en 4 eventos y 2
sesiones (14:20 `terminal`, 14:35 `memory`, 15:37 `terminal`, 15:43 `execute_code`+`terminal`).
En la sesión `20261111_170257_8d4b29` el usuario **vio el markup crudo** en la GUI
(`<||DSML||invoke name="execute_code">…`) y sólo después el mensaje quedó limpio.

Causa: `display.streaming: true` (GUI) entrega deltas token a token desde
`agent/stream_delivery.py::_deliver_to_stream_callbacks` y `chat_completion_helpers.py:2829`.
Ninguno de esos puntos consulta al guard.

## 2. Objetivo

Que ningún cliente con streaming reciba markup DSML en claro, sin romper la latencia
percibida ni el contrato de los callbacks.

## 3. No-goals

- No cambiar la detección/recuperación existente (`dsml_guard.py` se reutiliza tal cual).
- No tocar el adapter de Discord ni `streaming.enabled` del gateway (ya está en false).
- No reescribir el pipeline de streaming ni el orden de los callbacks.
- No persistir nada nuevo ni cambiar el transcript.

## 4. Criterios de aceptación

- **CA-1** Dado un stream cuyo primer delta empieza con un prefijo de marcador
  (`||DSML||`, `｜｜DSML｜｜`, `｜DSML｜`, `<toolcalls>`), cuando el texto acumulado sigue siendo
  prefijo de un marcador, entonces no se emite ningún delta al cliente.
- **CA-2** Dado ese stream, cuando el acumulado diverge del marcador, entonces se emite el
  buffer completo una sola vez y el resto pasa en modo passthrough (sin latencia añadida).
- **CA-3** Dado un stream que resulta ser un bloque DSML completo, cuando el turno cierra,
  entonces el buffer se descarta y el guard existente limpia/recupera como hoy.
- **CA-4** Dado un stream normal (primer delta no-marcador), entonces el comportamiento es
  idéntico byte a byte al actual (0 deltas retenidos).
- **CA-5** Los callbacks de TTS y los plugin stream hooks reciben exactamente los mismos
  eventos que hoy cuando el texto es limpio.
- **CA-6** `pytest tests/agent/test_dsml_stream_buffer.py -v` y
  `pytest tests/agent/test_dsml_guard.py tests/agent/test_hold_stream_agent.py -v` en verde.

## 5. Edge cases

- Marcadores partidos entre deltas (`|` + `|DSML||`).
- Turno con tool-calls reales: el buffer debe resetearse por respuesta, no por sesión.
- `_hold_stream` activo: no emitir nada (comportamiento actual se preserva).
- Respuesta vacía o solo whitespace antes del marcador.
- Marcador dentro de prosa en medio del texto: no debe retener (sólo al inicio del stream).

## 6. Fallos y observabilidad

- Contador `_dsml_stream_held` + log `HERMES-DSML-GUARD: stream buffered (prefix=…, bytes=N)`
  con modelo/proveedor, para que el digest diario pueda contar retenciones además de recuperaciones.
- Si el buffer excede un tope (p. ej. 4 KB) sin resolver, se hace flush y se deja al guard final.

## 7. Skill audit

- `python-patterns`, `python-testing-patterns` (implementación y TDD)
- `code-review-and-quality` (revisión fría por un perfil distinto al implementador)
- `hermes-agent` (contratos de `StreamDeliveryMixin`, `_hold_stream`, callbacks)

## 8. Rollback

Revertir el commit del worktree; no hay migración de datos ni cambios de config. La rama no
se fusiona a `prod-stable` sin aprobación explícita.
