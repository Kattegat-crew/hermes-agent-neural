---
name: nextauth-betterauth-url-debug
description: "Use when NextAuth or BetterAuth rejects callback URL"
tags: [nextauth, better-auth, callback-url, reverse-proxy, docker, auth, variables-env]
license: Apache-2.0
metadata:
  author: "neuralcrew"
  version: "1.0"
---

# NextAuth / Better Auth invalid callbackURL debug

## Activation Contract
Use when a self-hosted NextAuth or Better Auth app behind a proxy rejects logins with "Invalid callback URL" / "Invalid callbackURL: http://localhost:PORT" / "This resource does not exist".

## Hard Rules
- The error almost always means the app's configured **base URL is a localhost default**, not the public domain. Never fix by relaxing auth: fix the URL env and recreate the container.
- Read the error's exact URL — it names the wrong base (e.g. `localhost:3000` vs `localhost:3030`) and reveals which env the app fell back to.
- `NEXT_PUBLIC_*` vars are inlined client-side at image build time; the **server** may read a different var (e.g. Formbricks server reads `WEBAPP_URL`, not `NEXT_PUBLIC_WEBAPP_URL`).
- Verify what the running container actually has: `docker inspect <c> --format "{{range .Config.Env}}{{println .}}{{end}}"` — a recreated container may still hold stale values.

## Decision Gates
| App / symptom | Check first |
|---|---|
| Error cites `localhost:3000` | `WEBAPP_URL` / `BETTER_AUTH_URL` unset (server fallback) |
| Error cites `localhost:<app port>` | `NEXTAUTH_URL` / `SERVER_URL` still localhost |
| Formbricks v5 | grep the compiled bundle for the env it reads: `grep -rhoE "env\.\w+|BETTER_AUTH_URL|WEBAPP_URL" <container>/.next/server` |
| Langfuse/Twenty | `NEXTAUTH_URL` (add `NEXTAUTH_URL_INTERNAL=http://localhost:PORT` for server-side calls) |

## Execution Steps
1. `docker logs <app>` and grep `callback|csrf|error|invalid`; note the exact bad URL.
2. `docker inspect <app>` → list env; find localhost values for URL vars.
3. Inspect the compiled server bundle to learn the exact env var read (grep `.next/server` for `BETTER_AUTH_URL|NEXTAUTH_URL|WEBAPP_URL|SERVER_URL`).
4. Set the public URL env(s) in the compose/`.env`; for apps with an internal call path also add `NEXTAUTH_URL_INTERNAL`.
5. Recreate the container; wait for healthy; retry the login flow.
6. Optional SMTP-side check: e-mail links also need the public domain, not SMTP host.

## Output Contract
Return: the wrong base URL found, the env var that caused it, the exact env change applied, container health, and the retested login result.

## References
- `/root/Migracions/estado-20260818-dashboard-subdominios-accesos.md` — worked cases (Twenty, Formbricks, Langfuse)