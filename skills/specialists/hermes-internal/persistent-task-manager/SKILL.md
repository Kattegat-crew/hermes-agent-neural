---
name: persistent-task-manager
description: >-
  Use when tracking tasks across sessions (Brain Wiki/Notion). Manage persistent task tracking across sessions. Maintains Brain Wiki tasks file and syncs with Notion DB. Loads tasks at session start, updates on every task change. hermes: tags: [tasks, tracking, persistence, notion, brain-wiki]
version: 1.0.0
author: Ragnar
license: MIT
metadata:---

# Persistent Task Manager

Gestiona las tareas pendientes de forma persistente entre sesiones. Sincroniza Brain Wiki + Notion.

## Cuándo Usar

- **ALWAYS** al iniciar sesión → cargar tareas desde Brain Wiki
- **ALWAYS** al completar una tarea → actualizar estado
- **ALWAYS** al recibir una nueva tarea → agregar al archivo + Notion
- **ALWAYS** al cambiar prioridad o estado → actualizar

## Archivos

- **Fuente de verdad:** `/opt/data/brain/tasks/pending.md`
- **Notion DB:** ID `349853a7-3369-8139-a73e-d0e4213c215c` (Tareas Pendientes)
- **Legacy:** `/opt/data/home/TASKS.md` (no usar, solo legacy)

## Pasos

### 1. Cargar tareas (al inicio de sesión)

```python
# Leer Brain Wiki tasks
with open('/opt/data/brain/tasks/pending.md', 'r') as f:
    tasks_content = f.read()

# Parsear tareas pendientes (estado ⏳)
# Mostrar al usuario las tareas activas
```

### 2. Agregar nueva tarea

1. Leer `/opt/data/brain/tasks/pending.md`
2. Agregar fila en sección "En curso" con estado "⏳ Pendiente"
3. Escribir archivo completo
4. Actualizar Notion DB:
   ```python
   import os, requests
   headers = {
       'Authorization': f'Bearer {os.environ.get("NOTION_API_KEY", "")}',
       'Notion-Version': '2022-06-28'
   }
   resp = requests.post('https://api.notion.com/v1/pages', json={
       'parent': {'database_id': '349853a7-3369-8139-a73e-d0e4213c215c'},
       'properties': {
           'Name': {'title': [{'text': {'content': 'Nueva Tarea'}}]},
           'Status': {'select': {'name': 'Pendiente'}},
           'Priority': {'select': {'name': 'Alta'}},
           'Module': {'rich_text': [{'text': {'content': 'Módulo'}}]}
       }
   }, headers=headers)
   ```
5. Confirmar al usuario: "Tarea agregada. Actualicé Brain Wiki y Notion."

### 3. Actualizar tarea completada

1. Cambiar estado de "⏳ Pendiente" a "✅ Hecho"
2. Mover a sección "Listo" si es necesario
3. Actualizar Notion (cambiar status a Done)
4. Confirmar al usuario

### 4. Actualizar tarea en progreso

1. Cambiar estado a "🔵 En curso"
2. Actualizar Notion
3. Confirmar al usuario

## Formato del Archivo

```markdown
---
title: "Tareas Pendientes — Nexa Labs / Ragnar"
created: 2026-04-20
updated: YYYY-MM-DD
tags: [tareas, tracking, persistencia, notion, brain-wiki]
---

# 📋 Tareas Pendientes — Nexa Labs / Ragnar

> Fuente de verdad: Brain Wiki. Sincronizado con Notion DB.

## En curso

| # | Tarea | Módulo | Prioridad | Estado |
|---|-------|--------|-----------|--------|
| N | Descripción de tarea | Módulo | Alta/Media/Baja | ⏳ Pendiente / 🔵 En curso / ✅ Hecho |

## Listo

| # | Tarea | Módulo |
|---|-------|--------|
| N | Tarea completada | Módulo |

## Sin empezar

*(vacío o tareas futuras)*
```

## Estados

- `⏳ Pendiente` — Tarea que se debe hacer
- `🔵 En curso` — Estoy trabajando en esto ahora
- `✅ Hecho` — Completada, mover a "Listo"

## Reglas

1. **SIEMPRE** actualizar Brain Wiki primero, luego Notion
2. **SIEMPRE** cargar tareas al inicio de sesión
3. **NUNCA** confiar solo en el tool `todo` para tracking cross-session
4. **NUNCA** duplicar archivos — un solo archivo de verdad en Brain Wiki
5. **SIEMPRE** confirmar al usuario cuando se actualice una tarea

## Pitfalls

- **No confundir** con el tool `todo` (solo session-local)
- **No olvidar** sincronizar con Notion — es lo que ven Jonathan y Chucho
- **No crear** múltiples archivos de tareas — un solo archivo en `/opt/data/brain/tasks/pending.md`
- **No asumir** que las tareas del Brain Wiki están sync con Notion — verificar

## Wiki Sync (Brain → Notion)

El script `/opt/data/scripts/wiki-to-notion-sync.py` sincroniza Brain Wiki con Notion:
- Lee archivos `.md` de Brain Wiki (entities/, concepts/, projects/, etc.)
- Crea/actualiza páginas en la DB Wiki de Notion (`335853a7-3369-813d-8d65-d11c0355c2cf`)
- Estado actual: 23 páginas sincronizadas (5 entities + 18 concepts)

Para ejecutar: `python3 /opt/data/scripts/wiki-to-notion-sync.py`

## Related

- `notion-integration` — API de Notion para actualizar DB
- `brain-knowledge-base` — Estructura del Brain Wiki
- `loop-protection` — Evitar loops al trabajar en tareas
