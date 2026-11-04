---
name: oauth-connection-ops
description: "Use when verifying or fixing OAuth connections and tokens"
version: 2.0.0
author: NeuralCrew
tags: [oauth, conexiones, tokens, activepieces, google, verificacion, credenciales, reauth]

---

# Oauth Connection Ops

## Propósito y Alcance
Habilidad consolidada de clase que centraliza los flujos de:
- `agent-connection-governance`
- `cloudflare-access-api`
- `delegated-credential-access`
- `google-oauth-reauth`
- `google-oauth-reauth-ops`
- `mcp-oauth-remote-gateway`
- `oauth-connection-gateway`
- `oauth-connection-health-audit`
- `oauth-connection-verification`
- `twenty-selfhost-auth`
- `unify-service-logins`

## Arquitectura y Protocolos
Esta skill opera como despacho unificado. El detalle procedural y gotchas específicos de cada caso se encuentran preservados en:
`references/`

## Casos de Uso Disponibles
- **agent-connection-governance**: Ver [references/agent-connection-governance.md](file:///root/hermes-agent-legacy-docker/skills/core/oauth-connection-ops/references/agent-connection-governance.md)
- **cloudflare-access-api**: Ver [references/cloudflare-access-api.md](file:///root/hermes-agent-legacy-docker/skills/core/oauth-connection-ops/references/cloudflare-access-api.md)
- **delegated-credential-access**: Ver [references/delegated-credential-access.md](file:///root/hermes-agent-legacy-docker/skills/core/oauth-connection-ops/references/delegated-credential-access.md)
- **google-oauth-reauth**: Ver [references/google-oauth-reauth.md](file:///root/hermes-agent-legacy-docker/skills/core/oauth-connection-ops/references/google-oauth-reauth.md)
- **google-oauth-reauth-ops**: Ver [references/google-oauth-reauth-ops.md](file:///root/hermes-agent-legacy-docker/skills/core/oauth-connection-ops/references/google-oauth-reauth-ops.md)
- **mcp-oauth-remote-gateway**: Ver [references/mcp-oauth-remote-gateway.md](file:///root/hermes-agent-legacy-docker/skills/core/oauth-connection-ops/references/mcp-oauth-remote-gateway.md)
- **oauth-connection-gateway**: Ver [references/oauth-connection-gateway.md](file:///root/hermes-agent-legacy-docker/skills/core/oauth-connection-ops/references/oauth-connection-gateway.md)
- **oauth-connection-health-audit**: Ver [references/oauth-connection-health-audit.md](file:///root/hermes-agent-legacy-docker/skills/core/oauth-connection-ops/references/oauth-connection-health-audit.md)
- **oauth-connection-verification**: Ver [references/oauth-connection-verification.md](file:///root/hermes-agent-legacy-docker/skills/core/oauth-connection-ops/references/oauth-connection-verification.md)
- **twenty-selfhost-auth**: Ver [references/twenty-selfhost-auth.md](file:///root/hermes-agent-legacy-docker/skills/core/oauth-connection-ops/references/twenty-selfhost-auth.md)
- **unify-service-logins**: Ver [references/unify-service-logins.md](file:///root/hermes-agent-legacy-docker/skills/core/oauth-connection-ops/references/unify-service-logins.md)
