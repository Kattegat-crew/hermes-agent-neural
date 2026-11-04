---
name: hermes-profile-inventory
description: "Use when auditing deployed Hermes profile inventory."
tags: [hermes, perfiles, profiles, inventory, routing, auditoria, devops]
version: 1.0.0
author: Ragnar
triggers:
  - perfiles: cuántos perfiles / lista de perfiles / inventario de perfiles / qué perfiles existen
  - numero: qué número tiene / a qué chat está asociado / a qué perfil enruta X
  - rutas: profile_routes / multiplex_profiles / @lid / s.whatsapp.net
  - auditoria: auditar despliegue / qué hay desplegado / estado de perfiles de clientes
---

# Hermes Profile Inventory — auditar perfiles desplegados

Procedimiento para responder con evidencia preguntas como "¿cuántos perfiles hay?", "¿qué número tiene asociado X?", "¿está desplegado golden-game?". NO asumir: auditar en vivo (el estado cambia con cada limpieza/consolidación).

## Dónde vive cada cosa

- **Perfiles ACTIVOS** → `/opt/data/profiles/<name>/` (en contenedor; host `/root/hermes-agent-legacy-docker/data/profiles/`). Cada perfil tiene su propio `config.yaml` (model/provider/base_url), `profile.yaml` (description + ui_meta) y `SOUL.md`.
- **Perfil PRINCIPAL (default/Ragnar)** → NO tiene directorio bajo `profiles/`; su config es `/opt/data/config.yaml`. El config principal NO tiene sección `profiles:` top-level — el ruteo vive en `gateway.profile_routes` + `gateway.multiplex_profiles: true`.
- **Backups de perfiles borrados** → `/opt/data/backups/` (p. ej. `profiles-before-delete-20260822/{ragnarcho,shared}`).
- **Plantillas de clientes SIN desplegar** → `/opt/data/hermes-casinos-repo/profiles/{golden-game,lucky-club}/` (AGENTS.md/MEMORY.md/SOUL.md/config.yaml listos, aún sin montar como perfiles activos).

## Pasos (rápidos, sin hermes CLI en el contenedor)

1. `find / -maxdepth 6 -name "profile.yaml" 2>/dev/null | grep -v proc | grep -v backups` → nombres de perfiles activos.
2. `grep -n -A12 "profile_routes:" /opt/data/config.yaml` → rutas por chat (fuente de verdad del ruteo). Confirmar `multiplex_profiles: true` (sin él las rutas NO aplican).
3. `ls /opt/data/backups/*/` → perfiles retirados (mencionar que existen backups si se consulta por ellos).
4. `ls /opt/data/hermes-casinos-repo/profiles/` → perfiles de clientes en plantilla sin desplegar.

## Formas de chat_id para UNA misma ruta (WhatsApp)

El config suele tener las 3 formas del mismo chat apuntando al mismo perfil (ej. Chucho → roshi):

- `153580212334603@lid` — bridge moderno (el que confirma la sesión en `state.db`)
- `573334011599@s.whatsapp.net` — JID legacy
- `573334011599` — número plano

No borrar las formas legacy aunque parezcan duplicados; cubren distintos path del bridge.

## Pitfalls

- Los números en memoria pueden diferir de las rutas en config: el **config es la fuente de verdad** del ruteo. Ante duda, `SELECT DISTINCT chat_id, display_name FROM sessions WHERE source='whatsapp'` en `state.db`.
- No el mismo segmentar perfiles: distinguir activo (dir en `/opt/data/profiles/`) vs plantilla (en repo) vs eliminado (solo backup).
- `state.db` de sesiones y los respaldos cambian con cada limpieza — este inventario se re-audita en vivo, nunca se responde de memoria.

## Estado canónico (actualizado 26/08/2026)

- **12 activos:** `default` (Ragnar, este contenedor) + 11 bajo `profiles/`:
  - `roshi` (asistente técnico Chucho, ruteado por WhatsApp)
  - `vigia` (mantenimiento/observabilidad, ruteado por Discord)
  - `comms` (comunicaciones corporativas — **pendiente: no tiene skills materializadas**)
  - 8 especialistas NeuralCrew anoche con Jesús: `bragi` (Content), `brokkr` (Web), `freyja` (Social), `heimdall` (Analytics), `hermodr` (Connect), `sindri` (Producer), `ullr` (Leads), `vili` (Ads) — todos ruteados por Discord.
- **2 eliminados con backup:** `ragnarcho` (pre-consolidación), `shared`.
- **2 plantillas sin desplegar:** `golden-game`, `lucky-club` (repositorio `hermes-casinos-repo/`).

Nota skills: los perfiles usan symlinks a `/opt/data/skills` (core), `/opt/data/skills-especialistas` y `/opt/data/skills-ext` — NO copias. Cada perfil tiene su grafo de skills en `skills/graphify-out/graph.json` (regenerar con `/opt/data/scripts/build_skills_graph.py --all-profiles`).

Actualizar este bloque solo al constatar cambios reales con los comandos de arriba.