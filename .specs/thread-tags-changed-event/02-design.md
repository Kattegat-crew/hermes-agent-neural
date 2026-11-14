# Design — `thread_tags_changed`

## 1. Arquitectura

El cambio vive en **un solo archivo**, sobre la ruta que ya existe:

```
discord.py on_thread_update(before, after)          [ya existe, adapter.py:1512]
        └── adapter._on_platform_thread_update(before, after)   [ya existe]
                ├── emite "thread_renamed"    si cambió el nombre   [ya existe]
                └── emite "thread_tags_changed" si cambió applied_tags  ← NUEVO
                        └── _emit_platform_event(tipo, build)
                                └── _fire_platform_event(event, source)
                                        └── runner._handle_gateway_platform_event
                                                ├── has_hook("gateway_platform_event")
                                                └── _is_user_authorized_for_source(source)
                                                        └── invoke_hook(...) → plugin consumidor
```

Ninguna otra capa cambia: **no** se toca `gateway/run_adapters.py`, la
autorización, ni el resto de adapters (Telegram conserva su `catch-all`).

## 2. Contrato del evento

```json
{
  "platform": "discord",
  "event_type": "thread_tags_changed",
  "payload": {
    "thread_id": "1567690825977303120",
    "parent_chat_id": "1554957746980261938",
    "old_tags": ["1555025462684819496", "1554957746980261942"],
    "new_tags": ["1555025462684819496", "1554957746980261944"]
  }
}
```

`source` (para el gate de autorización) = el de `_thread_event_parts`
— `chat_id=thread_id`, `user_id=owner_id`. **Mismo trade-off documentado** que
`message_deleted`: el evento de Discord no trae actor.

## 3. Diseño de la normalización

Se reutiliza `_thread_event_parts(thread, extra_payload)` (static method ya
usado por `thread_created` / `thread_renamed`), que devuelve
`(payload, source_kwargs)` o `None` si faltan ids. El `extra_payload` propio:

```python
def _tags_of(thread) -> tuple[list[str], list[str]]:   # (old, new)
def _extra(...) -> dict   # {"old_tags": [...], "new_tags": [...]}
```

Comparación: `list[str]` de `str(tag)` con `getattr(tag, "id", tag)` — así
sobrevive tanto objetos `discord.Tag` como strings crudos.

En `_on_platform_thread_update`:

```python
renamed = old_name != new_name and isinstance(new_name, str)
old_t, new_t = _tags_of(before), _tags_of(after)
tags_changed = old_t != new_t
if renamed:    await self._emit_platform_event("thread_renamed", _build)
if tags_changed: await self._emit_platform_event("thread_tags_changed", _build_tags)
```

Los `emit` ya son no-op sin suscriptores (`_platform_events_subscribed`), así
que un gateway sin consumidores paga solo la comparación de dos listas.

## 4. Riesgos y mitigación

| Riesgo | Mitigación |
|---|---|
| Evento llega a un hilo que no es del foro de tickets | el consumidor filtra por `parent_chat_id` |
| Bucle (el regenerador edita mensajes, no tags) | el evento solo dispara con cambio real de tags; además el plugin usa lock single-flight |
| Dueño no autorizado ⇒ evento caído en el gate | documentado en spec; comportamiento idéntico al de `thread_created` existente |
| Orden de tags estable vs fabricado | se compara y emite tal cual, sin ordenar |
| Rollback | `git revert` del commit; sin estado persistido por el adapter |

## 5. Observabilidad

Log `logger.debug("[%s] thread tags changed %s -> %s", ...)` dentro del build
(solo con `HERMES_PLUGINS_DEBUG`/nivel debug): un evento de tag es de baja
frecuencia, no ensucia el log normal.

## 6. Verificación

1. `pytest tests/gateway/test_discord_platform_events.py -v` (TDD: rojo → verde).
2. `pytest tests/gateway -k "discord and thread" -v` (regresión de renames).
3. `ruff check plugins/platforms/discord/adapter.py`.
4. Evidencia de integración **pendiente de arranque**: tras el próximo
   reinicio del gateway, cambiar un tag en el foro y confirmar que
   `last-run.json` cambia sin intervención del cron.
