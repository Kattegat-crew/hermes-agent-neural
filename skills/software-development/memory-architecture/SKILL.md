---
name: memory-architecture
description: "Use when routing a fact/procedure to the right memory layer."
tags: [memoria, memory, enrutamiento, routing, persistencia, capas, knowledge]
version: 1.0.0
author: Ragnar
license: MIT
metadata:
  hermes:
    tags: [memory, architecture, routing, persistence, knowledge]
    category: devops
    related_skills: [engram-memory-system, brain-knowledge-base, context-monitoring]
---

# Arquitectura de Memoria de Ragnar (3 capas + enrutamiento)

Ragnar NO usa una memoria monolítica. Hay capas separadas por función y por vida útil. El objetivo es evitar el desbordamiento y las decisiones basadas en información caducada.

## Las 3 capas principales

### 1. Memoria persistente de Hermes (MEMORY.md + USER.md) — hechos durables que me acompañan en CADA sesión

**Qué va aquí:**
- Identidad del negocio (NeuralCrew Labs, Digital Expressions)
- Clientes (Golden Game, Paradise/Lucky Brothers) y sus datos de marca
- Infraestructura crítica (servidores DEV/PROD, WhatsApp bridge, Vaultwarden)
- Políticas de pago y aprobaciones, accesos a servidores
- Convenciones permanentes con el usuario

**Reglas:**
- Presupuesto duro **100k chars** (memoria) / **8k chars** (perfil usuario).
- Cuando se llena → consolidar o reemplazar entradas viejas en **un solo batch** (`operations` array).
- **NUNCA** código fuente, rutas de archivos, ni estados temporales de tareas.
- Entradas como hechos declarativos, no como instrucciones a mí mismo.

### 2. Skills (`/opt/data/skills/`) — procedimientos reutilizables

**Qué va aquí:**
- Workflows, protocolos, patrones, pitfalls que aprendo al hacer una tarea.
- Se cargan **bajo demanda** (`skill_view` / `skills_list`), no se inyectan en el prompt.

**Regla:** *procedimientos y lecciones → skill*; *hechos universales → memoria*.

### 3. Bóveda de conocimiento (`/opt/vault/` + `/opt/vps-brain/`) — truths documentales

- **`/opt/vault/`** (`ESTRATEGIA-EMPRESA.md`, `REPOS-ARQUITECTURA.md`, `APIS-INTEGRACIONES.md`): source of truth permanente de negocio/repos/APIs.
- **`/opt/vps-brain/HISTORIAL_Y_CONTEXTO_VPS.md`**: bitácora de cambios de infraestructura y servidores.

## Capas complementarias

- **Engram MCP** (`mem_search`/`mem_save`/`mem_context`): memoria episódica cross-sesión para decisiones técnicas y contexto de proyectos. Ver skill `engram-memory-system`.
- **`sessions/`**: historial de conversaciones (memoria de trabajo).
- **`/opt/data/brain/`** (grafo `memory_graph.py`): notas de clientes y campañas.

## Principio rector

> **"La memoria describe el sistema y al usuario, no el código."**

## Protocolo de enrutamiento (decide ANTES de escribir)

| Detalle / conocimiento | Dónde va |
|---|---|
| Hecho de negocio, preferencia, identidad, infra | **Memoria** (MEMORY.md / USER.md) |
| Procedimiento, workflow, lección, pitfall | **Skill** (skill_manage) |
| Verdad documental de negocio/repos/APIs | **Vault** (`/opt/vault/`) |
| Cambio de servidor / infra / puerto | **Bitácora VPS** (`/opt/vps-brain/`) |
| Decisión técnica, contexto de proyecto | **Engram** (`mem_save`) |
| Nota de cliente, campaña, concepto o estándar de negocio | **Brain** (`/opt/data/brain/`, carpeta existente + kebab-case + actualizar `index.md`) |
| **Código fuente** | **SOLO Git** en su repo físico — NUNCA en memoria |

## Regla de oro de la escritura

Siempre preguntar en este orden:
1. ¿Es un procedimiento que aprendo? → **Skill**
2. ¿Es un hecho de negocio durable? → **Memoria**
3. ¿Es un cambio de servidor? → **Bitácora VPS**
4. ¿Es código o estado de un archivo? → **Git** (inspección en vivo, Zero-Stale-State)
5. ¿Es contexto efímero de una sesión? → **historial de sesiones / engram**, no memoria

## Cierre de sesión (rutina de guardado)

Una jornada con trabajo sustantivo se cierra en **cuatro** capas, no en una. La pregunta correcta no es «¿lo guardé?» sino «¿en cuál de las cuatro va?»:

1. **Engram** — resumen de sesión (`mem_session_summary`: goal / instructions / discoveries / accomplished / next steps). Automatizado por el cron `guardar-diario-memoria` (23:00).
2. **Memoria Hermes** — solo si el Admin pide documentar (regla de `USER.md`) o si apareció un **hecho durable nuevo** (identidad, cliente, infra, política, convención). Consolidar entradas existentes antes de añadir.
3. **Brain** — una nota por tema durable (cliente, campaña, concepto, estándar) en la carpeta **existente** que corresponda + enlace en `index.md`. **NO es automático**: el cron nocturno solo INDEXA el grafo sobre los archivos que ya existen; no crea notas. Si nadie escribe, el brain no crece.
4. **Git** — si hubo código o documentación de repo, el commit **es** la evidencia. Sin commit, no hay entrega.

**Automatización real hoy:** `guardar-diario-memoria` (23:00) → Engram; `brain-graph-update-noche` (3:30) → índice del grafo del brain. Todo lo demás es manual o a petición del Admin.

**Consulta del brain: primero el grafo, NO leer los archivos.** El brain tiene cientos de notas (377 .md en sep-2026): leerlas todas es imposible y caro. Orden correcto:

1. `graphify query "<tema>" --graph /opt/data/brain/graphify-out/graph.json --budget 2000` — recorrido BFS con presupuesto de tokens; devuelve los nodos relevantes y sus vecinos. Es la vía principal.
2. `graphify explain "<nodo>"` — explicación en lenguaje llano de un nodo y su entorno (cuando el query devuelve un nodo cuyo contexto no queda claro).
3. `graphify god-nodes --top 10` — los nodos más conectados, para saber qué es estructural del brain.
4. `python3 /opt/data/tools/memory_graph.py "<tema>"` — helper local (substring, **sensible a acentos**: usar el término tal cual aparece, con tildes).
5. **Solo si el grafo apunta a una nota concreta cuyo detalle hace falta** → `read_file` de esa nota (y no de otra).

El grafo también aprende: `graphify save-result --question ... --answer ... --nodes ... --outcome useful|dead_end|corrected` y `graphify reflect` agregan esas señales en `graphify-out/reflections/LESSONS.md`. Úsalo cuando una consulta al grafo haya servido (o llevado a un callejón sin salida): es la forma de que el brain priorice lo que de verdad se usa.

**Pitfalls del brain:**
- El grafo se construye con `graphify extract`, que **llama a un modelo de PAGO**: no reconstruirlo a mano sin autorización; el cron de las 3:30 lo hace.
- La consulta al grafo (`memory_graph.py`) es **sensible a acentos**: `"modulos neural"` devuelve 0 y `"Módulos Neural"` encuentra los nodos.
- Respetar `brain/AGENTS.md`: no crear carpetas nuevas sin autorización del Admin.

## Reglas de límite

- **No duplicar** en memoria lo que ya vive en engram (memoria ~100k, engram sin límite).
- **Fact stale dentro de una semana** → historial de sesiones, no memoria.
- **Zero-Stale-State Protocol** aplica a todo código: inspeccionar el repo físico en vivo antes de tocar; no asumir estados por turnos previos.
