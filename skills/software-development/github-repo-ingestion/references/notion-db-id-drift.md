# Notion DB ID Drift Detection

Notion database UUIDs stored in `.env` and skill documentation can become
stale. This was discovered on 2026-08-17 when the `NOTION_DB_REPOS` ID
returned 404 — the actual IDs had shifted.

## How to Find Current DB IDs

```python
import os, requests

with open('/opt/data/.env') as f:
    for line in f:
        if '=' in line and not line.startswith('#'):
            k, v = line.split('=', 1)
            os.environ[k.strip()] = v.strip()

api_key = os.environ.get('NOTION_API_KEY', '')
headers = {
    'Authorization': f'Bearer {api_key}',
    'Notion-Version': '2022-06-28',
    'Content-Type': 'application/json'
}

# Search ALL databases the integration can see
resp = requests.post('https://api.notion.com/v1/search',
    json={"filter": {"value": "database", "property": "object"}},
    headers=headers)

for r in resp.json().get('results', []):
    rid = r['id'].replace('-', '')
    title = ''
    if r.get('title'):
        title = ''.join([t['plain_text'] for t in r['title']])
    elif r.get('properties'):
        for pname, pval in r['properties'].items():
            if pval.get('type') == 'title' and pval.get('title'):
                title = ''.join([t['plain_text'] for t in pval['title']])
                break
    print(f'{rid} -> {title}')
```

## Verify Single DB ID

```python
resp = requests.get(f'https://api.notion.com/v1/databases/{db_id}', headers=headers)
if resp.status_code == 200:
    print(f"✅ DB valid")
elif resp.status_code == 404:
    print(f"❌ DB NOT FOUND — search for current ID")
```

## Historical Drift (2026-08-17)

| Database | Old (stale) ID | Current ID |
|----------|---------------|------------|
| Repos | `335853a7-3369-81ce-bd94-f2799db51efa` | `3ac853a7-3369-818d-a14f-daa9f26cbb6e` |
| Wiki | `335853a7-3369-813d-8d65-d11c0355c2cf` | `af30a0f1-a1ec-4600-95dd-c90ad596e473` |

The stale IDs share prefix `335853a7-3369-81` suggesting origin from a
previous workspace state or backup restore.

## After Finding Correct IDs

1. Update `/opt/data/.env` with the correct UUID
2. Update any skills that hardcode the IDs (notion-integration SKILL.md table)
3. Always verify via search before creating pages in the ingestion pipeline

## Schema Verification Pattern (2026-08-18)

Even when DB IDs are correct, field names can change. Always inspect the schema
before creating pages — pass the schema check to confirm the exact property names:

```python
db_id = os.environ.get('NOTION_DB_REPOS', '')
resp = requests.get(f'https://api.notion.com/v1/databases/{db_id}', headers=headers)
for name, prop in resp.json().get('properties', {}).items():
    print(f'{name} ({prop[\"type\"]})')
```

## execute_code > shell for Notion API calls

`execute_code` (Hermes Python tool) is more reliable than inline `curl` or
`source .env && curl` in terminal. Shell commands often fail to source `.env`
correctly inside Docker containers, while `execute_code` reads Python env vars
flawlessly. Use `execute_code` for all Notion writes.