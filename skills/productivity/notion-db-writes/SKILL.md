---
name: notion-db-writes
description: "Use when inserting rows into Notion DBs over raw HTTP"
tags: [notion, api, escritura, writes, database, dedup, ingesta]
---

# Notion DB Writes (headless scripts)

Class-level recipe for any agent flow that INSERTS rows into an existing Notion database: link-ingestion feeds, sync jobs, task/CRM-style DBs. Assumes a standard integration token, no SDK — raw HTTP that works from any Python/shell context.

## Workflow

### 1. Auth
Read the token from the env file (in this VPS: `NOTION_API_KEY` in `/opt/data/.env`, format k=v, ignore `#` lines — it is NOT exported to the shell). Send on every call:
`Authorization: Bearer <token>` · `Notion-Version: <version>` · `Content-Type: application/json`

### 2. Verify the DB schema BEFORE writing
`GET /v1/databases/{id}` — confirms the DB exists, is shared with the integration (otherwise 404), and gives exact property names/types. This also answers "which of the two same-named DBs is this?" (common when duplicates exist) and lists the exact select option strings.

### 3. Dedup query (correct endpoint shape)
Filter queries go to **POST `/v1/databases/{database_id}/query`** with the filter in the JSON body:
```json
{"filter": {"property": "Link", "url": {"equals": "https://..."}}}
```
The legacy shape — POST to `/v1/databases/query` with `database_id` inside the body — returns 400 `invalid_request_url`. When porting old snippets, move the ID into the path.

### 4. Create the page
POST `/v1/pages` with `"parent": {"database_id": "<id>"}`. If that returns 404 as parent, retry with `{"parent": {"data_source_id": "<same id>"}}` (API 2025-09-03 split databases into database_id + data_source_id; which one works has flipped between versions — try database_id first).

### 5. Verify
Read back the created page id/url from the response and (for ingestion feeds) report it. A 200 response with a page id is the only proof of the write.

## Pitfalls
- **Select values auto-create options.** Writing a select name not in the schema SILENTLY CREATES it (schema contamination). Copy option strings exactly from the schema — e.g. emoji-star strings `⭐⭐⭐⭐⭐`, not "5 estrellas".
- **rich_text cap:** 2000 chars per rich_text value — truncate before sending.
- **Shared-with-integration:** a DB that exists but isn't connected to the integration returns 404 `object_not_found` — that's a Notion UI fix (`...` → Connect to → integration), not an API bug.
- **Query can return 0 results even when rows exist** (known Notion quirk). For dedup this fails safe (may create a duplicate); never rely on a non-empty query result as proof something exists.
- **Same-named DBs drift:** verify by schema/columns, not by title. Known case in this workspace: two "Links de X" DBs, only one has Stack/Acción columns — see `references/notion-links-de-x.md`.
- **Rate limits:** back off on 429.

## Reference files
- `references/notion-links-de-x.md` — verified recipes + IDs for the Telegram "Links de X" ingestion DB (schema options, dedup filter, create payload, provenance).

## Related
- `productivity/notion` (hub) — full Notion API surface incl. ntn CLI, Workers, markdown endpoints.
- `notion-integration` (user-owned) — search/blocks patterns; its "Nexa Labs Notion Structure" ID table is STALE — the working Links de X DB id lives in the reference file above.
- `twitter-telegram-ingestion` (user-owned) — the ingestion workflow that exercises this class.