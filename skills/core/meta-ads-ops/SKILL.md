---
name: meta-ads-ops
description: "Use when running Meta Ads campaigns via Composio"
version: 2.0.0
author: NeuralCrew
tags: [meta-ads, composio, pixel, capi, campanas, anuncios, facebook, instagram]

---

# Meta Ads Ops

## Propósito y Alcance
Habilidad consolidada de clase que centraliza los flujos de:
- `ad-library-research`
- `composio-social-publishing`
- `meta-ads-campaigns`
- `meta-ads-operations`
- `social-post-identification`
- `social-story-production`

- `destination-compliance-verticales`

- `meta-capi-tracking`

## Arquitectura y Protocolos
Esta skill opera como despacho unificado. El detalle procedural y gotchas específicos de cada caso se encuentran preservados en:
`references/`

## Casos de Uso Disponibles
- **ad-library-research**: Ver [references/ad-library-research.md](file:///root/hermes-agent-legacy-docker/skills/core/meta-ads-ops/references/ad-library-research.md)
- **composio-social-publishing**: Ver [references/composio-social-publishing.md](file:///root/hermes-agent-legacy-docker/skills/core/meta-ads-ops/references/composio-social-publishing.md)
- **meta-ads-campaigns**: Ver [references/meta-ads-campaigns.md](file:///root/hermes-agent-legacy-docker/skills/core/meta-ads-ops/references/meta-ads-campaigns.md)
- **meta-ads-operations**: Ver [references/meta-ads-operations.md](file:///root/hermes-agent-legacy-docker/skills/core/meta-ads-ops/references/meta-ads-operations.md)
- **social-post-identification**: Ver [references/social-post-identification.md](file:///root/hermes-agent-legacy-docker/skills/core/meta-ads-ops/references/social-post-identification.md)
- **social-story-production**: Ver [references/social-story-production.md](file:///root/hermes-agent-legacy-docker/skills/core/meta-ads-ops/references/social-story-production.md)
- **destination-compliance-verticales**: anuncios rechazados por el DESTINO en verticales restringidas (casino, apuestas): triage de rechazos y patron venue-first — ver [references/destination-compliance-verticales.md](file:///root/hermes-agent-legacy-docker/skills/core/meta-ads-ops/references/destination-compliance-verticales.md)
- **meta-capi-tracking**: diagnosticar pixels y datasets de Meta en Events Manager y deduplicar el pixel con la Conversions API en pipelines de leads — ver [references/meta-capi-tracking.md](file:///root/hermes-agent-legacy-docker/skills/core/meta-ads-ops/references/meta-capi-tracking.md)
- **composio-multi-execute**: transporte real de ejecución de tools de acción Meta Ads vía Composio JSON-RPC (MULTI_EXECUTE, no llamada directa), routing multi-cuenta y gotchas — ver [references/composio-multi-execute.md](file:///root/hermes-agent-legacy-docker/skills/core/meta-ads-ops/references/composio-multi-execute.md)
