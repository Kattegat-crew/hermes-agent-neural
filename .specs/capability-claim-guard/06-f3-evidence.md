# 06 — Evidencia F3: gates de publicación (T4–T7) + hallazgos 1–5

Tarea kanban: `t_5cc01f4c` (continuación autorizada de F2). Base: `cd397afc64`
(`feat/capability-claim-guard`). Worktree único:
`/opt/hermes-agent-data/fleet/worktrees/hermes-agent/capability-claim-guard`.

Todo el enforcement está **detrás de flag** (`agent.capability_claim_guard.enabled`,
default `false`): sin snapshot no hay scan, no se crea estado y el runtime es
byte-idéntico (verificado por test con "bomba" en el módulo guard).

## 1. Superficies y puntos de integración (1 call site por gate)

| Gate | Archivo | Punto exacto | Contrato |
|---|---|---|---|
| S1 delta holdback | `agent/stream_delivery.py` | `_fire_stream_delta` → `_ccg_stream_gate`; flush en `_reset_stream_delivery_tracking` y `_finish_chat_stream` | ventana `holdback_chars`, prefijo publicado = prefijo del stream, nada se retracta |
| S1 (bug de newline) | `agent/stream_delivery.py` | condición `text.lstrip("\n")`: el holdback cuenta como ya streameado | un delta compuesto solo de `\n` no se come mientras el holdback tiene el head |
| S2 interim/commentary | `agent/stream_delivery.py` | `_deliver_interim` → `_ccg_interim_gate` | suprime solo si nunca se mostró; si ya está en pantalla solo marca tainted |
| S3a reparación acotada | `agent/turn_stop_gates.py` | `apply_stop_gates` (primero) → `_ccg_verify_nudge` | 1 nudge user-role por ronda, `repair_limit` por turno |
| S3a historia | `agent/agent_runtime_helpers.py` | `finish_reason` provisional en `_merge_consecutive_assistants` | la respuesta corregida sustituye el candidato, no se fusiona |
| S3b sello veraz | `agent/turn_finalizer.py` | `apply_llm_output_transform` (después de hooks) | append de cláusula; nunca reescribe la afirmación del modelo |
| Evidencia de fallo real | `agent/tool_executor.py` | `_commit_tool_result` → `_ccg_record_outcome` | solo envelope autenticado del dispatcher |
| Snapshot por turno | `agent/conversation_loop.py` | `_run_conversation_turn` → `wire_turn` | reset siempre, captura solo si `enabled` |
| Config | `hermes_cli/config_defaults.py` | `agent.capability_claim_guard` | default OFF + `holdback_chars: 200`, `repair_limit: 2` |

## 2. Hallazgos del reviewer parcial — resolución

**1. `record_observed_error` sin callers / no confiar en texto.**
`record_tool_outcome(agent, tool, result, *, is_error, blocked)` reemplaza el uso
directo: solo acepta evidencia que el dispatcher autenticó —`success: false`,
`exit_code` entero ≠ 0, o denegación de aprobación (`blocked`)—. Texto libre (página
fetch, mensaje de usuario) **nunca** crea evidencia. Integrado en el call site real
`_commit_tool_result`, junto a `observe_tool_outcome`.
Tests: `test_capability_claim_guard_findings.py::test_scraped_text_that_looks_like_an_error_is_not_trusted`,
`::test_raw_error_text_is_not_trusted`, `::test_dispatcher_seam_records_only_authenticated_failures`.

**2. Aliases no poblados / semántica alias→tool vs alias→toolset.**
`capture_evidence(..., aliases=None)` ahora expande desde el registry vivo:
`registry.get_registered_toolset_aliases()` + `registry.get_toolset_for_tool(name)`
→ alias : frozenset(tools de la sesión). Un alias que no toca el snapshot de la
sesión no se registra; el resolver acepta tanto `str` (DI/legacy) como `frozenset`.
Tests: `::test_aliases_expand_toolset_to_its_tools`, `::test_alias_reference_resolves_through_the_toolset`,
`::test_alias_never_mentions_a_tool_outside_the_snapshot`.

**3. `is_enabled(agent)` leía config ambiente (HX002).**
El perfil dueño se deriva de `agent._session_db.db_path` (`<hermes_home>/state.db` →
parent) y la config se lee con `set_hermes_home_override(...)` alrededor de
`load_config_readonly()`. Multiplex: dos agentes de dos homes distintos en el mismo
proceso responden flags distintos; el config ambiente de launch no influye.
Tests: `test_capability_claim_guard_config.py::test_enabled_comes_from_the_agents_own_profile`,
`::test_concurrent_profiles_do_not_share_the_flag`, `::test_wire_turn_resets_state_every_turn`.

**4. Multi-familia y bare denial.**
`_resolve_candidates` separa resolución concreta (`_SPECIFIC_TERMS`, nombres, aliases)
de familias: los sustantivos de familia (`_FAMILY_TERMS`: mensajería/mensajes/chat/
sms/pendientes/…) se **apilan** sobre un hit concreto, de modo que "tareas ni
mensajería" resuelve ambas familias. Con hit concreto y sin sustantivo de familia
manda la resolución específica ("programar correos" → `email_send`, no
`send_message`). El bare denial sin objeto resoluble se acota a ≤5 tools
(evidencia acotada, nunca "cualquier herramienta irrelevante"). Objeto no resoluble
= `allowed_absent` (fail-open).
Tests: `::test_both_named_families_are_resolved`, `::test_bare_denial_is_bounded_and_still_contradicted`,
`::test_unresolvable_object_stays_fail_open`, `::test_resolved_family_does_not_drag_in_unrelated_tools`.

**5. Docs/AC y reseteo.**
Este documento + el docstring del módulo fijan la distinción detector-level
(`scan_published_text` es determinista y puro) vs publicación (S1/S2/S3 deciden qué
sale y cuándo). El reset per turno vive en `wire_turn` (`_ccg_hold_parts`,
`_ccg_published_tail`, `_ccg_tainted`, `_ccg_repairs`, `_ccg_repair_turn`,
`_ccg_evidence`) y se ejecuta **siempre**, incluso con el guard apagado, para que
ningún turno ni perfil herede estado. Ningún AC se declara aprobado aquí: la
aceptación la aplica el orquestador tras la revisión.

## 3. Fronteras de seguridad respetadas

- La reparación **no ejecuta** efectos externos: solo añade una fila `user` al
  historial del turno y re-entra al loop normal, con approval/security intactos.
- La evidencia de fallo es per-turno, per-sesión y per-home; no hay estado global.
- El sello no oculta auth/restricciones legítimas ni inventa disponibilidad: solo
  afirma que la herramienta consta en la lista de la sesión y pide comunicar el
  error real si falla.
- Sin credenciales, sin requests pagas, sin red en las pruebas.

## 4. Log de comandos (runner oficial, homes aislados)

```
cd /opt/hermes-agent-data/fleet/worktrees/hermes-agent/capability-claim-guard
timeout N env -u PYTHONPATH -u __HERMES_ACTIVATED -u VIRTUAL_ENV \
  HERMES_PYTHON=<test-venv>/bin/python \
  HERMES_RUNTIME_DIR=/opt/hermes-agent-data/tools \
  scripts/run_tests.sh <archivos> -q
```

<!-- RESULTADOS: se completan al cierre con la salida real -->
