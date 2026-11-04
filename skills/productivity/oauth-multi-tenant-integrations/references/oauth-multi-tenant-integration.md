<!-- Absorbido por F6 lote 0 el 2026-09-23 desde `productivity/oauth-multi-tenant-integration`.
     Contenido íntegro de la skill absorbida; el original queda en
     `data/archive/F6_lote0_20260923-150318/absorbidas/`. -->

---
name: oauth-multi-tenant-integration
description: Designing multi-tenant OAuth connections.
trigger: "When designing or debugging multi-tenant OAuth connections via ActivePieces."
---

# OAuth & Multi-Tenant Integration (ActivePieces + Hermes)

Use this skill when designing or troubleshooting multi-tenant OAuth connections between Hermes agents and ActivePieces (AP).

## The "Hybrid" Architecture (Opción C)
To scale without exploding costs or management complexity, use a hybrid approach:

1. **ActivePieces (Auth Hub):** Handles all heavy OAuth (Google, Meta, Canva, Amazon, etc.). AP manages the refresh tokens, multi-tenant connections, and the UI for the "Client Consent" flow.
2. **Hermes MCP (API/Direct):** Handles simple API-key based connections (Engram, ElevenLabs, fal.ai, Twenty CRM) via direct MCP servers.
3. **The "Gate" (ap_call wrapper):** A specialized wrapper that ensures an agent can only invoke a connection if they own it in the `connections-map`.

## Connection Governance (The 5 Layers of Security)
1. **SOUL (Contract):** The agent's identity/SOUL defines which connections they are allowed to use (e.g., "I only use `helmer-*` connections").
2. **Engram Map (Logical):** A `connections-map` in Engram tracks `tenant -> connection_name -> service`.
3. **ActivePieces Projects (Scale):** When moving from <5 to >5 clients, transition from a single AP project to dedicated AP Projects for hard isolation.
4. **Vigía (Auditor):** Continuous health checks and auditing of which agent is calling which connection.
5. **ap_call (The Law):** A technical wrapper/script that validates the caller's identity against the Engram map *before* executing the AP request.

## Implementing the "Client Consent" Flow (The White Button)
Instead of sending clients to the AP dashboard, use a custom "Connect" page:
- **Backend:** Generates a JWT signed with the `AP_JWT_SECRET` and an `authRequestId`.
- **Frontend:** Uses the AP Embed SDK (`activepieces.connect()`) to trigger the OAuth flow within an iframe/overlay.
- **Result:** The connection is automatically created inside AP with the correct `externalId` (e.g., `tenant-gmail`) and is immediately usable by agents.

## Troubleshooting `INVALID_CLOUD_CLAIM`
If AP returns this error, it means the agent is trying to use a connection they don't own, OR the OAuth request is being made with the wrong Client Identity.
- **Cause:** Using `CLOUD_OAUTH2` (which tells AP to use AP's own app identity) instead of `OAUTH2` (which uses the specific Client ID/Secret provided in the request).
- **Fix:** Ensure the backend uses `type: OAUTH2` and passes the `client_id` and `client_secret` of the specific Client.

## Naming Convention
Always use `{tenant}-{service}` (e.g., `golden-gmail`, `jonathan-drive`) to ensure clear ownership in the Engram map and AP UI.
