# 05 — Evidencia de ejecución F2 (T1-T3)

Run 82 (reintento tras timeout del run 79 en 5400 s). Worktree
`/opt/hermes-agent-data/fleet/worktrees/hermes-agent/capability-claim-guard`, branch
`feat/capability-claim-guard`, HEAD `cd397afc64c91e759d49c1db6418e4b7ab107d12`.
Sin commits: todo el entregable es fuente local (autorización de commit pendiente).
Este documento es un **snapshot del estado F2 (T1–T3)**; el estado actual del guard
está en `06-f3-evidence.md` (gates T4–T7) y `07-checkpoint.md`.

## Cambios

| Archivo | Tipo | SHA-256 |
|---|---|---|
| `agent/capability_claim_guard.py` (NUEVO, 470 líneas — snapshot F2; ver `06-f3-evidence.md` para el estado actual: 941 líneas en HEAD `0a619a2544`) | módulo guard: CES (T1), detector determinista ES/EN (T2), `wire_turn` (T3) | `0ecdb3b9e6d2b9ab5e417c57869129ffb8445d69da56ef07c720df23f35eb026` |
| `agent/conversation_loop.py` (+6 líneas) | call site único T3: `wire_turn(agent, s.turn_id)` al arrancar el turno, antes del branch codex | `84ae131ee6e01bb908fd0c8814e1bc1293e1cae5983618c1168200afde329913` |
| `tests/agent/test_capability_claim_guard_evidence.py` (NUEVO, 328 líneas) | contrato T1 + wiring T3 (integración con AIAgent real, patrón de `test_run_agent`) | `90c87b1dce04532b2895284b4e5b85ea72e43077fbf640010b3abe1fc2d8ae6e` |
| `tests/agent/test_capability_claim_guard_detector.py` (NUEVO, 215 líneas) | corpus §6: ES/EN, comillas, código, hipótesis, permisos/datos, deferred, aliases, error observado, absent, fail-open | `ec5a3e4ffa7c199de40b52f2ac2916d26ece7e639fbd0530958e7c3974dcb24d` |

Diff del call site: `git diff agent/conversation_loop.py` (6 líneas, copiado en
`conversation_loop.diff` junto a esta evidencia). Cero globals nuevos; el estado
vive en `agent._ccg_evidence` (instancia, scope del perfil servido).

## Verificación (comandos reales, este run)

1. **GREEN T1+T2+T3** —
   `env -u PYTHONPATH HERMES_RUNTIME_DIR=/opt/hermes-agent-data/tools scripts/run_tests.sh
   tests/agent/test_capability_claim_guard_evidence.py tests/agent/test_capability_claim_guard_detector.py`
   → `2 files, 50 tests passed, 0 failed` en 8.5 s.

2. **RED del wiring T3 (A/B sin tocar el original)** —
   `git stash push -- agent/conversation_loop.py` y re-run de
   `TestTurnWiring` → `2 failed, 2 passed` (fallan
   `test_capture_runs_at_turn_start_when_enabled` y
   `test_stale_evidence_reset_even_when_disabled`; los otros 2 son verdades
   triviales sin wiring). `git stash pop` restaura el diff byte-idéntico.
   RED-GREEN del detector es estructural: el módulo es la única
   implementación de `scan_published_text` (sin ella, ImportError).

3. **Regresión baseline F1 + nuevos** — mismo runner sobre los 6 archivos del
   baseline (01-spec §9) + `test_streaming.py` (toca el archivo modificado) +
   los 2 nuevos →
   `8 files, 199 tests passed, 0 failed, 4 skipped` en 26.3 s
   (baseline 149✓/0✗/4s intacto + 50 nuevos). Comparación A/B contra el
   baseline de F1: solo se añadieron los 2 archivos nuevos; ningún fallo.

4. **Lint repo** — `python scripts/check` y `python -m scripts.code_health`
   ejecutados completos en este host. Resultados A/B (ninguno causado por el
   diff):
   - `ruff --only ruff`: 1050 hallazgos, TODOS en `scripts/`, `skills/`,
     `plugins/` pre-existentes (p. ej. `scripts/f2_preflight.py`,
     `scripts/consolida_censo.py`); cero en los 4 archivos del diff.
   - `code_health`: 5379 blocking de árbol vs base `70a846f7` (11400 archivos);
     de este diff SOLO 3 BLE001 (excepts silenciosos en
     `capability_claim_guard.py`) → corregidos registrando el traceback
     (`log.debug/warning(..., exc_info=True)`); re-verificado con el ruff
     pinneado de `scripts/code_health/ruff_runner.py` sobre los 4 archivos:
     cero BLE001/S110 restantes; máx CC del módulo = 10 (`_scan`, cap 20);
     archivo 470 líneas (cap 2000). Los demás guards de `scripts/check`
     (footguns/shebangs/no-tmp/agents-md/profile-archives/blob-size) fallan
     por archivos pre-existentes ajenos al diff (misma clasificación, cero
     solapamiento — `blob-size` marca `apps/desktop/packaging/nous-dmg-2b.tiff`
     y otros).
   - El job `health` de `scripts/check` excede su timeout interno de 900 s en
     este host incluso en solitario (~1050 s): ambiental, documentado; el
     ratchet se ejecutó directo con `python -m scripts.code_health`.

## Cobertura por criterio de aceptación (alcance F2)

| AC | Estado |
|---|---|
| AC2 (negativa ES con kanban DIRECT) | `TestDirectContradictions` ✓ — **detector-level** (F2); publicación S1/S2/S3 en `06-f3-evidence.md` + `07-checkpoint.md` §6 |
| AC3 (negativa EN con messaging DIRECT) | ídem ✓ — **detector-level** (F2); publicación S1/S2/S3 en `06-f3-evidence.md` + `07-checkpoint.md` §6 |
| AC4 (ABSENT pasa) | `TestAllowedAbsent` ✓ |
| AC5 (comillas/código/hipótesis pasan) | `TestExemptions` ✓ |
| AC7 (snapshot ausente → fail-open) | `TestFailOpen` + `test_fail_open_on_broken_agent` + `test_capture_failure_is_fail_open` ✓ |
| AC8 (error real del turno pasa) | `TestObservedErrors` ✓ |
| AC10 (búsqueda vacía no es ausencia) | `test_empty_search_result_is_not_absence` ✓ |
| AC11 (turno decoupled: evidencia de sesión, no del payload) | `test_records_session_capability_not_payload` ✓ |

Fuera de alcance F2 (F3+): AC1 completo (config file propio), AC6 (repair
budget), AC9 (prefix-stability S1) — sin gates de publicación en este run; el
módulo expone solo captura/detección, ningún call site S1/S2/S3 existe aún.

## Rollback

Revert del diff de `conversation_loop.py` + borrar los 3 archivos nuevos
(`git checkout -- agent/conversation_loop.py && rm agent/capability_claim_guard.py
tests/agent/test_capability_claim_guard_{detector,evidence}.py`). Sin estado
persistido, sin migraciones, default `enabled:false` (runtime byte-idéntico).
