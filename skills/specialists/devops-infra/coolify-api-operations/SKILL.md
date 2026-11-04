---
name: coolify-api-operations
description: "Use when operating Coolify headlessly via its API."
tags: [coolify, api, deploy, docker, self-hosted, devops, secrets]
license: Apache-2.0
metadata:
  author: "neuralcrew"
  version: "1.0"
---

# Coolify API Operations

## Activation Contract

Use when operating Coolify without the UI: bootstrap an admin account, create an API token, enable the API, register deploy keys, create applications, map ports, or trigger deploys.

## Hard Rules

- Coolify API tokens are NOT standard Sanctum `id|plain` — see Decision Gates.
- Never write the API token or admin password into files tracked by git.
- `ports_mappings` format is `host:container` (e.g. `9001:80`). Reverse order binds host port 80 and fails.
- First-time admin login via HTTP requires a valid CSRF/XSRF flow; editing the DB directly is more reliable.

## Decision Gates

| Need | Action |
|------|--------|
| Enable API | `UPDATE instance_settings SET is_api_enabled=true, allowed_ips='0.0.0.0' WHERE id=0;` then `php artisan cache:clear` |
| API token format | `plain = Str::random(40) . hash('crc32b', Str::random(40))`; store `hash('sha256', plain)`; send `plain` as Bearer (no `id\|` prefix). Note: `tokenable_type` in DB must be `'App\Models\User'` and `team_id` must not be null (use 0 for Root Team). |
| Admin in DB | `INSERT INTO users (name,email,password,...) VALUES (...)` with `password_hash($pw, PASSWORD_BCRYPT)`; then insert team_user (team_id=0, role='owner') |
| Private repo app | `POST /api/v1/applications/private-deploy-key` with `private_key_uuid`, `git_repository`, `build_pack=dockerfile`, `ports_exposes=80`, `instant_deploy=false` |
| GitHub Webhook | URL: `https://<coolify_fqdn>/webhooks/source/github/events/manual` (Content-Type: `application/json`). Secret: `$app->manual_webhook_secret_github` (decrypted automatically by Eloquent cast). |
| Reverse Proxy / SSO Bypass | When Coolify sits behind an SSO auth guard (e.g. NPM `forward_auth_guard.conf`), `/webhooks/` and `/api/` locations MUST bypass the auth guard (`include conf.d/include/proxy.conf;`) so GitHub webhooks are not rejected with HTTP 302. |

## Execution Steps

1. Resolve server UUID via `GET /api/v1/servers` (not `0`).
2. Create project: `POST /api/v1/projects` → note `project_uuid` + `environment_uuid`.
3. Register GitHub deploy keys: one SSH key per repo (GitHub rejects reuse across repos).
4. Create app with `POST /api/v1/applications/private-deploy-key`; then `PATCH /api/v1/applications/{uuid}` with `ports_mappings:"9001:80"`.
5. Deploy: `POST /api/v1/deploy?uuid=<app_uuid>`; poll `GET /api/v1/applications/{uuid}` for status.
6. Debug builds: read `logs` from `application_deployment_queues` in the coolify DB; a Next.js `npm ci` fails if the Dockerfile copies only `package.json` (fix to `package*.json`) or if `public/` is absent.

## Output Contract

Return: server/project/environment UUIDs, app UUIDs and mapped ports, deploy status, and any repo fixes applied (with commit messages).

## References

- `coolify-secure-secrets` — UI-based deploy + Laravel encryption, complement to this headless flow.
