---
name: notion
description: "Use when working with the Notion API, pages or databases."
tags: [notion, api, cli, database, markdown, workers]
version: 2.0.0
author: community
license: MIT
platforms: [linux, macos, windows]
prerequisites:
  env_vars: [NOTION_API_KEY]
metadata:
  hermes:
    tags: [Notion, Productivity, Notes, Database, API, CLI, Workers]
    homepage: https://developers.notion.com
---

# Notion

Talk to Notion two ways. Same integration token works for both — pick by what's available.

◆ **`ntn` CLI** — Notion's official CLI. Shorter syntax, one-line file uploads, required for Workers. macOS + Linux only as of May 2026 (Windows support "coming soon"). **Default when installed.**
◆ **HTTP + curl** — works everywhere including Windows. **Default fallback** when `ntn` isn't installed.

## Setup

### 1. Get an integration token (required for both paths)

1. Create an integration at https://notion.so/my-integrations
2. Copy the API key (starts with `ntn_` or `secret_`)
3. Store in `${HERMES_HOME:-~/.hermes}/.env`:
   ```
   NOTION_API_KEY=ntn_your_key_here
   ```
4. **Share target pages/databases with the integration** in Notion: page menu `...` → `Connect to` → your integration name. Without this, the API returns 404 for that page even though it exists.

### 2. Install `ntn` (preferred path on macOS / Linux)

```bash
# Recommended
curl -fsSL https://ntn.dev | bash

# Or via npm (needs Node 22+, npm 10+)
npm install --global ntn

ntn --version    # verify
```

**Skip `ntn login` — use the integration token instead.** This works headlessly, no browser needed:
```bash
export NOTION_API_TOKEN=$NOTION_API_KEY      # ntn reads NOTION_API_TOKEN
export NOTION_KEYRING=0                       # don't try to use the OS keychain
```

Add those exports to your shell profile (or to `${HERMES_HOME:-~/.hermes}/.env`) so every session inherits them.

### 3. Choose path at runtime

```bash
if command -v ntn >/dev/null 2>&1; then
  # use ntn
else
  # fall back to curl
fi
```

Windows users: skip step 2 entirely until native `ntn` ships — Path B works fine. If you want CLI ergonomics now, install `ntn` inside WSL2.

## API Basics

`Notion-Version: 2025-09-03` is required on all HTTP requests. `ntn` handles this for you. In this version, what users call "databases" are called **data sources** in the API.

## Path A — `ntn` CLI (preferred, macOS / Linux)

### Raw API calls (shorthand for curl)
```bash
ntn api v1/users                                  # GET
# POST with inline body
ntn api v1/pages parent[page_id]=abc123 \
  properties[title][0][text][content]="Notes"
ntn api v1/pages/abc123 -X PATCH archived:=true   # PATCH; := is non-string (bool/num/null)
```

Syntax notes:
- `key=value` — string fields
- `key[nested]=value` — nested object fields
- `key:=value` — typed assignment (booleans, numbers, null, arrays)

### Search
```bash
ntn api v1/search query="page title"
```

### Read page metadata
```bash
ntn api v1/pages/{page_id}
```

### Read page as Markdown (agent-friendly)
```bash
ntn api v1/pages/{page_id}/markdown
```

### Read page content as blocks
```bash
ntn api v1/blocks/{page_id}/children
```

### Create page from Markdown
```bash
ntn api v1/pages \
  parent[page_id]=xxx \
  properties[title][0][text][content]="Notes from meeting" \
  markdown="# Agenda

- Q3 roadmap
- Hiring"
```

### Patch a page with Markdown
```bash
ntn api v1/pages/{page_id}/markdown -X PATCH \
  markdown="## Update

Shipped the prototype."
```

### Query a database (data source)
```bash
ntn api v1/data_sources/{data_source_id}/query -X POST \
  filter[property]=Status filter[select][equals]=Active
```

For complex queries with `sorts`, multiple filter clauses, or compound logic, pipe JSON in:
```bash
echo '{"filter": {"property": "Status", "select": {"equals": "Active"}}, "sorts": [{"property": "Date", "direction": "descending"}]}' | \
  ntn api v1/data_sources/{data_source_id}/query -X POST --json -
```

### File uploads (one-liner — biggest CLI win)
```bash
ntn files create < photo.png
ntn files create --external-url https://example.com/photo.png
ntn files list
```

Compare to the 3-step HTTP flow (create upload → PUT bytes → reference).

### Useful env vars
| Var | Effect |
|---|---|
| `NOTION_API_TOKEN` | Auth token (overrides keychain) — set this to your integration token |
| `NOTION_KEYRING=0` | File-based creds at `~/.config/notion/auth.json` instead of OS keychain |
| `NOTION_WORKSPACE_ID` | Skip the workspace picker prompt |

## Path B — HTTP + curl (cross-platform, default on Windows)

All requests share this pattern:

```bash
curl -s -X GET "https://api.notion.com/v1/..." \
  -H "Authorization: Bearer $NOTION_API_KEY" \
  -H "Notion-Version: 2025-09-03" \
  -H "Content-Type: application/json"
```

On Windows the `curl` shipped with Windows 10+ works as-is. PowerShell users can also use `Invoke-RestMethod`.

### Search
```bash
curl -s -X POST "https://api.notion.com/v1/search" \
  -H "Authorization: Bearer $NOTION_API_KEY" \
  -H "Notion-Version: 2025-09-03" \
  -H "Content-Type: application/json" \
  -d '{"query": "page title"}'
```

### Read page metadata
```bash
curl -s "https://api.notion.com/v1/pages/{page_id}" \
  -H "Authorization: Bearer $NOTION_API_KEY" \
  -H "Notion-Version: 2025-09-03"
```

### Read page as Markdown (agent-friendly)

Easier to feed to a model than block JSON.

```bash
curl -s "https://api.notion.com/v1/pages/{page_id}/markdown" \
  -H "Authorization: Bearer $NOTION_API_KEY" \
  -H "Notion-Version: 2025-09-03"
```

### Read page content as blocks (when you need structure)
```bash
curl -s "https://api.notion.com/v1/blocks/{page_id}/children" \
  -H "Authorization: Bearer $NOTION_API_KEY" \
  -H "Notion-Version: 2025-09-03"
```

### Create page from Markdown

`POST /v1/pages` accepts a `markdown` body param.

```bash
curl -s -X POST "https://api.notion.com/v1/pages" \
  -H "Authorization: Bearer $NOTION_API_KEY" \
  -H "Notion-Version: 2025-09-03" \
  -H "Content-Type: application/json" \
  -d '{
    "parent": {"page_id": "xxx"},
    "properties": {"title": [{"text": {"content": "Notes from meeting"}}]},
    "markdown": "# Agenda\n\n- Q3 roadmap\n- Hiring\n\n## Decisions\n- Ship MVP Friday"
  }'
```

### Patch a page with Markdown
```bash
curl -s -X PATCH "https://api.notion.com/v1/pages/{page_id}/markdown" \
  -H "Authorization: Bearer $NOTION_API_KEY" \
  -H "Notion-Version: 2025-09-03" \
  -H "Content-Type: application/json" \
  -d '{"markdown": "## Update\n\nShipped the prototype."}'
```

### Create page in a database (typed properties)
```bash
curl -s -X POST "https://api.notion.com/v1/pages" \
  -H "Authorization: Bearer $NOTION_API_KEY" \
  -H "Notion-Version: 2025-09-03" \
  -H "Content-Type: application/json" \
  -d '{
    "parent": {"database_id": "xxx"},
    "properties": {
      "Name": {"title": [{"text": {"content": "New Item"}}]},
      "Status": {"select": {"name": "Todo"}}
    }
  }'
```

### Query a database (data source)
```bash
curl -s -X POST "https://api.notion.com/v1/data_sources/{data_source_id}/query" \
  -H "Authorization: Bearer $NOTION_API_KEY" \
  -H "Notion-Version: 2025-09-03" \
  -H "Content-Type: application/json" \
  -d '{
    "filter": {"property": "Status", "select": {"equals": "Active"}},
    "sorts": [{"property": "Date", "direction": "descending"}]
  }'
```

### Create a database
```bash
curl -s -X POST "https://api.notion.com/v1/data_sources" \
  -H "Authorization: Bearer $NOTION_API_KEY" \
  -H "Notion-Version: 2025-09-03" \
  -H "Content-Type: application/json" \
  -d '{
    "parent": {"page_id": "xxx"},
    "title": [{"text": {"content": "My Database"}}],
    "properties": {
      "Name": {"title": {}},
      "Status": {"select": {"options": [{"name": "Todo"}, {"name": "Done"}]}},
      "Date": {"date": {}}
    }
  }'
```

### Update page properties
```bash
curl -s -X PATCH "https://api.notion.com/v1/pages/{page_id}" \
  -H "Authorization: Bearer $NOTION_API_KEY" \
  -H "Notion-Version: 2025-09-03" \
  -H "Content-Type: application/json" \
  -d '{"properties": {"Status": {"select": {"name": "Done"}}}}'
```

### Append blocks to a page
```bash
curl -s -X PATCH "https://api.notion.com/v1/blocks/{page_id}/children" \
  -H "Authorization: Bearer $NOTION_API_KEY" \
  -H "Notion-Version: 2025-09-03" \
  -H "Content-Type: application/json" \
  -d '{
    "children": [
      {"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"text": {"content": "Hello from Hermes!"}}]}}
    ]
  }'
```

### File uploads (3-step flow)
```bash
# 1. Create upload
curl -s -X POST "https://api.notion.com/v1/file_uploads" \
  -H "Authorization: Bearer $NOTION_API_KEY" \
  -H "Notion-Version: 2025-09-03" \
  -H "Content-Type: application/json" \
  -d '{"filename": "photo.png", "content_type": "image/png"}'

# 2. PUT bytes to the upload_url returned above
curl -s -X PUT "{upload_url}" --data-binary @photo.png

# 3. Reference {file_upload_id} in a page/block payload
```

## Property Types

Common property formats for database items:

- **Title:** `{"title": [{"text": {"content": "..."}}]}`
- **Rich text:** `{"rich_text": [{"text": {"content": "..."}}]}`
- **Select:** `{"select": {"name": "Option"}}`
- **Multi-select:** `{"multi_select": [{"name": "A"}, {"name": "B"}]}`
- **Date:** `{"date": {"start": "2026-01-15", "end": "2026-01-16"}}`
- **Checkbox:** `{"checkbox": true}`
- **Number:** `{"number": 42}`
- **URL:** `{"url": "https://..."}`
- **Email:** `{"email": "user@example.com"}`
- **Relation:** `{"relation": [{"id": "page_id"}]}`

## API Version 2025-09-03 — Databases vs Data Sources

- **Databases became data sources.** Use `/data_sources/` endpoints for queries and retrieval.
- **Two IDs per database:** `database_id` and `data_source_id`.
  - `database_id` when creating pages: `parent: {"database_id": "..."}`
  - `data_source_id` when querying: `POST /v1/data_sources/{id}/query`
- Search returns databases as `"object": "data_source"` with the `data_source_id` field.

## Notion Workers (advanced, requires `ntn`)

Workers are TypeScript programs Notion hosts for you. One worker can expose any combination of:
- **Syncs** — pull data from external APIs into a Notion database on a schedule (default 30 min).
- **Tools** — appear as callable tools inside Notion's Custom Agents.
- **Webhooks** — receive HTTP events from external services (GitHub, Stripe, etc.) and act in Notion.

**Plan / platform gating:**
- CLI works on all plans. **Deploying Workers requires Business or Enterprise.**
- `ntn` is macOS/Linux only as of May 2026. Windows users need WSL2 or to wait for native support.
- Free through August 11, 2026; metered on Notion credits after.

### Minimal Worker

```bash
ntn workers new my-worker      # scaffold
cd my-worker
# Edit src/index.ts
ntn workers deploy --name my-worker
```

`src/index.ts`:
```typescript
import { Worker } from "@notionhq/workers";

const worker = new Worker();
export default worker;

worker.tool("greet", {
  title: "Greet a User",
  description: "Returns a friendly greeting",
  inputSchema: { type: "object", properties: { name: { type: "string" } }, required: ["name"] },
  execute: async ({ name }) => `Hello, ${name}!`,
});
```

### Webhook capability

```typescript
worker.webhook("onGithubPush", {
  title: "GitHub Push Handler",
  execute: async (events, { notion }) => {
    for (const event of events) {
      // event.body, event.rawBody (for signature verification), event.headers
      console.log("got delivery", event.deliveryId);
    }
  },
});
```

After deploy: `ntn workers webhooks list` shows the URL Notion generates. Treat that URL as a secret — anyone with it can POST events unless you add signature verification.

### Worker lifecycle commands

```bash
ntn workers deploy
ntn workers list
ntn workers exec <capability-key> -d '{"name": "world"}'
ntn workers sync trigger <key>            # run a sync now
ntn workers sync pause <key>
ntn workers env set GITHUB_WEBHOOK_SECRET=...
ntn workers runs list                     # recent invocations
ntn workers runs logs <run-id>
ntn workers webhooks list
```

When asked to build a Worker, scaffold with `ntn workers new`, write the code in `src/index.ts`, set any secrets with `ntn workers env set`, and deploy. Notion's docs at https://developers.notion.com/workers cover the full API surface.

## Notion-Flavored Markdown (used by `/markdown` endpoints)

Standard CommonMark plus XML-like tags for Notion-specific blocks. Use **tabs** for indentation.

**Blocks beyond CommonMark:**
```
<callout icon="🎯" color="blue_bg">
	Ship the MVP by **Friday**.
</callout>

<details color="gray">
<summary>Toggle title</summary>
	Children indented one tab
</details>

<columns>
	<column>Left side</column>
	<column>Right side</column>
</columns>

<table_of_contents color="gray"/>
```

**Inline:**
- Mentions: `<mention-user url="..."/>`, `<mention-page url="...">Title</mention-page>`, `<mention-date start="2026-05-15"/>`
- Underline: `<span underline="true">text</span>`
- Color: `<span color="blue">text</span>` or block-level `{color="blue"}` on the first line
- Math: inline `$x^2$`, block `$$ ... $$`
- Citations: `[^https://example.com]`

**Colors:** `gray brown orange yellow green blue purple pink red`, plus `*_bg` variants for backgrounds.

Headings 5/6 collapse to H4. Multiple `>` lines render as separate quote blocks — use `<br>` inside a single `>` for multi-line quotes.

## Choosing the Right Path

| Task | mac / Linux | Windows |
|---|---|---|
| Read/write pages, search, query databases | `ntn api ...` | curl |
| Read a page for an agent to summarize | `ntn api v1/pages/{id}/markdown` | curl `/markdown` endpoint |
| Upload a file | `ntn files create < file` | 3-step HTTP flow |
| One-off API exploration | `ntn api ...` | curl |
| Build a sync / webhook / agent tool hosted by Notion | `ntn workers ...` | WSL2 + `ntn workers ...` |

## Notes

- Page/database IDs are UUIDs (with or without dashes — both accepted).
- Rate limit: ~3 requests/second average. The CLI doesn't bypass this.
- The API cannot set database **view** filters — that's UI-only.
- Use `"is_inline": true` when creating data sources to embed them in a page.
- Always pass `-s` to curl to suppress progress bars (cleaner agent output).
- Pipe JSON through `jq` when reading: `... | jq '.results[0].properties'`.
- Notion also ships an MCP server now (`Notion MCP`, ~91% more token-efficient on DB ops than the previous version) — wire it via Hermes' MCP support if you want streaming Notion access from inside a session, but the paths above are enough for most one-shot tasks.


<!-- absorbido de productivity/notion-integration (censo 2026-09-24) -->
# Notion Integration


Configure and operate the Notion API for workspace management, wikis, and task tracking.

## Authentication


```python
headers = {
    'Authorization': 'Bearer YOUR_INTEGRATION_TOKEN',
    'Notion-Version': '2022-06-28'
}
```

## Searching All Accessible Content


```python
import requests

headers = {
    'Authorization': 'Bearer YOUR_TOKEN',
    'Notion-Version': '2022-06-28'
}

# Search everything the integration has access to

resp = requests.post('https://api.notion.com/v1/search', json={}, headers=headers)
data = resp.json()

for item in data.get('results', []):
    obj_type = item.get('object', '')
    if obj_type == 'page':
        # Title may be in properties or inside the page content
        title = ''
        if 'properties' in item:
            for pname, pval in item['properties'].items():
                if pval.get('type') == 'title' and pval.get('title'):
                    title = pval['title'][0].get('plain_text', '')
                    break
        parent = item.get('parent', {})
        print(f'  [PAGE] {title or "(untitled)"} | parent: {parent.get("type", "?")}')
    elif obj_type == 'database':
        title = ''
        if item.get('title'):
            title = item['title'][0].get('plain_text', '') if item['title'] else ''
        print(f'  [DB]   {title or "(untitled)"}')
```

## Reading Page Content (Blocks)


Pages often have their title inside the content, not as a property. To read a page:

```python
# Get page blocks (children)

page_id = 'YOUR_PAGE_ID'
resp = requests.get(f'https://api.notion.com/v1/blocks/{page_id}/children', headers=headers)
data = resp.json()

for block in data.get('results', []):
    btype = block['type']
    if btype in ('paragraph', 'heading_1', 'heading_2', 'heading_3',
                 'bulleted_list_item', 'numbered_list_item', 'to_do'):
        content_list = block.get(btype, [])
        text_parts = []
        if isinstance(content_list, list):
            for item in content_list:
                if isinstance(item, dict) and item.get('rich_text'):
                    for rt in item['rich_text']:
                        if isinstance(rt, dict) and rt.get('text', {}).get('content'):
                            text_parts.append(rt['text']['content'])
        if text_parts:
            print(f'  [{btype}] {" ".join(text_parts)}')
    elif btype == 'child_database':
        tl = block['child_database'].get('title', [])
        title = tl[0].get('plain_text', '(untitled)') if isinstance(tl, list) and tl and isinstance(tl[0], dict) else '(untitled)'
        print(f'  [child_database] {title}')
    elif btype == 'child_page':
        title = block['child_page'].get('title', '(untitled)')
        print(f'  [child_page] {title}')
```

## Important: Pagination


Notion returns max 100 results per search/page. If `has_more` is true:

```python
next_cursor = data.get('next_cursor')
while next_cursor:
    resp = requests.post('https://api.notion.com/v1/search',
        json={'cursor': next_cursor, 'page_size': 100},
        headers=headers)
    data = resp.json()
    next_cursor = data.get('next_cursor')
```

## Creating a Page


```python
parent = {'page_id': 'PARENT_PAGE_ID'}  # or {'database_id': 'DB_ID'}
resp = requests.post('https://api.notion.com/v1/pages',
    json={
        'parent': parent,
        'properties': {
            'Name': {'title': [{'text': {'content': 'Page Title'}}]}
        },
        'children': [
            {
                'object': 'block',
                'type': 'paragraph',
                'paragraph': {
                    'rich_text': [{'type': 'text', 'text': {'content': 'Hello world'}}]
                }
            }
        ]
    },
    headers=headers)
```

## Creating a Database


```python
resp = requests.post('https://api.notion.com/v1/databases',
    json={
        'parent': {'type': 'page_id', 'page_id': 'PARENT_PAGE_ID'},
        'title': [{'type': 'text', 'text': {'content': 'My Database'}}],
        'properties': {
            'Name': {'title': {}},
            'Status': {'select': {'options': [{'name': 'Pending'}, {'name': 'Done'}]}},
            'Due Date': {'date': {}}
        }
    },
    headers=headers)
```

## Key Gotchas


1. **Token may be missing even if "configured":** The notion-integration skill may say "Hecho" in task lists, but the actual token might not be in `.env`. Always verify with `grep -ri "notion" /opt/data/.env` across ALL env files (`/opt/data/.env`, `/opt/data/hermes-workspace/.env`, `config.yaml`). The token is often forgotten or configured via a different method.

2. **Token may exist only in session history:** If the user shared a Notion token in a past conversation but it was never saved to `.env`, search session files for the token pattern:
   ```bash
   grep -ro 'ntn_[a-zA-Z0-9]\{20,\}' /opt/data/sessions/ | head -5
   ```
   The token format is `ntn_` followed by 30+ alphanumeric characters. Extract it and add to `.env` as `NOTION_API_KEY=`.

3. **Docker container permission issues:** Inside the Docker container, `/opt/data/.env` may be owned by root with no write permissions and no `sudo` available. Workarounds:
   - Copy the file, modify the copy, and use the copy for testing: `cp /opt/data/.env /opt/data/.env.modified`
   - The token can still be used directly in Python scripts without being in `.env`
   - For persistence, ask the user to add it to their local `.env` outside the container

2. **Pages shared with integration:** The integration only sees pages explicitly shared with it. Check the Notion UI — click "..." on a page → "Add connections" → find your integration.

3. **Title location:** Page titles may be in `properties` OR inside the page content blocks. Always check both.

4. **rich_text format:** Text is always nested: `block[type][0].rich_text[0].text.content`. Handle both dict and string types.

5. **child_database title:** The `title` field is a list of rich_text objects, NOT a simple string.

6. **Pagination:** Always check `has_more` and paginate for large workspaces.

7. **Rate limits:** Notion has rate limits. If you get 429, back off and retry.
8. **Notion DB page content:** Pages inside Notion databases CANNOT have blocks appended via `/blocks/{page_id}/children` PATCH. You must include content in the `children` array of the POST to `/v1/pages` when creating.
9. **Paragraph text limit:** Each paragraph block's `rich_text[0].text.content` is limited to **2000 characters**. Truncate content before sending.
10. **DB field names:** Database property names are custom — always query the DB schema first to get exact field names (e.g., "Estado" not "Status", "Categoria" not "Category"). Use `GET /v1/databases/{id}` to inspect.
11. **Sync script content truncation:** The wiki-to-notion-sync script (`/opt/data/scripts/wiki-to-notion-sync.py`) has a `create_notion_page_with_content()` function that truncates to 1900 chars per paragraph. Use it for wiki sync.
12. **Notion DB query returns 0 pages (KNOWN BUG):** The `GET /v1/databases/{id}/query` endpoint can silently return 0 results even when pages exist in the database. Direct POST (create) and PATCH (update) work fine. **Workaround:** Don't rely on query to check existing pages. Create tasks directly with POST. Use conflict detection (HTTP 409) or a separate tracking list to avoid duplicates. If you must check existing, use the Search endpoint (`POST /v1/search`) instead, though it has its own quirks.

## Related: Dual Knowledge System


For setups where agents use Obsidian (Markdown) as source of truth and Notion as human-facing view, see the `dual-knowledge-system` skill. This is the recommended pattern for Hermes since agents natively read/write Markdown files while humans benefit from Notion's visual interface.

## Common Operations


| Operation | Endpoint | Method |
|-----------|----------|--------|
| Search | `/v1/search` | POST |
| Get page | `/v1/pages/{id}` | GET |
| Page blocks | `/v1/blocks/{id}/children` | GET |
| Create page | `/v1/pages` | POST |
| Create database | `/v1/databases` | POST |
| Append blocks | `/v1/blocks/{id}/children` | PATCH |
| Update page | `/v1/pages/{id}` | PATCH |
| Query database | `/v1/databases/{id}/query` | POST |

## Nexa Labs Notion Structure


**Parent:** "Nexa Labs" — `335853a7-3369-803a-9a82-edb6246e1ea5`

| Database | ID | Purpose |
|---|---|---|
| Links de X | `335853a7-3369-81e3-b261-e4e44c10fc36` | Twitter/X links |
| Repos | `3ac853a7-3369-818d-a14f-daa9f26cbb6e` | GitHub repos |
| TikToks | `335853a7-3369-810a-8e5e-c79c1ae7fb09` | TikTok videos |
| Wiki | `af30a0f1-a1ec-4600-95dd-c90ad596e473` | Brain Wiki pages |
| Tasks | `349853a7-3369-8139-a73e-d0e4213c215c` | Task tracking |

**Sync script:** `/opt/data/scripts/wiki-to-notion-sync.py` — reads Brain Wiki files and updates Notion Wiki DB automatically.
