---
name: cloudflare-access-api
description: "Use when protecting a subdomain with Cloudflare Access."
tags: [cloudflare, zero-trust, access, subdominio, bypass, otp, seguridad, api]
license: Apache-2.0
metadata:
  author: "neuralcrew"
  version: "1.1"
---

# Cloudflare Access setup via API

## Activation Contract
Use when protecting web subdomains/apps with Cloudflare Access (Zero Trust): creating the org, adding an email OTP identity provider, creating applications and policies, renaming the team, OR making a specific path/route of a protected app public (bypass).

## Hard Rules
- **Access must be enabled from the dashboard first** (`dash.cloudflare.com → Zero Trust → Set up`). There is no API to enable it; API calls return `access.api.error.not_enabled` until then.
- The API **ignores `additional_domains`** silently — create **one self-hosted app per domain**, each with its own policy.
- **`domain` is a SINGLE string, NOT an array.** For self_hosted apps, an array fails with `12130 access.api.error.invalid_request`; `self_hosted_domains` with >1 entry fails with `too many destinations for one app`. → **1 app per path** for multi-path bypass.
- Rename the team only via `PUT /access/organizations` sending BOTH `name` and `auth_domain` (e.g. `neuralcrew` + `neuralcrew.cloudflareaccess.com`); `name` alone returns `invalid_auth_domain`.
- Policy email include rules are `{"email":{"email":"user@example.com"}}` (string per rule, one rule per email) — an array inside `email` is rejected.
- **Bypass does NOT support identity selectors** — the only include is `[{"everyone":{}}]`.
- `POST /user/tokens/verify` may return "Invalid API Token" even when the token works for DNS/Access — verify with a real call instead.
- Path-based rules take precedence over the hostname root rule (app-paths). An app for `host/s/*` opens only `/s/*` while `host/` stays protected by the root app.

## Execution Steps
1. Verify token + state: `GET /accounts/{acct}/access/organizations` and `GET .../access/apps?per_page=1`.
2. Rename team (optional): `PUT /accounts/{acct}/access/organizations` `{name, auth_domain}`.
3. Add One-time PIN IdP: `POST .../access/identity_providers` `{type:"onetimepin", name:"Email OTP", config:{}}`.
4. For each hostname (allow): `POST .../access/apps` `{type:"self_hosted", name, domain, session_duration:"24h", app_launcher_visible:false}`; then `POST .../access/apps/{id}/policies` `{name, decision:"allow", include:[{email:{email}},...], precedence:1}`.
5. **Bypass a path (make it public)**: for EACH path, one app `{type:"self_hosted", name:"<app> - <path>", domain:"host/path/*", app_launcher_visible:false, session_duration:"24h"}`; then `POST .../access/apps/{id}/policies` `{name, decision:"bypass", precedence:1, include:[{"everyone":{}}]}`.
6. Verify per domain/path: unauthenticated HTTPS request returns `302` to `<team>.cloudflareaccess.com/cdn-cgi/access/login/<domain>` for protected routes; bypassed paths return the origin response (200/404/etc), never a CF redirect.

## Output Contract
Return: team auth domain, IdP id, and a table of domain/path → app id → policy id (allow and bypass separately), plus per-route redirect verification.

## References
- `/root/.config/opencode/skills/cloudflare-dns-cutover/SKILL.md` — DNS record setup that Access domains sit on top of
- `/root/.config/opencode/skills/docuseal-selfhost-ops/SKILL.md` — full public-signing route set for DocuSeal (example of a path-bypass use case)