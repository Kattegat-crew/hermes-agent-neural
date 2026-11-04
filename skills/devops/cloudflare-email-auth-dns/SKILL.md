---
name: cloudflare-email-auth-dns
description: "Use when setting SPF, DMARC or DKIM records in Cloudflare."
tags: [cloudflare, dns, spf, dmarc, dkim, deliverability, correo, mx]
license: Apache-2.0
metadata:
  author: "neuralcrew"
  version: "1.0"
---

# Cloudflare Email Auth DNS

## Activation Contract

Use when a domain needs email deliverability setup: create or verify SPF, DMARC, DKIM, or MX records through Cloudflare, or when mail from a self-hosted app lands in spam.

## Hard Rules

- Bearer token `cfat_` is valid for zone ops even when `GET /user/tokens/verify` returns "Invalid API Token" — never trust verify, test a real call.
- Only ONE SPF record per domain: always `GET` existing TXT records first and never duplicate `v=spf1`.
- Never touch MX/DKIM/A/CNAME/site-verification records during email-auth work.
- TXT records are not proxied; set `ttl:300` for fast rollback.
- Start DMARC at `p=none` (monitor); harden to `quarantine` → `reject` only after 48–72h of rua reports.

## Decision Gates

| Need | Action |
|------|--------|
| Zone ID | `GET /zones?per_page=50` → match `name` (known: neuralcrewlabs.com = e9078af868fccbdccff63eea3e563d65) |
| List records | `GET /zones/{zid}/dns_records?per_page=100` |
| Create TXT | `POST /zones/{zid}/dns_records` `{type:"TXT", name, content, ttl:300}` |
| Google Workspace SPF | `v=spf1 include:_spf.google.com ~all` |
| DMARC | `v=DMARC1; p=none; rua=mailto:postmaster@<domain>` |
| Existing MX? | Verify `dig +short MX <domain>` → Google (`smtp.google.com`) before adding SPF |

## Execution Steps

1. Read token from VPS `credentials-3` (format `dns_cloudflare_api_token=...`); never print it.
2. `GET /zones` → confirm zone + ID; `GET dns_records` → snapshot existing TXT/MX/DKIM.
3. Create SPF TXT at apex and DMARC TXT at `_dmarc.<domain>` (both ttl 300) via `POST`.
4. `GET dns_records` again → confirm no collateral changes (15 records known baseline, MX/DKIM/A intact).
5. Verify propagation: `dig @1.1.1.1 +short TXT <domain>` and against the authoritative NS — the local resolver may serve stale cache.
6. Advise DMARC hardening timeline and where rua reports land.

## Output Contract

Return: zone ID, before/after TXT records, record IDs of created records, HTTP status of POSTs, and the dig verification output (resolver + authoritative).

## References

- `cloudflare-dns-cutover` — A-record cutover and SSL mode on the same zones.
- `gmail-smtp-app-password` — SMTP wiring that consumes these records.
