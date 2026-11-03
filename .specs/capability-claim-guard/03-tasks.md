# 03 — Tareas: Capability Claim Guard (TDD, fases F2+)

Reglas: TDD estricto (RED antes de GREEN), un solo worktree
(`/opt/hermes-agent-data/fleet/worktrees/hermes-agent/capability-claim-guard`, branch
`feat/capability-claim-guard`), runner oficial SIEMPRE
(`env -u PYTHONPATH HERMES_RUNTIME_DIR=/opt/hermes-agent-data/tools scripts/run_tests.sh …`,
jamás bare pytest), sin commits/push sin autorización, reviewer heimdall al cierre de
cada fase. Skills a consumir antes de ejecutar cada tarea: las marcadas por tarea
(`.skills/<name>/SKILL.md`).

## Fase F2 — Núcleo del guard (módulo + detector + evidencia)

- [x] **T1 RED/GREEN — Evidence Snapshot (CES).** Nuevo `agent/capability_claim_guard.py`
  con `capture_evidence(agent, turn_id, tool_defs, deferred_names, aliases)` y reset por
  turno. Tests: `tests/agent/test_capability_claim_guard_evidence.py` — captura DIRECT
  desde `agent.tools` (capacidad de sesión, `agent/agent_init.py:1117`; NO del payload
  `tools=` del request ni `_last_resolved_tool_names`), clase turno decoupled
  (`tools_for_api = []` en `turn_request_assembly.py:205-210`: la evidencia persiste),
  DEFERRED
  desde el ensamblado tool_search, staleness del global NO usado, aislamiento entre
  turnos y entre perfiles (dos instancias). Verificación: `scripts/run_tests.sh
  tests/agent/test_capability_claim_guard_evidence.py`. Skills: `python-patterns`,
  `python-testing-patterns`, `codebase-inspection`.

- [x] **T2 RED/GREEN — Detector determinista ES/EN.** `scan_published_text(evidence,
  text, surface) -> Verdict`. Tabla declarativa de speech-acts ES/EN + extracción de
  capacidad + exenciones (R4) + clases veredicto (R5). Tests parametrizados con el
  corpus completo de §6 de 01-spec (negación amplia/específica ES y EN, comillas,
  código, hipótesis, error observado, permisos/datos, deferred, envelope, aliases,
  búsquedas vacías, out-of-band, turno conversacional decoupled con
  `tools_for_api = []`). Verificación: `scripts/run_tests.sh
  tests/agent/test_capability_claim_guard_detector.py`. Skills: `python-patterns`.

- [x] **T3 RED/GREEN — Conexión de evidencia al turno.** Llamada a `capture_evidence`
  leyendo `agent.tools` al arrancar el turno (la lista se fija en
  `agent/agent_init.py:1117`; `turn_request_assembly` no re-resuelve nada) y reset
  junto a `_current_streamed_assistant_text`. Incluir caso decoupled
  (`should_decouple_tools_for_turn` → `tools_for_api = []`: la evidencia no cambia).
  Tests de integración
  con agent real de `tests/agent/test_streaming.py` (patrón existente). Verificación:
  `scripts/run_tests.sh tests/agent/test_capability_claim_guard_evidence.py
  tests/agent/test_streaming.py`. Depende de T1.

## Fase F3 — Gates de publicación (S1/S2/S3)

- [ ] **T4 RED/GREEN — S1 delta sink.** Scan en `_deliver_to_stream_callbacks` con
  ventana `holdback_chars` y escaneo por frontera de oración; tainted-mark en
  contradicción; jamás retrata frames (test de prefix-stability con el patrón de
  `tests/gateway/test_stream_final_contract.py`); corrección por sello
  `finish(final_text)`. Verificación: `scripts/run_tests.sh
  tests/agent/test_capability_claim_guard_stream.py
  tests/gateway/test_stream_final_contract.py`. Depende de T2, T3. Skills:
  `api-and-interface-design`.

- [ ] **T5 RED/GREEN — S2 interim.** Scan en `_deliver_interim` /
  `_emit_interim_assistant_message`: supresión solo si NO streamed; registro si
  streamed. Tests con `interim_assistant_callback` falso (patrón
  `tests/agent/test_multimodal_interim.py`). Verificación: `scripts/run_tests.sh
  tests/agent/test_capability_claim_guard_interim.py`. Depende de T2, T3.

- [ ] **T6 RED/GREEN — S3 final + reparación acotada.** Extensión de
  `apply_llm_output_transform` (idempotencia por turn_id preservada); inyección de
  reparación como tool result/user message (test de forma de mensaje y de alternancia
  de roles, patrón `tests/agent/test_turn_finalizer_interrupt_alternation.py`);
  `repair_limit=2` → después solo sello veraz; fail-open con snapshot ausente. Tests:
  `tests/agent/test_capability_claim_guard_final.py`. Verificación: `scripts/run_tests.sh
  tests/agent/test_capability_claim_guard_final.py
  tests/agent/test_turn_finalizer_final_response_persistence.py`. Depende de T2, T3.

## Fase F4 — Config y aislamiento

- [ ] **T7 — Config `agent.capability_claim_guard.*` default `enabled:false`.** Lectura
  estándar; test AC1: con default, baseline de seams idéntico (los 6 archivos de
  baseline + los nuevos) y ningún scan ejecutado (spy). Verificación: `scripts/run_tests.sh
  tests/agent/test_capability_claim_guard_config.py` + baseline completo.
  Depende de T4-T6.

- [ ] **T8 — Cobertura de superficies (E2E sin red).** Con `enabled:true`: API server
  SSE (patrón `tests/gateway/test_api_server.py`), streaming gateway, TUI callback —
  verificar que la corrección llega por el sello y que `_post_stream_transform`
  permanece como append post-final. Verificación: `scripts/run_tests.sh
  tests/gateway/test_capability_claim_guard_surfaces.py`. Depende de T4-T7.

## Fase F5 — Cierre de fase

- [ ] **T9 — Regresión completa de carpetas tocadas.** `scripts/run_tests.sh
  tests/agent/ tests/gateway/ tests/tools/test_tool_search.py` con presupuesto de
  tiempo; comparar contra baseline F1 (149✓) — solo se toleran fallos pre-existentes
  ambientales A/B-verificados. Depende de T1-T8.

- [ ] **T10 — Canary AISLADO DEV (requiere autorización explícita de Jonathan en ese
  momento).** Perfil/hogar aislado temporal, turnos sintéticos del corpus, sin agentes
  operativos ni PROD, sin restart de gateways productivos, sin Telegram real. Evidencia:
  transcripts + logs del guard. Fuera de alcance de F2 sin nueva autorización.

## Dependencias

```
T1 ─┬─ T3 ─┬─ T4 ─┐
T2 ─┘      ├─ T5 ─┼─ T7 ─ T8 ─ T9 ─ T10
           └─ T6 ─┘
```

## Rollback por tarea
Cada tarea es un diff ortogonal: T1-T3 (módulo + 1 call site), T4 (1 call site),
T5 (1 call site), T6 (1 call site), T7 (config). Revert por tarea sin tocar las demás;
ningún estado persistido. `enabled:false` = no-op total en runtime (AC1).
