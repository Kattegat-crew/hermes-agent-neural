---
name: oauth-multi-tenant-integrations
description: "Use when wiring multi-tenant OAuth connections per client."
tags: [oauth, multi-tenant, activepieces, jwt, conexiones, refresh-token]
---

# OAuth & Multi-Tenant Integrations

Use when designing or troubleshooting integrations that require managing multiple user accounts (multi-tenant) via OAuth (Google, Meta, Canva, etc.) on a self-hosted platform like ActivePieces or custom agent profiles.

## The Multi-Tenant Problem
When agents need access to different accounts (e.g., Agent A needs Client A's Gmail, Agent B needs Client B's Gmail), a single global connection is insufficient and insecure.

## Recommended Architecture: The Hybrid Model (Option C)

1. **OAuth Hub (ActivePieces):**
   - Use ActivePieces as the central authority for all OAuth-heavy services (Google, Meta, Canva, Amazon, etc.).
   - AP manages the `refresh_token` lifecycle and handles the complex OAuth handshake.
   - **Naming Convention:** Always use `{tenant}-{service}` (e.g., `helmer-gmail`, `golden-meta-ads`) to ensure clear ownership.

2. **Direct MCP/API (API Keys):**
   - Use direct MCP servers or API wrappers for services that use static API keys or don't require complex OAuth (e.g., Engram, ElevenLabs, Twenty CRM, WhatsApp Gateway).

3. **Identity & Enforcement (The 5 Layers):**
   - **Layer 1: SOUL.md** — The agent's identity defines its allowed connection prefixes (e.g., "I only use `helmer-*` connections").
   - **Layer 2: Engram Map** — A central `connections-map.json` (synced to Engram) that maps `tenant -> connection_name`.
   - **Layer 3: Project Isolation** — (Advanced) Use AP's "Projects" feature to physically isolate tenants (requires Premium).
   - **Layer 4: Vigía Audit** — Automated health checks that monitor for cross-tenant connection usage.
   - **Layer 5: The Law (`ap_call` wrapper)** — A mandatory technical wrapper that validates the agent's identity against the connection map before firing the request to AP.

## Troubleshooting OAuth Flows

### Common Failure: "Missing authRequestId or code"
Usually caused by:
- **Missing JWT:** The frontend/SDK is calling the backend without a valid signed JWT (required for AP MCP authorization).
- **Incorrect Redirect URI:** The OAuth provider is redirecting to a URL not registered in the provider's console (e.g., `localhost` vs `production-ip`).
- **SDK Configuration:** The client-side SDK (e.g., ActivePieces JS) hasn't been initialized with the correct `instanceUrl`.

### Debugging Steps
1. **Verify JWT:** Ensure the backend generates a valid HS256 JWT with `iss: activepieces`, `aud: MCP_OAUTH_ACCESS`, and the correct `projectId`.
2. **Check Redirects:** Ensure the `redirect_uri` matches exactly what is configured in the Google/Meta Cloud Console.
3. **Browser Test:** If the UI "hangs," try opening the authorization URL in a new tab to see if the browser/popup is being blocked.

## Best Practices
- **One-Click Onboarding:** For clients, use an embedded OAuth button (Iframe/SDK) so they never see the internal dashboard.
- **Minimal Scopes:** Only request the necessary scopes (e.g., `gmail.modify` + `calendar.events` + `drive.file`) in a single consent screen to reduce friction.
- **Silent Refresh:** Rely on AP's ability to handle refresh tokens to keep connections "evergreen" without user intervention.

## Referencias absorbidas

- `references/oauth-multi-tenant-integration.md` — absorbida desde `productivity/oauth-multi-tenant-integration` el 2026-09-23 (F6 lote 0, R15: condensar sin borrar).
