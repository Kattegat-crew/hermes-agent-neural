---
name: unify-service-logins
description: "Use when unifying Docker app logins to one admin."
tags: [sql, postgres, bcrypt, admin, logins, docker]
license: Apache-2.0
metadata:
  author: "neuralcrew"
  version: "1.0"
---

# Unify Service Logins

## Activation Contract

Use when a Dockerized service must end up with a single admin user (create/update/delete users, change owner, reset passwords) and the UI/API path is unreliable or unavailable. Covers Coolify, ActivePieces, Twenty, Formbricks.

## Hard Rules

- Inspect the real schema (`\d users`, `\d "user"`, `\d user_identity`) BEFORE writing any SQL — column names, PK types, and NOT NULLs differ per app.
- `crypt()`/`gen_salt()` need `CREATE EXTENSION IF NOT EXISTS pgcrypto` first.
- Check FKs before deleting users: if `ON DELETE` is not CASCADE on critical refs (`platform.ownerId`, `project.ownerId`), **reconvert the identity row instead of DELETE+INSERT**.
- Passwords travel only via stdin heredoc into psql — never argv, files, or commits. Clear `.bash_history` afterwards.
- Use bcrypt cost 12: `crypt('<pw>', gen_salt('bf', 12))`; run inside psql so the hash never appears in shell output.

## Decision Gates

| App | Schema reality | Login verification |
|-----|----------------|--------------------|
| Coolify | `users.id` bigint serial, UNIQUE email, nullable password; `team_user` has NO FK to users (safe delete); `user_changelog_reads` CASCADE | No API login in this version (404): POST `/login` with CSRF → 302 → authenticated `/` 200 |
| ActivePieces | `"user"` has NO email — it lives in `user_identity`; `user.id` varchar(21) nanoid; `platform.ownerId`/`project.ownerId` RESTRICT/no CASCADE | `POST /api/v1/authentication/sign-in` → 200 + token |
| Existing user | `SELECT email FROM ...` first; upsert with `ON CONFLICT (email) DO UPDATE` |

## Execution Steps

1. `docker ps` → locate DB containers and service ports; never assume names.
2. Start DB container; `CREATE EXTENSION IF NOT EXISTS pgcrypto;` then inspect schema and list current users.
3. Hash new password (cost 12) inside psql; upsert the target user (owner/admin membership per app: Coolify `team_user` role='owner' on teams 0/1).
4. Remove old users ONLY if FK-safe; otherwise reconvert identity (update email+password) and document the decision.
5. Start full stack; verify REAL login per Decision Gates (API or UI flow); confirm only the target user remains in DB.
6. Clean `.bash_history` and any temp files with tokens/cookies.

## Output Contract

Return: real schemas found, SQL executed (passwords masked), FK decisions and why, login verification method + result, container states, deviations from assumptions.

## References

- `coolify-api-operations` — Coolify API/token flow alternative to DB edits.
- `security-and-hardening` — secret handling rules that apply throughout.
