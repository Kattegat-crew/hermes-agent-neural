---
name: hermes-runtime-ops
description: "Use when operating or debugging the Hermes gateway"
version: 2.0.0
author: NeuralCrew
tags: [hermes, runtime, gateway, s6, docker, infra, diagnostico, fleet]

---

# Hermes Runtime Ops

## Propósito y Alcance
Habilidad consolidada de clase que centraliza los flujos de:
- `hermes-admin-operations`
- `hermes-ecosystem-tools`
- `hermes-gateway-http-api`
- `hermes-gateway-lifecycle-forensics`
- `hermes-gateway-ops`
- `hermes-gateway-s6-ops`
- `hermes-latency-diagnosis`
- `hermes-mcp-integration`
- `hermes-permisos-optdata`
- `hermes-prod-stack-operations`
- `hermes-production-deployment`
- `hermes-runtime-self-report`
- `hermes-s6-container-supervision`
- `hermes-session-forensics`
- `hermes-session-organization`
- `hermes-usage-cost-audit`
- `hermes-workspace-setup`

## Arquitectura y Protocolos
Esta skill opera como despacho unificado. El detalle procedural y gotchas específicos de cada caso se encuentran preservados en:
`references/`

## Casos de Uso Disponibles
- **hermes-admin-operations**: Ver [references/hermes-admin-operations.md](file:///root/hermes-agent-legacy-docker/skills/core/hermes-runtime-ops/references/hermes-admin-operations.md)
- **hermes-ecosystem-tools**: Ver [references/hermes-ecosystem-tools.md](file:///root/hermes-agent-legacy-docker/skills/core/hermes-runtime-ops/references/hermes-ecosystem-tools.md)
- **hermes-gateway-http-api**: Ver [references/hermes-gateway-http-api.md](file:///root/hermes-agent-legacy-docker/skills/core/hermes-runtime-ops/references/hermes-gateway-http-api.md)
- **hermes-gateway-lifecycle-forensics**: Ver [references/hermes-gateway-lifecycle-forensics.md](file:///root/hermes-agent-legacy-docker/skills/core/hermes-runtime-ops/references/hermes-gateway-lifecycle-forensics.md)
- **hermes-gateway-ops**: Ver [references/hermes-gateway-ops.md](file:///root/hermes-agent-legacy-docker/skills/core/hermes-runtime-ops/references/hermes-gateway-ops.md)
- **hermes-gateway-s6-ops**: Ver [references/hermes-gateway-s6-ops.md](file:///root/hermes-agent-legacy-docker/skills/core/hermes-runtime-ops/references/hermes-gateway-s6-ops.md)
- **hermes-latency-diagnosis**: Ver [references/hermes-latency-diagnosis.md](file:///root/hermes-agent-legacy-docker/skills/core/hermes-runtime-ops/references/hermes-latency-diagnosis.md)
- **hermes-mcp-integration**: Ver [references/hermes-mcp-integration.md](file:///root/hermes-agent-legacy-docker/skills/core/hermes-runtime-ops/references/hermes-mcp-integration.md)
- **hermes-permisos-optdata**: Ver [references/hermes-permisos-optdata.md](file:///root/hermes-agent-legacy-docker/skills/core/hermes-runtime-ops/references/hermes-permisos-optdata.md)
- **hermes-prod-stack-operations**: Ver [references/hermes-prod-stack-operations.md](file:///root/hermes-agent-legacy-docker/skills/core/hermes-runtime-ops/references/hermes-prod-stack-operations.md)
- **hermes-production-deployment**: Ver [references/hermes-production-deployment.md](file:///root/hermes-agent-legacy-docker/skills/core/hermes-runtime-ops/references/hermes-production-deployment.md)
- **hermes-runtime-self-report**: Ver [references/hermes-runtime-self-report.md](file:///root/hermes-agent-legacy-docker/skills/core/hermes-runtime-ops/references/hermes-runtime-self-report.md)
- **hermes-s6-container-supervision**: Ver [references/hermes-s6-container-supervision.md](file:///root/hermes-agent-legacy-docker/skills/core/hermes-runtime-ops/references/hermes-s6-container-supervision.md)
- **hermes-session-forensics**: Ver [references/hermes-session-forensics.md](file:///root/hermes-agent-legacy-docker/skills/core/hermes-runtime-ops/references/hermes-session-forensics.md)
- **hermes-session-organization**: Ver [references/hermes-session-organization.md](file:///root/hermes-agent-legacy-docker/skills/core/hermes-runtime-ops/references/hermes-session-organization.md)
- **hermes-usage-cost-audit**: Ver [references/hermes-usage-cost-audit.md](file:///root/hermes-agent-legacy-docker/skills/core/hermes-runtime-ops/references/hermes-usage-cost-audit.md)
- **hermes-workspace-setup**: Ver [references/hermes-workspace-setup.md](file:///root/hermes-agent-legacy-docker/skills/core/hermes-runtime-ops/references/hermes-workspace-setup.md)


---

## admission_conflict en WhatsApp: rutas duplicadas por persona (verificado 04-nov-2026)

Síntoma: el bridge conecta y recibe mensajes, pero cada mensaje muere con
`Error handling message: admission_conflict` y el usuario ve error en WhatsApp.

Causa: varias `profile_routes` para la misma persona (`<n>@lid`, `<n>@s.whatsapp.net` y `<n>`).
El matcher compara WhatsApp **entre formatos**, así que las tres coinciden con el mismo mensaje, empatan
en especificidad y `_runtime_profile` levanta `admission_conflict` antes de entregar.

Diagnóstico reproducible sin arrancar el gateway:

```python
from gateway.profile_routing import ProfileRoute
# construir las rutas sospechosas y contar coincidencias por chat_id
[r.name for r in rutas if r.matches("whatsapp", chat_id="<chat>", adapter_profile=None, user_id="<num>")]
```

Si devuelve más de una, es esto. Regla: **una sola ruta por persona**; el cross-format ya cubre lid, jid y número.

Corrección: `config.yaml` está protegido contra escritura del agente. Usar `hermes config set gateway.profile_routes '<json>'`
(el valor se parsea con `yaml.safe_load`, así que un array JSON es válido). Respaldo antes, y verificar después que
cada chat resuelve a exactamente una ruta y que las rutas de otras plataformas siguen ahí.

Reinicio: no se puede reiniciar el gateway desde dentro de sí mismo (SIGTERM mata el comando).
Lanzarlo desde el host: `ssh root@127.0.0.1 'setsid bash -c "sleep 20; systemctl restart hermes-agent.service" &'`
y confirmar en el log `✓ whatsapp connected` + un mensaje real respondido.
