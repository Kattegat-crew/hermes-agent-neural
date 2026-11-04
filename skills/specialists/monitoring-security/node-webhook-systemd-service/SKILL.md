---
name: node-webhook-systemd-service
description: "Use when deploying an Express webhook as a systemd service."
tags: [systemd, webhook, express, postgres, activepieces, deploy]
---

# Node Webhook systemd Service

## Overview

Run Express webhook servers as isolated systemd services with `.env` co-located in the server directory. Pattern used in paradise/golden projects.

## When to Use

- Deploying a webhook Express server as a production service
- Debugging webhook → DB → ActivePieces pipeline failures
- Fixing CORS, proxy, or database connection issues in production
- Adding a new webhook endpoint to an existing service

## When NOT to Use

- Development (use `nodemon` or `npm start` locally)
- Webhooks that need platform-native handling (use platform integrations)
- Long-running background workers (use Celery/queue systems)

## Core Pattern

```
VPS → systemd service → Express app → PostgreSQL → ActivePieces webhook
       WorkingDirectory=/path/to/server
       ExecStart=node server/webhook-server.js
       .env in same directory (PORT, PGHOST, CORS_ORIGINS, ACTIVEPIECES_WEBHOOK_URL)
```

## Quick Reference

**Service file location:** `/etc/systemd/system/<service>.service`
**Typical layout:** `server/webhook-server.js` + `.env` in same directory
**Key env vars:** `PORT`, `PGHOST`, `PGDATABASE`, `PGUSER`, `PGPASSWORD`, `CORS_ORIGINS`, `ACTIVEPIECES_WEBHOOK_URL`

## Implementation

### 1. Create systemd unit

```ini
[Unit]
Description=My Casino — Webhook Server
After=network.target

[Service]
Type=simple
WorkingDirectory=/root/paradise-casino/paradise-casino-landing
ExecStart=/usr/bin/node server/webhook-server.js
Restart=always
RestartSec=3
Environment=NODE_ENV=production

[Install]
WantedBy=multi-user.target
```

### 2. Safe edit cycle

```bash
# 1. Edit the code
# 2. Syntax check before restart
node --check server/webhook-server.js

# 3. Restart the service
systemctl restart <service>

# 4. Verify
systemctl is-active <service>
# Expected: active
```

### 3. End-to-end verification

```bash
# Send test lead
curl -X POST -H "Content-Type: application/json"   -H "Origin: https://<domain>"   -d '{"name":"Test","cedula":"123","telefono":"555","email":"test@test.com"}'   https://<domain>/webhook/leads

# Verify DB insert
docker exec <db> psql -U <user> -d <db> -tAc "SELECT * FROM leads ORDER BY id DESC LIMIT 1;"

# Verify AP flow
docker exec ap-db psql -U postgres -d activepieces -tAc   "SELECT status FROM flow_run WHERE "flowId"='<FLOW_ID>' ORDER BY "startTime" DESC LIMIT 1;"

# Clean up test data
docker exec <db> psql -U <user> -d <db> -c "DELETE FROM leads WHERE name='Test';"
```

## Common Mistakes

| Error | Cause | Fix |
|-------|-------|-----|
| Webhook doesn't write leads | PGHOST points to another project's DB | Verify container IP with `docker inspect` |
| Logs show proxy issues | Missing `app.set('trust proxy', true)` | Add it before route handlers |
| Date column empty | Form doesn't send `created_at` | Add `created_at: new Date().toISOString().slice(0,10)` in webhook |
| Change lost after restart | Repo not committed | `git commit -am "fix" && git push` |
| CORS rejected | Origin not in CORS_ORIGINS list | Add the real domain to `CORS_ORIGINS` in `.env` |
| Port already in use | Dev server still running | Kill dev process (`lsof -ti:<port> | xargs kill`) |

## Real-World Impact

- Golden's webhook pointed to IP `10.0.1.6` but its DB was at `10.0.1.8` — wrong IP = silent failure
- Golden had a fix committed locally but never pushed — service restarted with old code
- Forms missing `created_at` → DB column empty → AP sheet shows blank date
