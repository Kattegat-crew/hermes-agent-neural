---
name: hermes-session-organization
description: "Use when classifying or auto-titling Hermes sessions."
version: 1.0.0
author: Ragnar
category: autonomous-ai-agents
---

# Organizar y clasificar sesiones de Hermes (títulos, proyectos, plugins)

Dónde vive la verdad cuando se quiere agrupar/renombrar conversaciones de la flota (verificado 17-sep-2026 en código y BD de v0.21.0, sin especular):

## Títulos de sesión

- `sessions` en `state.db` trae `title` + `title_source` (`llm` / `manual` / `derived` / NULL). Un chat sin título ni fuente es sesión vieja anterior al backfill — no un bug.
- Hermes autotitula en **dos fases**: nombre instantáneo al abrir la sesión + refinado con modelo barato después. No hay que editar títulos a mano para "catalogar": ya son datos editables.
- Existe `/title` en el gateway (Telegram y Discord) que reescribe el título de la sesión (en Telegram renombra además el tema del chat).

## Agrupación por proyectos (sidebar Desktop)

- El Desktop agrupa una sesión bajo un proyecto cuando su `cwd` cae bajo la carpeta del proyecto — coincidencia de prefijo más largo (`hermes_cli/projects_db.py`). No existe `project_id` en sesiones: la pertenencia se deriva, no se etiqueta.
- Las sesiones de gateway nacen con `cwd=NULL` (medido: Telegram 111/115, Discord 71/71, WhatsApp 35/35) → **nunca se auto-agrupan** en el sidebar por sí solas.
- Un proyecto pide una carpeta: anclar a directorios que YA existen (p.ej. `/root/marketing-campaign-generator`), nunca crear carpetas nuevas para que cuadre la taxonomía.

## Patrón para agrupar sesiones de chat sin tocar el core

1. Tabla sidecar en `projects.db` (`session_projects`: chat_id/plataforma → proyecto) — clasificación 100% en BD, sin depender de `cwd`.
2. Cron vigilante (cada ~10 min) que lee sesiones nuevas y las clasifica con modelo barato; el título se reescribe con prefijo `[Proyecto]` para que el agrupamiento se vea en cualquier plataforma, no solo en el Desktop.
3. Plugin del Desktop (mismo mecanismo que `nan-usage`) que lee la tabla sidecar y agrupa el sidebar, con botón de reclasificación.

## Pitfalls

- **Renombrado en masa = dry-run primero.** Generar el mapa de clasificación completo y presentarlo en seco para aprobación ANTES de escribir un solo título (dry-run con `NULL`/solo lectura). El Admin ve esos títulos todos los días y un renombrado malo no tiene undo.
- No asumir que una sesión trae `cwd` ni que el agrupamiento nativo sirve fuera del Desktop: medir el NULL-rate real por plataforma antes de diseñar.
- El título lo puede pisar el usuario a mano (`title_source` cambia a `manual`) — el catalogador debe respetar los manuales y solo tocar los `llm`/NULL.
