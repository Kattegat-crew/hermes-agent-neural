# Tasks — Fase 1 (TDD)

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
| T7 | **Review adversarial** independiente → hallazgos corregidos → re-run green | `code-review-and-quality` | veredicto APROBADO + suite green | T6 | ☐ |

## Cierre de fase
T7 en verde: cero hallazgos abiertos + suite completa green + commit en la rama.
**Despliegue a hosts = Fase 2** (backup fechado en `/opt/vault/backups/`), fuera de esta fase.
