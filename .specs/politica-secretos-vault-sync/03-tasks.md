# Tasks — Fase 1 (TDD) — **ESTADO: Completed** (gate 4 APROBADO 2026-11-07)

Cadena de review: ronda 1 RECHAZADO (9 hallazgos H1-H9) → ronda 2 APROBADO (N1) → gate 3 APROBADO (deuda N-a/N-b) → commit `a3ffe224ff` → **gate 4 APROBADO** (43/43 tests, sin regresiones, 5 rutas, cero atribución de IA).

Verifier canónico de la fase:
`env -u PYTHONPATH python3 -m unittest -v tests/scripts/test_vault_sync_env.py`
(stdlib puro: el entorno **no trae `pytest`** — verificado 7-nov; las clases son recolectables por pytest en CI).

| # | Tarea | Skill | Verificación | Dep. | Estado |
|---|---|---|---|---|---|
| T1 | `tests/scripts/test_vault_sync_env.py` con AC-1..AC-7 (**RED primero**) | `python-testing-patterns` | comando de la fase → fallo (módulo inexistente) | — | ☐ |
| T2 | `scripts/vault-timer/sync-env.py`: merge preservativo (`split_eol`, `parse_kv`, `split_value_comment`, `merge_env_text`) | `python-patterns` | `py_compile` + AC-1/2/4/6 green | T1 | ☐ |
| T3 | Paridad DEV+PROD: guard padre, `SUMMARY`, `owner`, restart-si-cambia, fallback `notes`, escritura atómica | `python-patterns` | AC-3/4/5 + `py_compile` | T2 | ☐ |
| T4 | `main` inyectable (`fetch`, `mapfile`, `err`, `restart_fn`) + exit code RF-7/RF-8 | `python-testing-patterns` | tests de fetch/exit | T3 | ☐ |
| T5 | Lint: `python3 -m py_compile` + `git diff --check` | `code-review-and-quality` | exit 0 | T4 | ☐ |
| T6 | Commit convencional sin atribución de IA en `feat/politica-secretos-vault-sync` | — | `git status` limpio + `git log -1 --stat` | T5 | ☐ |
| T7 | **Review adversarial** (reviewer independiente) → hallazgos corregidos → re-run green | `code-review-and-quality` | veredicto `APROBADO` + suite en green | T6 | ☑ ronda 1: RECHAZADO (9 hallazgos) → corregidos (37 tests) · ronda 2: **APROBADO** con 3 hallazgos no bloqueantes → N1 corregido (39 tests) y N2 documentado |

### Ronda 1 del reviewer (2026-11-07)
RECHAZADO con 9 hallazgos. Corregidos y con test: H1 (lecturas/parsing por target no pueden tumbar la cola), H2 (symlink escrito a través del enlace), H3 (BOM inicial no duplica la clave), H4 (sin updates y archivo ausente no crea `.env` vacío ni reinicia), H5 (rc del restart visible como WARNING), H6 (append hereda el EOL del archivo), H9 (nombres duplicados en el vault → WARNING). Documentados como decisión: H7 (sin quoting en valores) y H8 (exit 1 es nuevo en PROD).

## Cierre de fase
T7 en verde: cero hallazgos abiertos + suite completa green + commit en la rama.
**Despliegue a hosts = Fase 2** (backup fechado en `/opt/vault/backups/`), fuera de esta fase.
