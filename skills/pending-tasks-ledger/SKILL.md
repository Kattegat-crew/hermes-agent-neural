---
name: pending-tasks-ledger
description: Use when managing the agency pending-tasks ledger store.
version: 1.0.0
author: Ragnar (NeuralCrew Labs)
license: proprietary
metadata:
  hermes:
    tags: [pendientes, ledger, tareas]
    related_skills: [hermes-cron-health, tickets-tecnicos-foro]
---

# pending-tasks-ledger

## When to Use
- Cuando el Admin pide la lista de pendientes o pregunta qué falta.
- Al cerrar, añadir o consolidar tareas del store canónico tras una sesión de trabajo.

Store canónico: `/opt/hermes-agent-data/brain/tasks/pending.jsonl` (append-only, con guard). CLI: `python3.12 /opt/hermes-agent-data/scripts/pending_tasks.py {list,add,close,state,sync,verify,history,import-seed}`. Cada `close` regenera `pending.md` automáticamente — no editar el .md a mano.

## Procedimiento (lote de cierre/actualización)

1. Leer estado real: `list` (o el jsonl con python) y clasificar abiertos por área/prioridad.
2. Mapear cada orden del Admin a IDs concretos ANTES de cerrar. Una frase amplia ("ya quedó", "ya avanzamos bastante") cubre varios ítems; distinguir cierre real de aparcado-con-avance (cerrar con nota "Reabrir si <condición>").
3. Cerrar SIEMPRE con `--evidencia` citando la decisión que autoriza (fuente + contenido), nunca por deducción propia.
4. Colapsar duplicados/obsoletos en la MISMA pasada: N tickets del mismo tema → 1 tarea paraguas nueva con el objetivo consolidado; cerrar cada reemplazado referenciando el ID nuevo.
5. Añadir los nuevos con `--area --prioridad --fuente`. Lo diagnosticado-y-resuelto en la misma sesión se añade YA CERRADO con la evidencia — la auditoría posterior del Admin revisa exactamente eso.
6. Verificar: `verify` debe responder "GUARD PENDING — OK (N ítems, M abiertos)"; releer los abiertos y resumir al Admin con el conteo real.

## Visibilidad para el Admin (superficies vivas ya desplegadas)
El ledger se ve en dos superficies vivas — mantener ambas sincronizadas tras cada cambio del store:
1. **Portal kanban `https://reels.neuralcrewlabs.com/tareas/`** (detrás del SSO universal,
   grupo admins): listas por dueño (jonathan / chucho / compartido), prioridad y área al
   crear, y sección «Cerradas» por columna con reabrir. Backend `tools/portal-tareas/server.py`
   (systemd `portal-tareas.service` en DEV, bind a la IP de Tailscale) escribe en el MISMO
   jsonl canónico: altas/cierres del portal llegan con `fuente: portal:<actor>` en el events
   log y son cierres válidos con evidencia. `GET /api/tasks` devuelve `items` (abiertas) Y
   `cerradas` — no asumir que el endpoint solo trae abiertas.
2. **Mensaje fijado en Telegram editado in-place**: `python3.12 tools/portal-tareas/telegram_pin.py`
   tras cada cambio del store (usar `--force` cuando cambia el reparto de dueños, no solo el contenido).

Nunca publicar la lista sin SSO (tiene clientes, sedes y montos). UX validada por el Admin:
cerrar/chulear una tarea NUNCA debe parecer que se pierde — mostrar a dónde fue (abrir la
sección «Cerradas» + toast con deshacer). Detalles de deploy del portal en `web-portal-deploy`.

## Reglas duras

- Prohibido borrar: append-only. Los cierres con evidencia SON el historial.
- Reconstruir listas para el Admin desde el ledger/state.db con fecha y fuente — nunca desde memoria ni desde resúmenes de sesión.
- Un ítem sin evidencia de cierre queda abierto, aunque "se sepa" que ya está hecho.
- Al reemplazar una tarea por otra (enfoque cambia, no desaparece), cerrar la vieja citando el ID nueva — nunca dejar ambas abiertas ni perder el contexto.
- Un trabajo que ya tiene ticket en `tickets-tecnicos-foro` NO se añade al ledger: se cierra la tarea con puntero al ticket. Si existe en ambos (tareas abiertas + ticket del mismo objetivo), colapsar a una sola fuente — el ticket — y cerrar el resto citándolo. Regla completa en `tickets-tecnicos-foro`, seccion frontera.
