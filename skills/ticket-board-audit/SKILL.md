---
name: ticket-board-audit
description: Use when asked for ticket/project status or board audit.
version: 1.0.0
author: Ragnar (autonomous review)
license: internal
metadata:
  hermes:
    tags: [kanban, tickets, audit, discord]
    related_skills: []
---

# Auditoría de tickets / tablero (fuente canónica)

## When to Use
- "Estado general", "qué tickets tomamos al inicio", "cuáles cerramos", "qué falta", "cómo vamos".
- Cierre de día/proyecto que exige conciliar tablero vs. lo reportado en chat.

El kanban es la única fuente de verdad del estado de tickets. Los hilos del foro de tickets de Discord NO se pueden leer vía bot (sin permisos en el canal; el token del gateway no vive en `.env`) — no perder tiempo intentándolo; el foro solo sirve como aviso visible, el registro con evidencia (comentarios, commits, runs, crash reasons) vive en las tarjetas.

## Procedimiento
1. **Tablero completo:** `hermes kanban list --json` vía terminal (devuelve TODAS las tarjetas sin el cap de 50 filas del tool) y agregar conteos por `status` con Python, nunca a ojo.
2. **Detalle por tarjeta:** tool `kanban_show(task_id=...)` — su `worker_context` ya trae intentos previos, handoffs de padres y el `last_failure_error` real (ej. worker muerto por bug session-save en vez de fallo del trabajo).
3. **Separar proyectos:** filtrar por prefijo del título (ej. tarjetas F* de un plan vs. resto) para responder 'de esos cuáles faltan' sin mezclar frentes.
4. **Criterio de cierre:** nunca proponer cerrar una tarjeta cuya acceptance exige evidencia pendiente (corridas reales commiteadas, review con perfil distinto). Blocked es un estado legítimo si el bloqueo es externo (cuota 429, OK humano, login manual).

## Pitfalls
- El tool kanban lista máx 200 y 50 por defecto; en tableros de 100+ usar siempre el CLI `--json` y contar con código.
- Responder 'qué tomamos al inicio' desde la fecha de `created_at` de las tarjetas, no desde el resumen de la conversación (las sesiones se compactan y pierden el origen).
