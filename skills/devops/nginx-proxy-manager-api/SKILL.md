---
name: nginx-proxy-manager-api
description: "Use when configuring Nginx Proxy Manager via API."
tags: [nginx-proxy-manager, npm, letsencrypt, proxy, dns, api]
license: Apache-2.0
metadata:
  author: "neuralcrew"
  version: "1.0"
---

# Nginx Proxy Manager (NPM) API

## Activation Contract

Use when configuring NPM without the UI: first admin bootstrap, proxy hosts, or Let's Encrypt certs with DNS-01 challenge (e.g. behind Cloudflare proxy).

## Hard Rules

- Forward host must be reachable from the NPM container network. `127.0.0.1` fails; use the host IP on the NPM docker network (e.g. `172.19.0.1`).
- Let's Encrypt email comes from the NPM **user account**, not the API payload. Set it before issuing.
- API token: `POST /api/tokens` with `{identity, secret}` → `token` field (JWT).

## Decision Gates

| Need | Action |
|------|--------|
| First admin (no users) | `POST /api/users` (min: `nickname,name,email`), then set password via bcrypt insert into `auth` table (bcryptjs hash, type='password') and restart NPM |
| **Login/contraseña directa a la DB (03/09)** | NPM guarda todo en SQLite `/opt/docker/nginx-proxy-manager/data/database.sqlite` (tabla `auth`). Para rotar/crear credenciales sin UI: generar hash bcrypt con `node -e "console.log(require('bcryptjs').hashSync('<pass>',10))"` dentro del contenedor `nginx-proxy-manager` y `UPDATE auth SET ... WHERE user_id=1`. El hash bcrypt en la DB es la fuente del login form; la API v2 (puerto 81) autentica aparte con `{identity,secret}`→token JWT. Si un login viejo del vault falla (bcrypt False), rotar aquí. |
| Proxy host | `POST /api/nginx/proxy-hosts` with `domain_names`, `forward_host`, `forward_port`, `forward_scheme=http` |
| LE cert DNS-01 | `POST /api/nginx/certificates` with `provider:"letsencrypt"`, `meta.dns_challenge:true`, `meta.dns_provider:"cloudflare"`, `meta.dns_provider_credentials:"dns_cloudflare_api_token=<token>"` |
| Attach cert | `PUT /api/nginx/proxy-hosts/{id}` with `certificate_id` |
| DNS providers list | `GET /api/nginx/certificates/dns-providers` |

## Execution Steps

1. Bootstrap admin if `GET /api/users` returns empty; hash password with bcryptjs (`$2b$10$...`) and insert into `auth` (user_id=1, type='password').
2. Get token via `POST /api/tokens`.
3. Create proxy host (forward_host = host IP on NPM network, not 127.0.0.1).
4. Create certificate: `provider:"letsencrypt"`, meta with `dns_challenge:true`, `dns_provider:"cloudflare"`, credentials string `dns_cloudflare_api_token=<token>`, `propagation_seconds:60`.
5. Poll `GET /api/nginx/certificates` until `expires_on` is set (emission done).
6. Attach cert to proxy host via `PUT` with `certificate_id`.
7. Verify: `curl -s -o /dev/null -w "%{http_code}" https://<domain>/` → 200; check issuer with `openssl s_client`.

## Output Contract

Return: proxy host IDs, certificate IDs, expiry dates, and per-domain HTTPS status.

## References

- `nginx-certbot-reverse-proxy` — certbot/nginx CLI alternative for non-NPM setups.
