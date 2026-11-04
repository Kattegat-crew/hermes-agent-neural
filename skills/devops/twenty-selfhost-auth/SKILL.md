---
name: twenty-selfhost-auth
description: "Use when Twenty CRM login fails or adding users."
tags: [twenty, crm, auth, bcrypt, self-hosted, usuarios]
license: Apache-2.0
metadata:
  author: "neuralcrew"
  version: "1.0"
---

# Twenty self-hosted auth & user provisioning

## Activation Contract
Use when users cannot log into a self-hosted Twenty CRM ("registration is disabled", login fails, "Your role in this workspace could not be found") or when creating a new user/role by hand.

## Hard Rules
- Without any auth provider, Twenty shows login but no usable sign-in. Enable password auth with `AUTH_PASSWORD_ENABLED=true` and set `SERVER_URL` to the public domain (never `localhost`).
- A `core.user` without `userWorkspace` + `workspaceMember` **cannot authenticate**, even with a valid password.
- A member without a `roleTarget` row gets "Your role in this workspace could not be found".
- Password hashes are bcrypt (`$2b$10$...`); generate with `python3 -c "import bcrypt; print(bcrypt.hashpw(b'<pass>', bcrypt.gensalt(rounds=10)).decode())"`.
- Never use the shell variable `UID` in scripts (read-only in bash); use e.g. `NUID`.

## Execution Steps
1. Check `.env` keys: `grep -oE "^[A-Z_]+" .env`; verify container env (`docker inspect <server> --format "{{range .Config.Env}}{{println .}}{{end}}"`).
2. Fix auth: add `AUTH_PASSWORD_ENABLED=true`; `SERVER_URL=https://<your-domain>`; recreate the server container (migrations re-run; allow 4-5 min to become healthy).
3. Inspect schema: `core."user"`, `core."userWorkspace"`, `core."role"`, `core."roleTarget"`, and `<workspace_schema>."workspaceMember"` (schema name = `workspace_<slug>`).
4. Provision a user (all four, in order):
   - `core."user"`: email, `passwordHash`, `isEmailVerified=true`. Check `UQ_USER_EMAIL` first — a failed signup attempt may have left the row already.
   - `core."userWorkspace"`: userId + workspaceId (workspace id from `core.workspace`).
   - `<ws>."workspaceMember"`: userId, userEmail, nameFirstName/LastName, colorScheme.
   - `core."roleTarget"`: workspaceId, roleId (from `core.role` for that workspace), userWorkspaceId, `universalIdentifier` (new uuidgen), `applicationId` (copy from an existing roleTarget row).
5. Verify: `select u.email, r.label from core."roleTarget" rt join core."role" r ...` → user shows the role.

## Output Contract
Return: auth env changes applied, user id, workspace link id, member id, role label, and a confirmation the user can log in.

## References
- `/root/Migracions/estado-20260818-dashboard-subdominios-accesos.md` — worked example (captain user, Admin role)