---
name: formbricks-v5-selfhost
description: "Use when deploying or fixing a self-hosted Formbricks v5."
tags: [formbricks, self-hosted, docker, postgres, encuestas, deploy, cuid2, migracion]
license: Apache-2.0
metadata:
  author: "neuralcrew"
  version: "1.0"
---

# Formbricks v5 self-hosted stack

## Activation Contract
Use when deploying, resetting, or debugging a self-hosted Formbricks (v5+): the app errors with "Error al cargar recursos", logs show `Invalid cuid2`, or the stack is missing Hub/Cube.

## Hard Rules
- **Never generate entity IDs manually** (`uuidgen` produces UUIDs with dashes). Formbricks v5 validates IDs as cuid2 (`/^[0-9a-z]+$/`); only the app/wizard creates valid IDs.
- v5 **requires** the full stack: `formbricks` + `formbricks-migrate` + `hub` + `hub-migrate` (goose+river) + `cube` (cubejs/cube). Missing Hub/Cube = core features fail.
- The **server** reads `WEBAPP_URL` (not `NEXT_PUBLIC_WEBAPP_URL`); if unset it falls back to `http://localhost:3000` → "Invalid callbackURL" on auth.
- Migration `20241017124431` creates the pgvector extension → the DB user needs `SUPERUSER` (or pre-create the extension).
- `EMAIL_VERIFICATION_DISABLED` / `PASSWORD_RESET_DISABLED` must be `"0"` to enable outgoing mail.

## Decision Gates
| Situation | Action |
|---|---|
| Fresh install or broken DB with 0 data | Drop+recreate DB, deploy official stack, recreate admin via wizard |
| Existing data with invalid UUID IDs | In-place migration (UUID→cuid2) or export/import; prefer wizard recreation |
| "Invalid callbackURL: localhost" | Set `WEBAPP_URL` (+ `NEXTAUTH_URL`) to the public domain, recreate |
| "permission denied to create extension vector" | `ALTER ROLE <dbuser> SUPERUSER`, rerun migrate |

## Execution Steps
1. Confirm version/errors: `docker inspect <app> --format {{.Config.Image}}`; `docker logs <app> | grep -i cuid2`.
2. Get official env/compose from `formbricks/stable` repo (docker-compose.yml, docker/cube/cube.js + schema/).
3. Adapt compose to your infra: DATABASE_URL/REDIS_URL to existing services; remove `depends_on` for external services; add cube healthcheck; shared `environment: &env` anchor.
4. Drop+recreate DB (`DROP DATABASE ... WITH (FORCE)`; `CREATE DATABASE ... OWNER <user>`); grant SUPERUSER to the app DB user.
5. `docker compose up -d`; verify migrate completes, hub/cube healthy, `0` cuid2 errors, HTTP 200, `/auth/login` renders.
6. SMTP (optional): `SMTP_HOST/PORT/USER/PASSWORD`, `SMTP_AUTHENTICATED=1`, `SMTP_SECURE_ENABLED=1` (465). Test with Python smtplib from the host; the container has no bash/openssl.
7. Create admin via the setup wizard (never via INSERT with generated IDs).

## Output Contract
Return: services up (names+status), migrate result, error-count in logs, HTTP status, and the login URL the admin must complete the wizard on.

## References
- `/root/Migracions/estado-20260818-dashboard-subdominios-accesos.md` — worked example, env values, pitfalls