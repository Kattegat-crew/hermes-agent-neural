# Vaultwarden: is registration really open? (verification recipe)

Scanner claim "User Registration Enabled" is unreliable. Verify with this
sequence before touching anything. Validated 2026-08-27 against
vault.neuralcrewlabs.com (false positive confirmed).

## Step 1 — env truth (not /api/config)

```bash
docker exec vaultwarden env | grep -iE 'SIGNUPS|INVITATIONS|ADMIN'
# redact ADMIN_TOKEN in any output: sed 's/=.*/=[REDACTED]/'
```

Do NOT trust `/api/config`'s `disableUserRegistration` field: Vaultwarden
reports the hardcoded default (`false`) there even when `SIGNUPS_ALLOWED=false`.
This single field is what fools scanners.

## Step 2 — real registration attempts (external-style POSTs)

Two probes, probe email pattern `probe-<random>@example.com`:

1. Legacy JSON API route: `POST /api/accounts/register` with
   `{name, email, masterPasswordHash, key, keys}` (Bitwarden account
   model). If the route is not exposed → HTTP 404 "The requested
   resource could not be found." = registration endpoint disabled.
2. Bitwarden Identity signup flow: `POST /identity/...` signup with the
   v2 field layout (master password hash `H` = base64 of sha256 of the
   password, plus base64 key material `K`/`PK`). Expected rejection when
   closed: **"Registration not allowed"**.

Either rejection closes the question: registration is OFF regardless of
what `/api/config` claims.

## Step 3 — confirm the invitation workflow matches the operator's intent

`INVITATIONS_ALLOWED=true` + `SIGNUPS_ALLOWED=false` = no public signup,
but the account owner can invite specific emails from their account —
this is the configuration the operator (Jonathan) wants for the bóveda.

User census (read-only, no secrets):

```bash
docker run --rm -v <host-vault-data>:/d:ro python:3.12-alpine python3 -c "
import sqlite3
c = sqlite3.connect('/d/db.sqlite3')
for r in c.execute('select email, verified_at is not null, datetime(created_at,\"unixepoch\") from users order by created_at'):
    print(r)"
```

(`verified_at` NULL = invited, not yet accepted.) Do not write to the
vault DB; if python+sqlite isn't available inside the target container,
use the ro-bind helper-container pattern from `vps-ops`.
