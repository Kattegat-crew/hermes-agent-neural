---
name: web-serving-diagnosis
description: >-
  Use when a VPS web page stops loading. Diagnose VPS web page access issues. author: ragnar version: "1.0.0" license: MIT hermes: tags: [web, nginx, ssl, https, http, vps, diagnosis] related_skills: [vps-ops, nginx-certbot-reverse-proxy, reel-gallery-deploy]
tags: [web, nginx, https, vps, diagnostico, ssl]
category: devops
metadata: {}
---

# Web Serving Diagnosis — VPS

## When to Use
User reports a web page that was previously working is now inaccessible or loading incorrectly. Triggers: "no carga", "no me deja acceder", "can't access", "pantalla blanca", "no funciona la página", "versión vieja no funciona".

## Quick Diagnosis Flow

### Step 1 — Verify the page exists on the server
```bash
for u in "http://<IP>/<path>/"; do
  code=$(curl -s -o /dev/null -w "%{http_code}" -m 15 "$u")
  echo "$code  $u"
done
```
- 200 → page is served. Problem is client-side (HTTPS, DNS, browser cache).
- 404 → page doesn't exist or was moved.
- 000 → server unreachable or connection refused.

### Step 2 — Check for redirects
```bash
curl -s -m 15 -L -o /dev/null \
  -w "Final: %{url_effective}\nRedirects: %{num_redirects}\nHTTP: %{http_code}\n" \
  "http://<IP>/<path>/"
```

### Step 3 — HTTPS vs HTTP (MOST COMMON CAUSE)
```bash
curl -sk -o /dev/null -w "%{http_code}\n" -m 10 "https://<IP>/<path>/"
```
If HTTPS returns `000` and HTTP returns `200` → **no SSL cert on bare IP**. Tell user: use `http://` (without the `s`).

### Step 4 — Check nginx for rewrite/redirect rules
```bash
nginx -T 2>/dev/null | grep -A3 -B3 -E "<path-keyword>"
```

### Step 5 — Check HTML for JS/meta redirects
```bash
curl -s -m 15 "http://<IP>/<path>/" | grep -iE "meta.*refresh|location|redirect|window\.location"
curl -s -m 15 "http://<IP>/<path>/" | sed -n '/<script/,/<\/script>/p'
```

## Common Root Causes

| Symptom | Likely cause |
|---------|-------------|
| HTTP 200 but user sees blank/error | User accessing via HTTPS on bare IP (no cert) |
| HTTP 301/302 loop | nginx redirect rule or Cloudflare SSL setting |
| Page loads but images/videos broken | Relative paths break when accessed via different URL |
| Intermittent timeout | ISP blocking port 80, or server firewall |
| 403 Forbidden | Missing index.html in directory (nginx autoindex off) |

## Pitfalls

- `curl` from inside the Docker container resolves `/etc/hosts` to `127.0.0.1` — always use the external IP or a Python `urllib` request for verification.
- HTTPS on a bare IP without a cert returns `000` (connection refused), not `403` or `502`. This confuses users who think the page is "blocked" when it's just HTTPS with no cert.
- The VPS (147.93.3.250) has SSL only for domain names with Let's Encrypt certs (e.g. `reels.neuralcrewlabs.com`), not for the bare IP.
- When user says "old version doesn't work" but the URL returns 200 → it's almost always HTTPS vs HTTP. Check this first.
