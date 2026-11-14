# Tasks — `thread_tags_changed`

Estado: T1–T5 completadas (verificación en cada una). T6 = activación, pendiente
de reinicio del gateway.

| # | Tarea | Skill / superficie | Estado |
|---|---|---|---|
| T1 | Spec: RF/NFR/non-goals/AC (`01-spec.md`) | planificación | ✅ |
| T2 | Diseño: diagrama de ruta, contrato del evento, riesgos, verificación (`02-design.md`) | planificación | ✅ |
| T3 | **Test-first** de los 5 casos del evento en `tests/gateway/test_discord_platform_events.py` (nueva clase `TestThreadTagsChanged` + `_thread_obj(applied_tags=...)`) — **RED probado**: 3/5 fallan con el adaptador viejo (los 2 restantes son tests negativos que son invariantes) | `tests/gateway` | ✅ |
| T4 | Implementación en `plugins/platforms/discord/adapter.py::_on_platform_thread_update` + `_thread_tag_ids` — **GREEN**: 22/22 del archivo, `ruff check` limpio | plataforma discord | ✅ |
| T5 | Consumidor: `plugins/ticket-board-sync/` (`plugin.yaml` + `register()` sobre `gateway_platform_event`) con coalesce ráfaga 6s, single-flight y contención de fallos + 9 tests en `tests/gateway/test_ticket_board_sync.py` — **RED probado** (8/8 fallan sin el plugin) → **GREEN** 30/30 con los dos archivos | plugins | ✅ |
| T6 | Activación: listar `ticket-board-sync` en `plugins.enabled` (config D-I-V-E) + reinicio del gateway para que carguen adaptador y plugin | config/gateway | ⏳ pendiente de reinicio |
| T7 | E2E: cambiar un tag del foro → `last-run.json` cambia sin intervención del cron | integración | ⏳ requiere T6 |
| T8 | Commit convencional, sin atribución de IA, **sin push** | git | ⏳ tras T6 |

## T4 — detalle de verificación

- `pytest tests/gateway/test_discord_platform_events.py -q` → **22 passed**
- `uvx ruff check` sobre adaptador + test → **All checks passed!**
- Regresión `pytest tests/gateway/test_discord*.py -q` → 434 passed / 11 failed,
  y esos 11 **son preexistentes al cambio**: se reproducen solos en 1
  (`test_fallback_blocked_by_ssrf_guard` = `ModuleNotFoundError` de un débito
  ambiental) y los otros 10 dejan de fallar al correrlos por archivo (artefacto
  de aislamiento entre pruebas). Ninguno toca `on_thread_update`.

## T5 — decisiones

- El plugin va **in-tree** (`plugins/ticket-board-sync/`, precedente
  `kanban/`, `disk-cleanup/`): es una automatización propia de NeuralCrew, no un
  conector de producto de terceros (política de `plugins/AGENTS.md`).
- El hook `gateway_platform_event` deja de ser infraestructura especulativa:
  tiene consumidor concreto (esta regla la pone `plugins/AGENTS.md`).
- `subprocess.run` con `timeout=180` en `threading.Timer`: nunca bloquea el loop
  de eventos; cualquier excepción se contenga y solo loguea.
- El **cron 06:00 sigue siendo la red de seguridad**: si el listener no corre
  (gateway sin T6, plugin deshabilitado), el tablero igual se regenera a diario.

## Rollback

- Adaptador: `git revert` del commit (no persiste estado).
- Plugin: quitar `ticket-board-sync` de `plugins.enabled` + reiniciar.
- Config: `config.yaml` se respalda antes de la edición (patrón D-I-V-E).
