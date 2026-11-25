# Tareas y reparto: guard `read-before-patch`

Worktree: `/opt/hermes-agent-data/worktrees/read-before-patch` · rama `feat/read-before-patch-guard`
(base `prod-stable` = `d04667851e`). Merge solo con review adversarial en PASS.

## Regla de separación

Cada tarea tiene **un dueño** y quien la escribe **no** la revisa. Los subagentes no ven esta
conversación: cada uno recibe el contexto completo en su `context`.

| # | Tarea | Dueño | Criterio de aceptación | Verificación |
|---|---|---|---|---|
| T0 | Worktree + spec + diseño + tareas | Ragnar (orquestador) | `.specs/read-before-patch-guard/{01,02,03}` en el worktree | `git status` limpio + lectura del spec |
| T1 | Suite de contrato **fallando** (RED) para CA1-CA11 | Subagente **A · tests** (perfil distinto al implementador) | 11 tests, cada uno mapeado a un CA, sin red, sin tocar el ledger real (`tmp_path`) | `pytest -q` → 11 failed |
| T2 | Hook `post_tool_call` + ledger con huellas | Subagente **B · implementer** | CAs de registro (CA2, CA3, CA4) en verde; `flock`; retención | `pytest -q -k "state or ledger"` |
| T3 | Decisión `pre_tool_call` + modos shadow/enforce + kill switch | Subagente **B · implementer** | CA1, CA5, CA6, CA7, CA8, CA9, CA10 | `pytest -q` completo en verde |
| T4 | Replay sobre `state.db` (CA11) | Subagente **C · analista** | reproduce 404/2.526 (±2%) y lista los 45 sospechosos de forma de ruta | `python3 scripts/hooks/read_before_patch_report.py --last 100` con tabla |
| T5 | Revisión adversarial del diff | `review_gate.py --engine opencode --model opencode/deepseek-v4.1-flash-free --require-tests` | PASS, 0 high, `tests_adequate: true` | JSON del gate + `state/reviews/...` |
| T6 | Revisión independiente (perfil distinto del implementador) | Subagente **D · reviewer** (lectura, sin editar) | Informe con hallazgos citando `archivo:línea` y veredicto PASS/FAIL | informe en el hilo del ticket |
| T7 | Despliegue en **shadow** + 24-48 h de medición | Ragnar (requiere OK del Admin) | `would_block` real medido por sesión, 0 bloqueos efectivos | ledger + `report.py` sobre lo capturado |
| T8 | Paso a **enforce** | Ragnar (requiere OK del Admin) | CA1 en vivo: 1 `patch` a ciegas bloqueado con el mensaje correcto | prueba manual en una sesión de prueba |
| T9 | Cierre: peguelo + ledger + Engram | Ragnar | lección promovida con evidencia | `mem_search` del `#id` |

## Reparto de subagentes

- **A · tests** (`delegate_task`, sin permisos de escritura fuera de `tests/hooks/`): escribe la
  suite RED a partir del spec, **sin ver la implementación**. Objetivo: que los tests describan el
  contrato, no la solución.
- **B · implementer** (`delegate_task`, escribe solo en `scripts/hooks/`): implementa hasta verde.
  Prohibido tocar los tests de A salvo para añadir casos, nunca para relajarlos.
- **C · analista** (lectura, `state.db` en `mode=ro`): mide y reporta; no escribe código de producción.
- **D · reviewer** (lectura, sin permisos de edición): revisa el diff completo con el spec delante
  y emite PASS/FAIL independiente del gate automático.
- **Gate automático**: `adversarial-review-gate` con `opencode/deepseek-v4.1-flash-free` — el mismo
  que gateó el QA de video. No sustituye a D: son dos jueces distintos.

## Presupuesto y frenos

- Máximo 2 ciclos de corrección por revisión; al tercero se escala al Admin (regla del gate).
- Nada de `git push` ni de tocar `config.yaml` en T1-T4: son locales al worktree.
- T7 y T8 tocan la flota ⇒ confirmación explícita del Admin antes de cada una.
- Coste estimado: 4 subagentes × 1 pasada + 2 revisiones. Sin gasto en APIs pagas: el reviewer
  corre en OpenCode Go (free tier) y el replay es local.
