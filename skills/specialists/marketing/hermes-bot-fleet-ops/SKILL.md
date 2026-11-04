---
name: hermes-bot-fleet-ops
description: "Use when auditing or wiring a Hermes bot fleet."
tags: [hermes, perfiles, flota, bots, engram, compresion, crons]
version: 1.0.0
author: Ragnar
metadata:
  hermes:
    tags: [perfiles, flota, bots, engram, compression, rate-limit, handoff, pipeline, auditoria]
    category: devops
    related_skills: [hermes-team-ops, hermes-multiprofile-cron-ops, hermes-multiprofile-model-config, hermes-production-deployment, hermes-admin-operations]
---

# Hermes Bot Fleet Ops — Auditoría y cableado de equipos de bots por perfil

Cómo auditar y conectar una flota de perfiles Hermes que trabajan como equipo
(pipeline de marketing, agentes especializados): verificar que cada perfil tenga
modelo/contexto/compresión/Engram/crons correctos, repartir modelos para no
chocar rate-limit, y diseñar el handoff entre bots.

## When to Use

- Hay que perfilar o auditar un equipo de bots (ej. los 8 dioses + comms de NeuralCrew).
- Pregunta tipo: "¿cada bot tiene su Engram? ¿qué modelo usa? ¿tiene compresión?".
- Hay que cablear un pipeline multi-bot y decidir cómo pasa el trabajo de un bot al siguiente.
- Antes de activar una flota en producción: revisar distribución de modelos (una sola
  API key = un solo bucket de rate-limit).

## Prerequisites

- Perfiles servidos visibles en `gateway_state.json` (campo `served_profiles`) o `ls profiles/`.
- El binario `hermes` del host es wrapper docker exec SIN `-e HERMES_HOME` → usar
  `docker exec -e HERMES_HOME=/opt/data/profiles/<p> hermes-agent hermes ...` para tocar un perfil.
- `hermes config set` sin `--profile` puede escribir en un perfil distinto del default
  (verificado: escribió en profiles/sindri); leer la salida "✓ Set ... in <ruta>".

## Quick Reference

Auditoría de un perfil:

```bash
p=<perfil>; cfg=/root/hermes-agent-legacy-docker/data/profiles/$p/config.yaml
grep -E "^(  )?(provider|default|base_url):" $cfg | head -4   # modelo activo
grep -c engram $cfg                                          # 0 = sin MCP Engram
grep -nE "^compression:|^  compression:" $cfg                # bloque raíz vs auxiliary
grep -n -A6 "^  compression:" $cfg                           # detalle auxiliary
ls profiles/$p/cron/                                         # jobs.json o solo esqueleto
```

Estructura top-level: `grep -nE "^[a-z_]+:" $cfg | head -30`.

## Procedure

1. **Listar la flota real**: `cat gateway_state.json | python3 -c "import json,sys; print(json.load(sys.stdin).get('served_profiles'))"` — usar ESTO, no asumir por nombres.
2. **Auditar 4 ejes por perfil** (batch en un for):
   - Modelo activo (`model.provider` + `model.default`).
   - Engram MCP: `grep -c engram config.yaml` — 0 = sin memoria persistente propia.
   - Compresión: distinguir **bloque raíz `compression:`** (`enabled: true`, `threshold: 0.5`, `target_ratio`, `protect_last_n` — la compresión AUTOMÁTICA solo corre con el bloque raíz) de **`auxiliary.compression`** (solo el modelo usado para comprimir, no activa la compresión).
   - Crons: `ls profiles/<p>/cron/` — `jobs.json` presente o solo esqueleto (`executions.db`, `output`, `ticker_*` = sin jobs).
3. **Repartir modelos**: si varios bots usan el mismo modelo contra una sola API key, comparten bucket de rate-limit. La tabla del plan del equipo (NaN: deepseek-v4-flash / gemma4 / mimo-v2.5 / qwen3.6) asigna un primario distinto por bot.
4. **Modelar el handoff ANTES de cablear**: sin un mecanismo de "el anterior terminó", los bots se pisan. Dos patrones en diseño (ver references/):
   - **Manifest compartido**: cada etapa escribe `campaign.yaml` + `estado.json` en un workspace/Drive común; un orquestador (ActivePieces) detecta el cambio de etapa y dispara al siguiente vía webhook al gateway.
   - **Hermes kanban**: board durable por campaña (hermes kanban <verb>), workers reclaman tareas.
5. **Crons de memoria por bot**: cada agente del equipo debe tener SU `guardar-diario-memoria` (patrón: uno por perfil, nunca central).

## Pitfalls

- **No confundir `auxiliary.compression` con compresión activa**: el bloque raíz `compression:` es el que hace la compresión automática de contexto; `auxiliary.compression` solo dice qué modelo comprime (aparece en TODOS los perfiles con providers NaN aunque el bloque raíz no exista).
- **`context_length` en `providers:` no es la ventana activa**: son entradas de catálogo por modelo; la ventana efectiva la fija el bloque `model` + compresión. Verificar contexto objetivo (ej. 256K = qwen3.6 262144) en el modelo asignado.
- **Perfiles "listos" ≠ perfiles conectados**: un perfil puede tener name/SOUL/skills y esqueleto de cron sin tener Engram MCP, compresión raíz ni jobs.json — auditar los 4 ejes antes de reportar "listo".
- Skills de roster/handoff relacionadas (`hermes-team-ops`, `hermes-multiprofile-*`) pueden ser user-owned → `hermes curator adopt <skill>` para editarlas.

## Verification

- Tras configurar Engram en un perfil: `grep -c engram config.yaml` > 0 y el MCP aparece en `config.yaml` (sección `mcp.servers` o equivalente del perfil).
- Tras activar compresión: bloque raíz `compression.enabled: true` presente en el perfil.
- Tras crear crons: `profiles/<p>/cron/jobs.json` existe con `state: scheduled` y `next_run_at` futuro.

## References

- `references/equipo-marketing-auditoria-2026-08-26.md` — auditoría real de la flota (8 dioses + comms): tablas por perfil, gaps, propuesta de handoff.