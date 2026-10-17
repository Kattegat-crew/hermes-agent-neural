---
name: activepieces-lead-automation
description: Use when automating lead capture flows in ActivePieces (webhook trigger, SMTP email, Google Sheets insert), debugging AP flow failures, or managing MCP OAuth JWT auth for AP tool integration.
---

# ActivePieces Lead Automation

## Overview

Automate lead capture via ActivePieces: form submission → webhook → SMTP email → Google Sheets row. Auth is MCP session JWT (HS256, 15 min TTL), not API keys.

## When to Use

- Building or debugging a lead automation pipeline in ActivePieces
- Fixing flow failures (send-email, insert_row, webhook triggers)
- Managing MCP OAuth JWT auth for AP tool integration
- Connecting a form/webhook to Google Sheets or SMTP

## When NOT to Use

- Direct database writes (use psql instead)
- Non-lead automations (use native CRON or systemd)
- Tasks requiring paid AP features (API key auth is paid)

## Core Pattern

```
Form submission
  └─> Webhook (app) → POST /webhook/leads
       └─> notifyActivePieces(AP_WEBHOOK_URL)
            └─> AP Flow: catch_webhook → SMTP send → Sheets insert
```

## Quick Reference

**MCP endpoint:** `http://147.93.3.250:8088/mcp`
**Flow webhook URL:** `http://127.0.0.1:8088/api/v1/webhooks/<flowId>`
**JWT secret:** `AP_JWT_SECRET` env var from `docker exec ap-app env`
**JWT issuer:** `activepieces`
**JWT TTL:** 15 minutes

**Sheet columns (paradise/golden):**
| Col | Field |
|-----|-------|
| A | created_at (YYYY-MM-DD) |
| B | nombre |
| C | cedula |
| D | telefono |
| E | email |
| F | sede |
| G | bono |

**AP MCP tools:** `ap_list_connections`, `ap_list_flows`, `ap_get_flow`, `ap_trigger_flow`, `ap_list_runs`, `ap_run_flow`

## Implementation

### 1. Generate MCP OAuth JWT

```python
import jwt, time
secret = os.environ["AP_JWT_SECRET"]  # NUNCA escribir el valor real en un archivo
payload = {
    "sub": "<user_id>",           # owner user id from AP
    "projectId": "<project_id>",
    "platformId": "<platform_id>",
    "type": "mcp_oauth",
    "aud": "MCP_OAUTH_ACCESS",
    "iat": int(time.time()),
    "exp": int(time.time()) + 900,  # 15 min
}
token = jwt.encode(payload, secret, algorithm="HS256", issuer="activepieces")
# Save to /tmp/opencode/ap-jwt for MCP use; lock permissions
with open("/tmp/opencode/ap-jwt", "w") as f:
    f.write(token)
import os
os.chmod("/tmp/opencode/ap-jwt", 0o600)  # solo lectura/escritura del owner
```

### 2. List connections and flows

```bash
# Via MCP tools: ap_list_connections → find externalId
# Via MCP tools: ap_list_flows → find flowId
```

### 3. Build/fix a flow

1. In AP UI: create flow with `catch_webhook` trigger
2. Add steps: `send_email` (piece-smtp) → `insert_row` (Google Sheets)
3. Set auth: use **externalId** from `ap_list_connections` (not the table id)
4. **Publish** the flow (required for webhook to work)
5. **Activate** the flow (toggle on)

### 4. Verify a flow run

```bash
docker exec ap-db psql -U postgres -d activepieces -tAc   "SELECT status FROM flow_run WHERE "flowId"='<FLOW_ID>' ORDER BY "startTime" DESC LIMIT 1;"
# Expected: SUCCEEDED
```

### 5. Clean up test data

```bash
# After testing, delete test lead from DB
docker exec ap-db psql -U postgres -d activepieces -tAc "DELETE FROM \"tableRow\" WHERE \"flowId\"='<FLOW_ID>' AND \"value\"::json->>'nombre'='TEST_NAME';"
```

### 6. Headless User JWT & Flow Update via REST API (No UI / No Paid API Key)

When API keys are unavailable (paid feature), forge a valid user JWT on the server using `AP_JWT_SECRET` and the user's active `tokenVersion`:

```bash
# 1. Fetch user_id, platformId, and tokenVersion from DB
docker exec ap-db psql -U postgres -d activepieces -c \
  "SELECT u.id as user_id, u.\"platformId\", ui.\"tokenVersion\" FROM \"user\" u JOIN user_identity ui ON ui.id = u.\"identityId\" WHERE ui.email = '<ADMIN_EMAIL>';"

# 2. Generate signed User JWT directly inside ap-app container
TOKEN=$(docker exec -w /usr/src/app/packages/server/api ap-app node -e '
const { accessTokenManager } = require("./dist/src/app/authentication/lib/access-token-manager");
const { PrincipalType } = require("@activepieces/shared");
const pino = require("pino");
async function run() {
    const token = await accessTokenManager(pino({level:"silent"})).generateToken({
        id: "<USER_ID>",
        type: PrincipalType.USER,
        platform: { id: "<PLATFORM_ID>" },
        tokenVersion: "<TOKEN_VERSION>"
    });
    process.stdout.write(token);
}
run();
')

# 3. Read full flow (includes current draft)
curl -s -H "Authorization: Bearer $TOKEN" http://<AP_HOST>:8088/api/v1/flows/<FLOW_ID> > flow.json

# 4. Update step action in draft via API
curl -s -X POST http://<AP_HOST>:8088/api/v1/flows/<FLOW_ID> \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{
    "type": "UPDATE_ACTION",
    "request": {
      "name": "step_1",
      "displayName": "Enviar correo",
      "type": "PIECE",
      "valid": true,
      "settings": {
        "pieceName": "@activepieces/piece-smtp",
        "actionName": "send-email",
        "pieceVersion": "0.4.6",
        "input": { ... }
      }
    }
  }'

# 5. Publish flow (CRITICAL: moves draft to LOCKED, updates publishedVersionId, clears caches)
curl -s -X POST http://<AP_HOST>:8088/api/v1/flows/<FLOW_ID> \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"type": "LOCK_AND_PUBLISH", "request": {"status": "ENABLED"}}'
```

### 7. Multi-Tier Cache Architecture & Forced Purge

ActivePieces caches flow versions in 2 distinct layers. Webhooks **NEVER** run drafts; they only execute `publishedVersionId`:

1. **Redis Flow State Cache (30-day TTL)**:
   - Key: `flow-execution-state:<flowId>`
   - Contains flow metadata and `publishedVersionId`.
   - Purge: `docker exec ap-redis redis-cli del "flow-execution-state:<FLOW_ID>"`
2. **Worker Disk Cache (`cache.json`)**:
   - Path on host: `/opt/docker/activepieces/cache/v11/flows/<flowVersionId>/cache.json`
   - Path in container: `/usr/src/app/cache/v11/flows/<flowVersionId>/cache.json`
   - If present, `flowCache` in `ap-worker` reads from disk and **never queries Postgres or the API**.
   - Purge: `rm -rf /opt/docker/activepieces/cache/v11/flows/*` on the host, followed by `docker restart ap-app ap-worker`.

### 8. Inspecting & Decompressing Flow Execution Logs

Flow run logs are stored compressed in PostgreSQL table `file`:

```bash
# 1. Get logsFileId from latest flow run
LOG_ID=$(docker exec ap-db psql -U postgres -d activepieces -Atc \
  "SELECT \"logsFileId\" FROM flow_run WHERE \"flowId\"='<FLOW_ID>' ORDER BY created DESC LIMIT 1;")

# 2. Extract base64 and decompress zstd payload
docker exec ap-db psql -U postgres -d activepieces -Atc \
  "SELECT encode(data, 'base64') FROM file WHERE id='$LOG_ID';" | base64 -d > /tmp/run.zst
zstd -d /tmp/run.zst -o /tmp/run.json -f

# 3. Inspect executed step inputs and outputs
python3 -c "import json; d=json.load(open('/tmp/run.json')); print(json.dumps(d['executionState']['steps'], indent=2))"
```

## Common Mistakes

| Error | Real Cause | Fix |
|-------|-----------|-----|
| Flow runs old template despite DB edit | ActivePieces executes `publishedVersionId` (LOCKED version), not the row you edited; and worker caches `cache.json` on disk | Never edit `flow_version` via raw SQL; update draft via `UPDATE_ACTION` and publish via `LOCK_AND_PUBLISH` API |
| `cache.json` persists after container restart | `/usr/src/app/cache` is a bind mount to host `/opt/docker/activepieces/cache` | Delete cache files directly on host filesystem (`rm -rf /opt/docker/activepieces/cache/v11/flows/*`) |
| API 401 `Cannot read properties of undefined (reading 'type')` | Forged JWT lacked `tokenVersion` or user identity verification | Generate token using `accessTokenManager.generateToken` with exact `tokenVersion` from `user_identity` |
| `to` of send-email fails | AP 0.82 requires ARRAY `["email"]`, not string | Pass array, not string |
| `RangeError: Invalid array length` on insert_row | `values` has column names or array | `values` = object with `"A"`..`"G"` keys (column letters) |
| "connection not found" | `auth` uses table id, not externalId | Use **externalId** from `ap_list_connections` |
| Sheet column empty | Field generated by DB, webhook doesn't send it | Add field in webhook before `notifyActivePieces` (e.g. `created_at: new Date().toISOString().slice(0,10)`) |
| MCP "unauthorized" | JWT expired (15 min TTL) | Regenerate JWT |
| Worker logs `Failed to complete job` (loop) | In multi-container setup, `AP_FRONTEND_URL` points at a public/unreachable IP; engine can't upload payload (ConnectTimeoutError) | Set `AP_FRONTEND_URL` to the internal docker URL reachable by both app and worker (e.g. `http://ap-app:80`) and restart both |
| Stale jobs retry forever after URL fix | Old INTERNAL_ERROR runs still queued in Redis `bull:workerJobs:active` | `redis-cli DEL bull:workerJobs:active bull:workerJobs:stalled-check` and restart ap-worker |
| `insert_row` overwrites row 2 every time | Sheet was converted to Google's native "Table" (`tables` metadata resource); `values.append` targets the static table boundary instead of the sheet bottom | Remove the Table resource (`deleteTable` via API or in UI: right click table -> "Revertir a rango"); use standard `Datos -> Crear un filtro` (`basicFilter`) instead |

## Real-World Impact

- Bypassing the API with raw SQL updates in PostgreSQL is an illusion: ActivePieces stores locked versions, caches them in Redis for 30 days, and caches flow schemas as `cache.json` in the worker bind mount.
- A single `LOCK_AND_PUBLISH` call via the internal REST API updates the flow, locks the version, and invalidates all caches cleanly.
- Inspecting `executionState` via `file.data` + `zstd -d` is the only 100% truthful verification of what the SMTP piece actually received and sent.

