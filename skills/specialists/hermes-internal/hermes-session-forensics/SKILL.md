---
name: hermes-session-forensics
description: "Use when a Hermes session expired and context is missing."
tags: [sesiones, forense, state-db, continuidad, expiracion, gateway, cron]
version: "1.0"
author: Ragnar (curator)
created: 2026-09-10
category: devops
metadata:
  hermes:
    tags: [sesiones, forense, state.db, gateway, cron, continuidad, expiracion]
    related_skills: [context-recovery, hermes-memory-maintenance, cron-delivery-routing]
---

# Hermes Session Forensics — reconstruir el hilo desde disco

## When to Use

- El contexto arranca con _"The user's previous session expired due to inactivity. This is a fresh conversation with no prior context."_ y el mensaje del usuario es una frase sin referente: _"Listo guarda"_, _"dale"_, _"sí"_, _"hazlo"_, _"¿y entonces?"_.
- Preguntas de continuidad: _"¿qué estábamos haciendo?"_, _"¿esto ya quedó?"_, _"¿me llegó algo?"_.
- Verificar una entrega real (cron, watchdog, aviso al cliente) sin fiarse del reporte del propio job.
- Un mensaje del usuario aparece sin respuesta y hay que saber si llegó al gateway, a qué sesión, o no llegó.

## Regla de oro

**La conversación no se adivina: se lee.** `state.db`, `gateway.log`, `bridge.log` y `cron/output/` viven en disco y contienen la línea de tiempo completa. "No tengo contexto" no es respuesta aceptable cuando el usuario espera continuidad — reconstruir es barato (1-2 min) y evita que repita su propio contexto.

## Workflow (5 pasos)

1. **Sesiones recientes:** `session_search()` sin query → lista con `last_active` y `source`. Ordenar por `last_active`, NO por inicio.
2. **Leer la sesión candidata:** `session_search(session_id=<id>)`. Si es grande devuelve head+tail y el volcado completo queda en `/opt/data/cache/spillover/` (procesarlo con `execute_code`, no re-pedirlo por API).
3. **DB directo si el tail no basta:** `sqlite3 file:/opt/data/state.db?mode=ro` → `messages` filtrando `role='user'` por `timestamp`; `sessions` para mapear sesión→canal/chat. (Recetas en `references/hermes-state-db-map.md`.)
4. **Timeline de canales y entregas:** `grep 'inbound message' /opt/data/logs/gateway.log | tail -25` y `grep -n 'Session expiry' /opt/data/logs/gateway.log | tail -5`. Para crons: `cronjob_manage(action='list')` (`last_run_at`, `last_status`, `deliver`) + el archivo de `/opt/data/cron/output/<job_id>/`.
5. **Responder:** decir qué se reconstruyó y de dónde (sesión, canal, hora); si el referente es claro, ejecutar; si sigue ambiguo, UNA pregunta con 2-4 opciones concretas (`clarify`), incluyendo la salida "era otra cosa / algo que dije en un audio".

## Pitfalls

- **Mismo perfil ≠ misma sesión:** WhatsApp, Telegram y Discord mantienen sesiones separadas del MISMO perfil. El trabajo vivo puede estar en otro canal; el aviso de expiración llega en el canal nuevo. Revisar `source` antes de concluir.
- **Fechas del prompt poco fiables:** `Conversation started: <fecha>` puede estar viejo. Usar `date` y los timestamps de la DB como verdad.
- **`sessions` no tiene columna `session_id`:** su PK es `id`; el `session_id` de la app vive en `messages.session_id`. Un `JOIN ... ON s.session_id = m.session_id` falla con `no such column`.
- **Archivos `root:root`** (salida de cron, spillover de crons): leerlos con `docker exec hermes-agent cat <path>`.
- **No inventar el referente.** Guardar una interpretación plausible como si fuera un hecho contamina memoria y documentación; reconstruir primero.
- **Un `guarda`/`documenta` tras expiración** sigue siendo una petición real: reconstruir el hito y ejecutar el guardado, confirmando el tema en una línea si hubo duda.
- **Si `memory add` falla** con _"could not be read"_: el store real es `/opt/data/memories/MEMORY.md` (NO `/opt/data/MEMORY.md`, señuelo de 0 bytes). Reparar con `docker exec hermes-agent chown hermes:hermes /opt/data/memories/MEMORY.md /opt/data/memories/USER.md` + `chmod 600` + borrar `.lock` huérfanos, y verificar con un add que devuelva `entry_count`/`usage`.

## Verificación

- El referente reconstruido se puede citar con hora y sesión (`id` + `last_active`), no como suposición.
- Si la conclusión es "el mensaje no llegó", mostrar la evidencia: no hay línea `inbound message` en `gateway.log` y/o no hay fila en `messages`.
- Para entregas de cron: el archivo de salida dice `Status: silent (empty output)` cuando el job NO envió nada — no confundir "job ok" con "el usuario recibió algo".

## Referencias

- `references/session-expiry-recovery.md` — caso real completo (10-sep-2026) con la cadena de comandos.
- `references/hermes-state-db-map.md` — esquema útil de `state.db`, logs de gateway/bridge y rutas de cron con recetas de consulta.
