# 01 — Especificación: Capability Claim Guard (CCG)

**Proyecto:** guard runtime contra negativas no verificadas de capacidades/herramientas.
**Fase:** F1 (solo diseño + baseline, este worktree). **Autorización:** Jonathan, Desktop 02-nov-2026.
**Estado:** Borrador para revisión (reviewer: heimdall).

## 1. Problema (repro documentado)

Ragnar declaró "no tengo herramientas de tareas/mensajería" en un turno real, cuando
`kanban_*` estaban en su lista directa de herramientas y `terminal` + `hermes send`
también lo estaban. La negativa se publicó al usuario sin ninguna comprobación previa
y sin comunicar un error real. El modelo no tiene hoy ningún punto del runtime que
obligue a verificar antes de negar una capacidad.

## 2. Evidencia técnica inicial (leída viva en el worktree, HEAD cd397afc64)

| # | Hecho verificado | Fuente |
|---|---|---|
| E1 | `transform_llm_output` se dispara una vez por turno, idempotente por `turn_id`, SOLO en puntos de persistencia del texto final (`finish_text_response` / `_persist_step` / `_apply_output_hooks`). No ve deltas de streaming ni commentary interim. | `agent/turn_finalizer.py:483` (`apply_llm_output_transform`) |
| E2 | Los deltas SSE ya llevaron la respuesta raw al cliente antes de cualquier transform final; `_post_stream_transform` solo puede APENDAR el rewrite (o reenviarlo completo si no es append puro). Un guard solo-final no repara superficies streaming. | `gateway/platforms/api_server_openai_routes.py:91` |
| E3 | El commentary interim se publica a mitad de turno vía `interim_assistant_callback` (`_deliver_interim`), antes de cualquier transform final. | `agent/stream_delivery.py:176,197` |
| E4 | El delta sink del core (`_deliver_to_stream_callbacks`) alimenta TODAS las superficies (TUI/Desktop vía tui_gateway, API SSE, plataformas con streaming). Un gate en ese punto cubre todas las superficies de una vez. | `agent/stream_delivery.py:33` |
| E5 | La lista de herramientas resueltas del proceso es un global (`_last_resolved_tool_names`) que `delegate_tool.py` guarda/restaura y puede estar stale durante delegación. NO es evidencia por-sesión confiable para un guard. | `model_tools.py:174`; `agent/AGENTS.md` § message-flow invariants |
| E6 | Las herramientas diferidas viven detrás del puente `tool_search/tool_describe/tool_call`; `not_found` de un nombre significa "no disponible ahora, re-ejecuta tool_search", NUNCA incapacidad total. | `model_tools.py:501-535,704-747`; `tools/tool_search.py:522-524` |
| E7 | `check_fn` responde reachability/opt-in y está TTL-cacheado por proceso keyed by `hermes_home_key()`: reutilizable como señal, jamás re-probéado con efectos. | `tools/registry.py:263-427` |
| E8 | La capacidad de superficie es propiedad de la SESIÓN, no del proceso ni de env vars. | `tools/AGENTS.md` § Surface capability |
| E9 | Existe precedente de guards core deterministas de salida: stall guards ES/EN en `agent_runtime_helpers.py` (patrón del tipo que CCG necesita). | `.specs` de stall guard; `tests/agent/test_stall_guards.py` (40✓ baseline) |

## 3. Contrato funcional

### R1 — Verificar antes de negar
Cuando el texto del modelo declara una negativa de disponibilidad de herramienta/capacidad
que CONTRADICE la evidencia de la sesión actual (la herramienta está en la lista real del
request, o es diferida y alcanzable vía `tool_search`), el runtime interviene antes de
publicar. Distinguir: denegar algo ABSENTE de la evidencia es veraz y NO se toca.

### R2 — Cobertura de publicación completa (sin claim absoluto)
El gate debe existir en los tres puntos de publicación: deltas de streaming (S1),
commentary interim (S2), texto final (S3). Prohibido degradar a un regex solo-final que
declare protección de todas las sesiones. E1+E2+E3 son la prueba de que S3 solo es insuficiente.

### R3 — Verdad, no omnipresencia
La regla NO es "todas las herramientas siempre existen". Si la herramienta realmente
falló este turno (error observado en la sesión), o no está en la evidencia, la negativa
es correcta y el guard la deja pasar. El guard comunica errores reales veraces; nunca
suprime un blocker comprobado.

### R4 — Clases exentas (nunca bloquear)
1. Negativas de seguridad/permisos/datos (no es lo mismo que disponibilidad de herramienta).
2. Texto citado: comillas, bloques de código, hipótesis explícitas, explicación de un
   error real capturado este turno.
3. Envelope `tool_call` estructurado (no es prosa).
4. Mensajes out-of-band del usuario / texto inyectado de páginas (no es output del modelo).
5. Búsquedas inútiles/vacías (tool_search sin resultados) no cuentan como "no existe".

### R5 — Semántica de evidencia
- DIRECT (capacidad de la SESIÓN: `agent.tools` / `agent.valid_tool_names`, fijados en
  `agent/agent_init.py:1117`; E8): negarla es contradicción → interviene. NO se define
  sobre los schemas del request actual: en turnos conversacionales decoupled
  (`agent/turn_request_assembly.py:205-210`, `should_decouple_tools_for_turn` en
  `agent/tool_guardrails.py:828`) el payload va con `tools_for_api = []` y una
  definición por-request vaciaría DIRECT exactamente en los turnos donde el modelo
  tiende a negar capacidades. La capacidad persiste como propiedad de la sesión; el
  payload solo la omite → una negativa DIRECT en un turno decoupled es igual de
  contradictoria y se interviene igual (corrección de review ronda 1, hallazgo 2).
- DEFERRED (alcanzable vía tool_search/tool_describe): negarla como "no existe" es
  contradicción → interviene (la verdad es "está diferida; usa tool_search").
- ABSENT: negativa permitida; prohibido afirmar incapacidad categórica de la CLASE.
- `not_found` de un nombre no implica incapacidad completa (E6). Una llamada ritual de
  `tool_search` a otra capacidad no acredita nada; tampoco la evidencia de conversaciones
  anteriores ni el auto-reporte del modelo.

### R6 — Recuperación acotada (bounded repair)
- Máximo 2 intervenciones de guard por `turn_id` (configurable). Sin bucles.
- La reparación obliga a UNA de dos salidas: discovery real (una ronda forzada con
  evidencia inyectada) o salida veraz explícita (el texto final declara la verdad con
  la evidencia disponible). Nunca inventar nombres de herramientas.
- Sin modelo clasificador pago nuevo: detector determinista offline.

### R7 — Condición segura ante catálogo caído
Si la evidencia propia no está disponible (snapshot ausente, catálogo vacío, error
interno del guard), el guard FALLA ABIERTO: deja pasar el texto, registra WARN.
Nunca deadlock, nunca suprimir toda salida, nunca bloquear el turno.

### R8 — Sin efectos externos para probar
El guard nunca ejecuta la herramienta para comprobar disponibilidad. Solo lee:
schemas de `agent.tools` (capacidad de sesión), estado de diferidos, aliases, y
`check_fn` ya cacheado (E7).
Distinguir disponibilidad (evidencia local) de auth/reachability (no se prueba aquí).

### R9 — Invariantes del core respetados
- Prompt caching: ninguna inyección al system prompt; la reparación viaja como
  user message o tool result (regla de `agent/AGENTS.md`).
- Streaming contract: frames prefix-stables; el gate NUNCA retrata deltas ya
  publicados (violación de prefix-stability → duplicados). La corrección de una
  tanda ya emitida viaja por el sello final (`finish(final_text)`), no por edición de frames.
- Narrow waist: un módulo nuevo + tres call sites; cero herramientas nuevas de core.
- Sin mutación de contexto pasado; sin swaps de toolsets mid-conversación.

### R10 — Config aislada, default apagado
Todos los parámetros viven bajo `agent.capability_claim_guard.*` con
`enabled: false` por defecto: el runtime actual queda byte-idéntico con la
config por omisión. La activación canaria será en entorno AISLADO DEV (F3+),
nunca en perfiles operativos ni PROD.

## 4. Criterios de aceptación (Given/When/Then, extra para F2)

- AC1 Dado `enabled:false`, cuando corre cualquier turno, entonces el diff de
  comportamiento es nulo (tests de baseline idénticos).
- AC2 Dado una negativa ES "no tengo herramientas de kanban" con `kanban_*` DIRECT,
  cuando se publica, entonces no sale sin intervención (S1/S2/S3 según superficie).
- AC3 Dado una negativa EN "I don't have any messaging tools" con messaging DIRECT,
  ídem AC2.
- AC4 Dado la herramienta ABSENT negada, el texto pasa sin intervención.
- AC5 Dado negación dentro de comillas/código/hipótesis, pasa sin intervención.
- AC6 Dado repair budget agotado (2), el turno termina con salida veraz explícita
  y log WARN; nunca bucle infinito.
- AC7 Dado snapshot de evidencia ausente, el guard falla abierto (WARN, texto pasa).
- AC8 Dado error real de la herramienta este turno, la negativa pasa (R3).
- AC9 Dado streaming, los frames ya emitidos no se retratan; la corrección llega
  por el sello final (prefix-stability intacta).
- AC10 Dado `not_found` de un nombre en tool_describe, NO se genera intervención
  por "incapacidad completa".
- AC11 Dado un turno conversacional decoupled (`tools_for_api = []`,
  `should_decouple_tools_for_turn`), cuando el modelo niega una herramienta que está
  en `agent.tools`, entonces es CONTRADICTION(direct): la evidencia proviene de la
  capacidad de sesión, no del payload del turno.

## 5. No-goals
- No es un plugin-only (E1-E3 prueban que commentary/streaming/recovery quedarían sin
  proteger: se declara el seam interno mínimo en vez de prometer "plugin solamente").
- No bloquear negativas de seguridad; no ejecutar side effects de prueba; no activar
  agentes operativos/PROD ni restart de gateways; sin commits/push/PR (F1).
- Sin telemetría saliente; sin nuevos env vars de comportamiento (config.yaml only).

## 6. Edge cases del corpus (ES/EN) que F2 debe cubrir en tests
Negación amplia ("no tengo herramientas") / específica ("no puedo enviar Telegram");
comillas y código; hipótesis ("si tuviera X…"); explicación de error real; negación de
permisos/datos; herramientas diferidas; envelope tool_call; aliases de toolsets;
búsquedas vacías; reset entre sesiones/perfiles (evidencia por turn_id/home/session);
mensajes out-of-band; fragmentación de tokens de streaming (claim partido entre deltas);
turno conversacional decoupled (`tools_for_api = []`, l.205-210: la capacidad de sesión
persiste aunque el payload omita las schemas).

## 7. Skill audit (SDD Phase 1)
Cargadas en F1: `hermes-agent` (`.skills/hermes-agent/SKILL.md`). Aplican en F2:
`codebase-inspection`, `python-patterns`, `python-testing-patterns`,
`api-and-interface-design`, `systematic-debugging`. Prohibido escanear `skills/` de
producto como instrucciones de repo (regla `.agents/rules/01`).

## 8. Lección de entorno registrada (bootstrap ≠ validación)
El crash inicial del run 70 ("no dependency environment is committed") fue de SETUP PM
del worktree, no de validación funcional: Ragnar lo resolvió con
`python3 -m pm.cli install --extra all` + `scripts/run-in-hermes-env` en DEV. El runner
oficial aquí requiere además `HERMES_RUNTIME_DIR=/opt/hermes-agent-data/tools` SOLO en
proceso (sin ese override `scripts/_activation.sh` devuelve "no bootstrap Python found").
Lección: preparar entorno con comandos PM oficiales por-worktree y nunca asumir que un
`git worktree add` hereda el ambiente del checkout origen.

## 9. Baseline de pruebas (evidencia viva, 02-nov-2026)

Comando (desde el worktree):

```
env -u PYTHONPATH HERMES_RUNTIME_DIR=/opt/hermes-agent-data/tools \
  scripts/run_tests.sh \
  tests/agent/test_turn_finalizer_final_response_persistence.py \
  tests/agent/test_turn_finalizer_cleanup_guard.py \
  tests/agent/test_stall_guards.py \
  tests/tools/test_tool_search.py \
  tests/agent/test_streaming.py \
  tests/gateway/test_stream_final_contract.py
```

Salida: `6 files, 149 tests passed, 0 failed, 4 skipped (100%) in 28.0s (4 workers)`,
exit 0. Estado git del worktree: limpio, branch `feat/capability-claim-guard`,
HEAD `cd397afc64c91e759d49c1db6418e4b7ab107d12`. Los archivos de spec quedan SIN
commit (autorización explícita requerida para commitear).

## 10. Diferencias registradas (sin copiar a ciegas)
- `.atl/skill-registry.md` NO existe en este worktree (la tarea pedía consultarlo):
  se registró la diferencia y se leyó `.skills/` directamente. No se copió desde el origen.
- `PROJECT_MEMORY.md` del worktree no menciona esta iniciativa (nació del HEAD base):
  su contexto proviene del body de la tarea y de la lectura viva del código.
