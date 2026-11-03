# 04 — Matriz: cobertura / seams / pruebas / rollback

## Matriz de cobertura por superficie de publicación

| Superficie | Ruta real del texto | Gate | Cubierto por | Evidencia |
|---|---|---|---|---|
| Streaming API server (SSE) | delta → stream_q → `_iter_stream_items` → SSE | S1 (en el sink, aguas arriba de la cola) | T4 | `api_server_openai_routes.py::_iter_stream_items`; `_post_stream_transform` l.91 documenta deltas previos raw (E2) |
| Streaming plataformas (Telegram/Discord/Slack/WhatsApp edit-stream) | callbacks de stream del core | S1 | T4 | `agent/stream_delivery.py:33` (E4) |
| Commentary interim (todas las plataformas con `interim_assistant_messages`) | `_deliver_interim` → `interim_assistant_callback` → adapter.send interim | S2 | T5 | `agent/stream_delivery.py:176,197` (E3) |
| Texto final (todas las superficies) | `apply_llm_output_transform` → persist → sello `finish(final_text)` | S3 | T6 | `agent/turn_finalizer.py:483` (E1) |
| Ruta de recovery (final desde stream, `_recover_final_from_stream`) | recovery tail en `_persist_step` | S3 (el transform ya corre en ese punto; idempotencia por turn_id) | T6 | `turn_finalizer.py:225,631` |
| TUI / Desktop | consumen los mismos stream hooks + interim events del core | heredan S1/S2/S3 | T8 | `tui_gateway` consume callbacks del core (E4) |
| Mensajes out-of-band del usuario / texto inyectado | nunca pasan por el output del modelo | fuera de alcance por diseño (R4.4) | — | — |
| Envelope `tool_call` (estructurado) | no es prosa publicada | exento (R4.3) | tests T2 | — |

## Matriz de seams exactos (diff mínimo)

| Seam | Archivo:línea (HEAD cd397afc64) | Tipo de cambio | Alternativa descartada |
|---|---|---|---|
| Captura de evidencia | `agent/agent_init.py:1117` (`agent.tools = model_tools.get_tool_definitions(...)`; el turno no re-resuelve: `turn_request_assembly.py:204-210` solo decide `tools_for_api = agent.tools` o `[]` decoupled) | snapshot por turno desde `agent.tools` (llamada en arranque de turno + reset en `agent_init/_reset`) | `get_tool_definitions()` por turno en `turn_request_assembly` — descartado: tal llamada no existe (hallazgo review 1); `_last_resolved_tool_names` — descartado: global stale en delegación (E5) |
| S1 | `agent/stream_delivery.py::_deliver_to_stream_callbacks` (l.33) + punto de acumulación de deltas | 1 llamada al detector con ventana | Hook genérico per-delta — descartado: latencia por token sin consumidor más concreto; plugin — descartado: no ve deltas |
| S2 | `agent/stream_delivery.py::_deliver_interim` (l.176) y `_emit_interim_assistant_message` (l.197) | 1 llamada | — |
| S3 | `agent/turn_finalizer.py::apply_llm_output_transform` (l.483) vía hook existente `transform_llm_output` | extensión del seam existente (Footprint Ladder) | Hook core nuevo — descartado: extender seam existente primero |
| Estado | `agent_init.py` (`_ccg_evidence`, `_ccg_tainted`, `_ccg_repairs` en `_STREAM_STATE`) | 3 campos de instancia | Globals/cache de proceso — prohibido (multi-perfil, E5/E7) |

## Matriz de pruebas (mapa corpus → test)

| Clase del corpus (01-spec §6) | Test (F2/F3) | Veredicto esperado |
|---|---|---|
| Negación amplia ES "no tengo herramientas de tareas" + kanban DIRECT | `test_capability_claim_guard_detector.py` | CONTRADICTION(direct) |
| Negación específica EN "I can't send Telegram messages" + send DIRECT | ídem | CONTRADICTION(direct) |
| Turno conversacional decoupled (`tools_for_api = []`) + negativa de herramienta en `agent.tools` | `test_capability_claim_guard_evidence.py` + `test_capability_claim_guard_detector.py` | CONTRADICTION(direct) — la capacidad de sesión persiste aunque el payload la omita (AC11) |
| "no existe la herramienta X" con X DEFERRED | ídem | CONTRADICTION(deferred) |
| Herramienta ABSENT negada | ídem | ALLOWED(absent) |
| Comillas / bloque de código / hipótesis | ídem | ALLOWED(exempt) |
| Explicación de error real del turno (observed_errors) | ídem | ALLOWED(observed_error) |
| Negación de permisos/datos ("no tengo acceso a la base") | ídem | ALLOWED(exempt, R4.1) |
| Búsqueda vacía ritual / `not_found` de un nombre | ídem + `test_tool_search.py` (regresión) | ALLOWED (E6) |
| Fragmentación del claim entre deltas | `test_capability_claim_guard_stream.py` | detección al completar la frontera |
| Frames ya emitidos NO retratados | `test_capability_claim_guard_stream.py` + `test_stream_final_contract.py` | prefix-stable, corrección por sello |
| repair_limit agotado | `test_capability_claim_guard_final.py` | salida veraz, WARN, sin bucle (AC6) |
| Snapshot ausente / catálogo caído | ídem | fail-open (AC7) |
| Aislamiento entre turnos/perfiles/delegación | `test_capability_claim_guard_evidence.py` | evidencia correcta por turno |
| Default apagado = byte-idéntico | `test_capability_claim_guard_config.py` | AC1 |

Baseline vivo (F1, este worktree): 6 archivos, **149✓ / 0✗ / 4 skipped**, exit 0
(01-spec §9). T9 exige igualar o superar ese baseline en las carpetas tocadas.

## Matriz de rollback

| Nivel | Acción | Efecto |
|---|---|---|
| L1 config | `agent.capability_claim_guard.enabled: false` (default) | no-op total; sin cambios de código |
| L2 tarea | revert del diff de una tarea (T1-T8 ortogonales) | sin efecto en las demás; cero estado persistido |
| L3 completo | revert del módulo + 3 call sites + 3 campos de estado | árbol vuelve a HEAD cd397afc64; sin migraciones, sin esquema, sin transcript |
| Límites | el sello veraz ya publicado es texto entregado (no retractable por diseño R9) | aceptado: es salida veraz, no daño |

## Aprobaciones y gates

- F1: este diseño → `kanban_request_review(reviewer='heimdall')` (obligatorio por el body de la tarea; NO `kanban_complete` del implementador).
- F2-F3: cambios de código con TDD; reviewer heimdall al cierre de cada fase.
- F4: config default apagado; activación canaria = F5/T10 SOLO con autorización explícita de Jonathan en ese momento, entorno aislado DEV.
- Sin push/PR/merge ni commits sin autorización expresa repo por repo.
