# 03-tasks — HERMES-DSML-GUARD

| # | Tarea | Verificación | Estado |
|---|---|---|---|
| 1 | Spec y diseño en `.specs/dsml-guard/` | lectura | ✅ |
| 2 | Tests primero (RED): `tests/agent/test_dsml_guard.py` — detección/variantes/truncado/guardias | RED (`ModuleNotFoundError`) | ✅ |
| 3 | Implementar `agent/dsml_guard.py` (detección/parse/limpieza) | 11 passed | ✅ GREEN |
| 4 | Integrar capas 2-3 en `agent/turn_final_response.py` | suite verde | ✅ |
| 5 | Capa 1 en `agent/turn_response_intake.py` (nota Roshi: ejecución in-turn a 0 tokens) + 4 tests de intake | 15 passed | ✅ |
| 6 | Suite completa `tests/agent/` + `tests/gateway/test_replay_entry_fields.py` | sin regresiones vs base | ⏳ |
| 7 | Commits convencionales en worktree (sin push) | `git log` / `git status` limpio | ⏳ |
| 8 | Revisión independiente (subagente) + replay de Roshi con `casos_reales.json` (58 casos) | veredicto revisores | ⏳ |
| 9 | Despliegue a perfiles (D-I-V-E) — REQUIERE OK explícito del Admin | restart controlado + turno real verificado | ⏳ |

Notas: job codex 20261025-114510 murió sin producción (colgado en modo collab, log
vacío); implementación ejecutada por el orquestador (lección flota 23-oct: cap 2 rondas
por fase). Worktree basado en `ca553b20e9` (HEAD de runtime, superconjunto de
origin/main — `git merge-base --is-ancestor` verificado).
