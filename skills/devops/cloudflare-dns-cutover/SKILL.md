---
name: cloudflare-dns-cutover
description: "Use when pointing Cloudflare DNS at a new origin server."
tags: [cloudflare, dns, cutover, a-record, ssl, ttl, origen, migracion]
license: Apache-2.0
metadata:
  author: "neuralcrew"
  version: "1.0"
---

# Cloudflare DNS Cutover

## Activation Contract

Use when migrating domains to a new origin server behind Cloudflare: switch A records, set TTL, enable SSL, and verify public HTTPS.

## Hard Rules

- Bearer token with prefix `cfat_` is valid for zone operations even though `GET /user/tokens/verify` returns "Invalid API Token" — do not trust verify, test a real call.
- Token must hold `Zone:DNS:Edit` permission; missing it yields error `10000 Authentication error` on `/dns_records` while `/zones` still works.
- A 32-hex string the user pastes is usually the **Account ID**, not a token.
- With proxy active, `dig A` returns Cloudflare IPs (104.x/172.x); the origin is hidden.

## Decision Gates

| Need | Action |
|------|--------|
| List zones | `GET /zones?per_page=50` → zone IDs |
| List records | `GET /zones/{zid}/dns_records?per_page=100` |
| Change A record | `PATCH /zones/{zid}/dns_records/{rid}` `{content, proxied:true, ttl:300}` |
| Create missing A | `POST /zones/{zid}/dns_records` `{type:"A", name, content, proxied:true, ttl:300}` |
| SSL mode | `PATCH /zones/{zid}/settings/ssl` `{value:"full"}` (flexible breaks origin cert checks) |

## Execution Steps

1. Verify token: `GET /zones` must return zones (not error 10000).
2. For each zone, list records and identify `A` records for apex + `www`.
3. `PATCH` apex/www A records to the new origin; `POST` any that don't exist (e.g. new domains).
4. Set `ttl:300` (5 min) on all changed records for fast rollback.
5. Set SSL mode `full` on each zone.
6. Verify: `curl https://<domain>/` → 200; `openssl s_client` shows subject CN = domain.

## Output Contract

Return: per-zone list of changed/created records (type, name, content, ttl), SSL mode, and HTTPS verification per domain.

## References

- `nginx-proxy-manager-api` — issue origin Let's Encrypt certs (DNS-01) that pair with SSL mode full.
