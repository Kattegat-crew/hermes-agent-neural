---
name: coolify-secure-secrets
description: "Use when deploying or rotating secrets in Coolify."
tags: [coolify, deploy, secretos, laravel, cifrado, postgres, rotacion, docker]
---

# Coolify Secure Secrets

## Overview

Deploy apps and databases in Coolify with manual deploys. Coolify stores secrets **encrypted** (Laravel AES, base64-encoded JSON with iv/mac) — never plaintext in the DB.

## When to Use

- Deploying a new app or database in Coolify (manual deploy via UI)
- Rotating database passwords or other Coolify secrets
- Fixing "payload is invalid" errors from Coolify's DB
- Connecting a deploy key to a private repository
- Verifying container networking between Coolify projects

## When NOT to Use

- Auto-deploy scenarios (this workflow is manual-only)
- Writing app code (use separate deployment scripts)
- Direct database operations on Coolify's internal DB

## Core Pattern

```
Coolify UI → Create resource (app/db)
  └─> Set secrets (encrypted via Laravel APP_KEY)
       └─> Manual deploy (trigger in UI)
            └─> Container runs on Docker host
                 └─> Network: coolify bridge (10.0.1.x)
```

## Quick Reference

| Resource | Container | Image | Network |
|----------|-----------|-------|---------|
| Coolify | `coolify` | coollabsio/coolify:4.1.2 | coolify |
| Coolify DB | `coolify-db` | postgres:15-alpine | coolify |
| Coolify Redis | `coolify-redis` | redis:7-alpine | coolify |
| Sentinel | `coolify-sentinel` | coollabsio/sentinel:0.0.21 | coolify |

**Coolify DB encryption:** Values encrypted with Laravel's `Crypt::encrypt()` → base64 JSON `{iv, value, mac}` (AES-256-CBC).

## Implementation

### 1. Create a database

```bash
# In Coolify UI: Resources → Create → Database → PostgreSQL
# Image: postgres:18-alpine
# Set password → Coolify encrypts it automatically
# Note IP: docker inspect <db-container> --format '{{.NetworkSettings.Networks.coolify.IPAddress}}'
# e.g. 10.0.1.12 (lucky-db)
```

### 2. Apply schema

```bash
docker exec <db-container> psql -U <user> -d <db> -c "CREATE TABLE ..."
```

### 3. Rotate a database password

1. Generate new password
2. Encrypt it via Coolify's Laravel encryption:
   ```bash
   docker exec coolify php artisan tinker
   >>> echo base64_encode(json_encode(Crypt::encrypt('new_password')));
   ```
3. Update the resource in Coolify UI with the encrypted value
4. Update `.env` of dependent apps (webhook, app)
5. Restart affected containers

### 4. Verify deployment

```bash
docker ps | grep <project-name>
docker inspect <db> --format '{{.NetworkSettings.Networks.coolify.IPAddress}}'
docker exec <db> psql -U <user> -d <db> -c "SELECT 1"
```

## Common Mistakes

| Error | Cause | Fix |
|-------|-------|-----|
| "payload is invalid" | Plaintext value in Coolify DB (must be encrypted) | Encrypt with Laravel APP_KEY first |
| Wrong DB connection | IP from another project's container | Verify with `docker inspect` on the correct network |
| Deploy fails | Missing deploy key for private repo | Add deploy key in Coolify settings |
| Container not running | Manual deploy not triggered | Trigger deploy from Coolify UI |
| Password rotation breaks app | Forgot to update app `.env` | Update all `.env` files, then restart containers |
