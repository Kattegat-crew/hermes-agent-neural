---
name: google-sheets-crm-sync
description: "Use when syncing Google Forms/Sheets rows into a CRM."
tags: [google-sheets, google-forms, drive-api, crm, sync, watermark, cron, twenty]
license: Apache-2.0
metadata:
  author: "neuralcrew"
  version: "1.0"
---

# Google Sheets to CRM Autonomous Sync

Pattern for synchronizing Google Forms / Google Sheets responses to backend CRM endpoints autonomously from Linux workers, avoiding user-side Google Apps Script setup.

## Why Drive CSV Export > Sheets API
- `Google Sheets API v4` frequently requires extra GCP project enablement, restricted quotas, or cloud proxies.
- `Google Drive API v3` export (`files/{id}/export?mimeType=text/csv`) works universally whenever Drive read scope is granted, retrieving raw sheet responses in a single HTTP request.

## Architecture

```
[ Google Form (Staff / Reception) ]
              ↓
  [ Google Sheet Responses ]
              ↓ (Every 2 min via Drive API CSV Export)
[ VPS Node.js Daemon (sync-redemptions.js) ]
              ↓ (Watermark dedup: redemptions_watermark.json)
[ Webhook Endpoint (POST /webhook/redeem) ]
              ↓
       [ Twenty CRM / DB ]
```

## Implementation Rules

1. **OAuth2 Refresh Loop**: Never rely on transient access tokens. Store `client_id`, `client_secret`, and `refresh_token` in a restricted `.env` (`chmod 600`). Refresh token on demand against `https://oauth2.googleapis.com/token`.
2. **Quote-Aware CSV Parsing**: Form responses often contain commas in text fields (e.g. `$20.000 COP`, `Sede, Bogotá`). Use a tokenizer that respects double-quote enclosures.
3. **State Watermarking**: Maintain an array of processed hash keys (`sheetId_timestamp_identifier`) in a local JSON watermark file. Skip already-processed rows on subsequent cron ticks.
4. **Idempotent Matching**: Match incoming sheet records against CRM leads using normalized phone (last 10 digits) OR email. If matched, update status to `REDIMIDO` and enrich empty phone fields.

## Minimal Cron Setup
```bash
*/2 * * * * docker exec -i webhook-gateway node sync-redemptions.js >> /var/log/sync-redemptions.log 2>&1
```
