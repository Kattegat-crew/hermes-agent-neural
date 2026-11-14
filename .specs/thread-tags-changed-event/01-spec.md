# Spec — `thread_tags_changed`: evento de cambio de tag en hilos de foro

## 1. Problema / intento de negocio

El **tablero de prioridades** del foro `🛠️ tickets-tecnicos`
(`1554957746980261938`) es una vista derivada: sus mensajes se recalculan a
partir de los tags del foro. Hoy solo se regenera a mano o con el cron diario
06:00, así que entre corridas el tablero miente (4 días de desfase: 37 → 41
tickets).

El gateway **ya escucha** `THREAD_UPDATE` (`on_thread_update`) pero el adapter
normaliza únicamente los cambios de nombre (`thread_renamed`) y descarta el
resto: *"Archive/slowmode/tag updates share on_thread_update — only real renames
fire"*. No existe ningún camino event-driven para "cambió el estado de un
ticket" → se pierde el evento que permitiría regenerar el tablero al instante.

**Usuario:** el Administrador (Jonathan "Plon") + los agentes que mantienen el
tablero. **Aprobación:** «listo ok dale» (14-nov-2026) sobre la propuesta
*listener `threadUpdate` del foro + cron 06:00 de respaldo*.

## 2. Requisitos funcionales

- **RF1:** Cuando `applied_tags` de un hilo del foro cambia, el adapter emite un
  evento normalizado `thread_tags_changed` por el pipeline existente
  (`gateway_platform_event`), con: `platform`, `event_type`, `payload`.
- **RF2:** `payload` = `thread_id`, `parent_chat_id`, `old_tags`, `new_tags`
  (ids como strings; el consumidor mapea a nombres).
- **RF3:** Un cambio de nombre *y* de tags emite **ambos** eventos
  (`thread_renamed` y `thread_tags_changed`), en ese orden de normalización.
- **RF4:** Update sin cambio de tags ni de nombre → **no** emite nada
  (archive/slowmode/lockiness siguen siendo ruido).
- **RF5:** Fallo de normalización (ids ausentes, tags no listos) → drop, fail
  closed, sin excepción hacia el loop de updates de discord.py.

## 3. Requisitos no funcionales

- **NFR1:** Cero coste cuando nadie suscribe: ya lo garantiza
  `_platform_events_subscribed()` (`has_hook`) antes de normalizar.
- **NFR2:** Sin objetos crudos del SDK en el payload (contrato del pipeline,
  #64176).
- **NFR3:** TDD: test rojo antes de implementar; `pytest tests/gateway/
  test_discord_platform_events.py -v` en verde, más la suite adyacente.
- **NFR4:** Conventional commits, cero atribución de IA, **sin push**.

## 4. Non-goals (explícitamente fuera de alcance)

- **NO** implementar aquí el consumidor: el plugin
  `ticket-board-sync` (fuera del repo, en `$HERMES_HOME/plugins/`) recibe el
  evento y dispara `regenerar_tablero.py`.
- **NO** cambiar la semántica de `thread_renamed`, `thread_created`,
  `message_edited`, `message_deleted`.
- **NO** tocar la autorización (`_is_user_authorized_for_source`) ni el
  contrato de `source` (el dueño del hilo sigue siendo el actor).
- **NO** reiniciar el gateway desde este trabajo: el cambio queda commiteado y
  se activa en el próximo arranque natural (el guard de `approvals.deny`
  `*systemctl*stop*hermes*` prohíbe al agente reiniciarlo).

## 5. Criterios de aceptación (Given/When/Then)

- **AC1** Given dos `Thread` con distinto `applied_tags` y igual nombre, When
  `_on_platform_thread_update(before, after)`, Then se dispara exactamente un
  evento `thread_tags_changed` con los ids ordenados de antes/después.
- **AC2** Given igual `applied_tags` y igual nombre, When lo mismo, Then
  `seen == []`.
- **AC3** Given nombre y tags cambiados, Then hay un `thread_renamed` **y** un
  `thread_tags_changed`.
- **AC4** Given dueño ausente (`owner_id=None`), Then el evento de tags se
  descarta (fail closed, como `thread_created`).
- **AC5** Given sin handler de plataforma instalado, Then no se normaliza nada.

## 6. Edge cases

- Tags presentes pero no-`Tag` (strings crudos desde payloads raw): se
  normalizan a `str(...)[:128]`, nunca objetos.
- Orden de `applied_tags`: se compara y se emite **tal cual** viene de Discord
  (no se ordena: el orden es estable y reordenarlo fabricaría diffs falsos).
- Un tag que se agrega y otro que se quita en el mismo update → es un cambio,
  emite.
