# Outline Wiki API — Cloudflare UA Pitfall

## Problem

Outline wiki (wiki.neuralcrewlabs.com) sits behind Cloudflare. Python's default `User-Agent` header is blocked with **HTTP 403, error code 1010** (Cloudflare's "owner banned your access based on browser signature").

This affects ALL API calls from scripts: `documents.info`, `documents.update`, `documents.search`, `documents.list`, etc.

## The Fix

Every HTTP request to the Outline API MUST include a browser-like User-Agent:

```python
req.add_header('User-Agent', 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36')
```

Or with `curl`:
```bash
curl -H 'User-Agent: Mozilla/5.0 (X11; Linux x86_64) Chrome/126.0' ...
```

## Why This Happens

Cloudflare's bot detection (WAF) fingerprints the `User-Agent` string. Python's `urllib` sends `Python-urllib/3.13` which is flagged as a bot. Browser UAs pass the check.

Note: `curl` without a UA also gets blocked (sends `curl/8.x`).

## Required Headers (Complete)

```python
req = urllib.request.Request(url, data=body, method='POST')
req.add_header('Authorization', 'Bearer ' + api_key)
req.add_header('Content-Type', 'application/json')
req.add_header('User-Agent', 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36')
```

The `Host` and `X-Forwarded-Proto` headers are also required (documented in outline-wiki-ops skill) but the UA is the one that gets silently blocked.

## Symptoms

- HTTP 403 with body `{"error": "error", "statusCode": 1010}`
- No other error detail — just error 1010
- Only affects requests from the Hermes container or scripts; browser-based access (through NPM proxy) works fine because browsers send real UAs

## Verified Context

- Outline version: 1.9.2 (prod)
- URL: wiki.neuralcrewlabs.com
- Discovered during batch ingest of 102+ tuits into wiki tables (Sep 2026)
- `outline-wiki-ops` skill does NOT document this pitfall (the skill's header section mentions `Host` + `X-Forwarded-Proto` but not the UA requirement)

## Related

- `outline-wiki-ops` skill — general Outline API operations
- `outline-ua-pitfall` — this file
- Cloudflare error 1010 documentation: https://developers.cloudflare.com/support/troubleshooting/cloudflare-errors/troubleshooting-1010-errors/