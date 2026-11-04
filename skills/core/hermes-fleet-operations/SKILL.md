---
name: hermes-fleet-operations
description: "Use when deploying or configuring Hermes fleet profiles"
version: 2.0.0
author: NeuralCrew
tags: [hermes, flota, perfiles, multiprofile, deploy, gateway, cron, roster]

---

# Hermes Fleet Operations

## Propósito y Alcance
Habilidad consolidada de clase que centraliza los flujos de:
- `hermes-bot-avatars`
- `hermes-bot-fleet-ops`
- `hermes-fleet-lifecycle`
- `hermes-fleet-model-ops`
- `hermes-multiprofile-cron-ops`
- `hermes-multiprofile-deploy`
- `hermes-multiprofile-gateway-ops`
- `hermes-multiprofile-model-config`
- `hermes-profile-inventory`
- `hermes-profile-routing`
- `hermes-roster-implementation`
- `hermes-specialist-agents-deploy`

## Arquitectura y Protocolos
Esta skill opera como despacho unificado. El detalle procedural y gotchas específicos de cada caso se encuentran preservados en:
`references/`

## Casos de Uso Disponibles
- **hermes-bot-avatars**: Ver [references/hermes-bot-avatars.md](file:///root/hermes-agent-legacy-docker/skills/core/hermes-fleet-operations/references/hermes-bot-avatars.md)
- **hermes-bot-fleet-ops**: Ver [references/hermes-bot-fleet-ops.md](file:///root/hermes-agent-legacy-docker/skills/core/hermes-fleet-operations/references/hermes-bot-fleet-ops.md)
- **hermes-fleet-lifecycle**: Ver [references/hermes-fleet-lifecycle.md](file:///root/hermes-agent-legacy-docker/skills/core/hermes-fleet-operations/references/hermes-fleet-lifecycle.md)
- **hermes-fleet-model-ops**: Ver [references/hermes-fleet-model-ops.md](file:///root/hermes-agent-legacy-docker/skills/core/hermes-fleet-operations/references/hermes-fleet-model-ops.md)
- **hermes-multiprofile-cron-ops**: Ver [references/hermes-multiprofile-cron-ops.md](file:///root/hermes-agent-legacy-docker/skills/core/hermes-fleet-operations/references/hermes-multiprofile-cron-ops.md)
- **hermes-multiprofile-deploy**: Ver [references/hermes-multiprofile-deploy.md](file:///root/hermes-agent-legacy-docker/skills/core/hermes-fleet-operations/references/hermes-multiprofile-deploy.md)
- **hermes-multiprofile-gateway-ops**: Ver [references/hermes-multiprofile-gateway-ops.md](file:///root/hermes-agent-legacy-docker/skills/core/hermes-fleet-operations/references/hermes-multiprofile-gateway-ops.md)
- **hermes-multiprofile-model-config**: Ver [references/hermes-multiprofile-model-config.md](file:///root/hermes-agent-legacy-docker/skills/core/hermes-fleet-operations/references/hermes-multiprofile-model-config.md)
- **hermes-profile-inventory**: Ver [references/hermes-profile-inventory.md](file:///root/hermes-agent-legacy-docker/skills/core/hermes-fleet-operations/references/hermes-profile-inventory.md)
- **hermes-profile-routing**: Ver [references/hermes-profile-routing.md](file:///root/hermes-agent-legacy-docker/skills/core/hermes-fleet-operations/references/hermes-profile-routing.md)
- **hermes-roster-implementation**: Ver [references/hermes-roster-implementation.md](file:///root/hermes-agent-legacy-docker/skills/core/hermes-fleet-operations/references/hermes-roster-implementation.md)
- **hermes-specialist-agents-deploy**: Ver [references/hermes-specialist-agents-deploy.md](file:///root/hermes-agent-legacy-docker/skills/core/hermes-fleet-operations/references/hermes-specialist-agents-deploy.md)
- **pm-dependency-env-recovery**: Ver [references/pm-dependency-env-recovery.md](file:///root/hermes-agent-legacy-docker/skills/core/hermes-fleet-operations/references/pm-dependency-env-recovery.md) — síntoma `cannot read dependency environment: .../facts.json`, diagnóstico con `pm.cli doctor` + smoke `hermes -p <perfil> --version`, override `HERMES_PYTHON` del test-env cuando el runner no puede auto-activarse, y bootstrap de worktree ANTES de despachar workers Kanban.
- **migracion-raices-skills-al-canon**: Ver [references/migracion-raices-skills-al-canon.md](file:///root/hermes-agent-legacy-docker/skills/core/hermes-fleet-operations/references/migracion-raices-skills-al-canon.md)
- **ncl-google-connections**: Ver [references/ncl-google-connections.md](file:///root/hermes-agent-legacy-docker/skills/core/hermes-fleet-operations/references/ncl-google-connections.md)
- **langfuse-fleet-observability**: Ver [references/langfuse-fleet-observability.md](file:///root/hermes-agent-legacy-docker/skills/core/hermes-fleet-operations/references/langfuse-fleet-observability.md) — trazabilidad LLM con Langfuse v2 (2.95.11, OTLP=404, solo REST legacy), plugin independiente `langfuse-fleet` (12 homes + canario separado), y pitfall de preservar `spool.db` (backup API, nunca `cp` con WAL vivo) durante deploy/rollback.
