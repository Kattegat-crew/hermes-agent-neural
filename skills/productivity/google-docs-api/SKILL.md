---
name: google-docs-api
description: >-
  Use when creating Google Docs content via the Docs API. Work around Google Docs API limitations when creating documents with content. Key issue: docs().create() produces an empty document with no paragraphs, and insertText requires an existing paragraph boundary (index must be < endIndex of a paragraph). Also covers full-content rebuilds of existing docs (deleteContentRange + insertText) and the OAuth scope-add pitfall (re-auth replaces the whole scope set). hermes: tags: [google, docs, api, workaround]
tags: [google, docs, api, workaround, oauth]
version: 1.0.0
author: hermes
license: MIT
metadata:---

# Google Docs API — Creating Documents with Content

## Problem
`docs_service.documents().create()` returns a document with NO paragraphs (just a section break).
`insertText` fails with: "Index X must be inside the bounds of an existing paragraph."

## Solution

### Step 1: Create the document
```python
doc = docs_service.documents().create(body={'title': 'Document Title'}).execute()
doc_id = doc.get('documentId')
```

### Step 2: Read body structure to find paragraph index
```python
doc_info = docs_service.documents().get(
    documentId=doc_id,
    fields='body.content'
).execute()

body_content = doc_info.get('body', {}).get('content', [])

# Find the paragraph's startIndex (usually 1, after section break at index 1)
paragraph_index = 1
for elem in body_content:
    if 'startIndex' in elem and 'paragraph' in elem:
        paragraph_index = elem['startIndex']
        break
```

### Step 3: Insert text INSIDE the paragraph (not at the end)
```python
requests = [{
    'insertText': {
        'location': {'index': paragraph_index},  # Must be WITHIN paragraph range
        'text': 'Your content here'
    }
}]

docs_service.documents().batchUpdate(
    documentId=doc_id,
    body={'requests': requests}
).execute()
```

## Key Points
- **Never** use `index=0` — that's before any content, no paragraph exists there
- **Never** use `index=endIndex` — insertText requires index < endIndex of the paragraph
- **Always** use `index=1` (or whatever `startIndex` the paragraph has) — inside the paragraph
- The document created by `docs().create()` always has a paragraph from index 1 to 2
- Use `fields='body.content'` to read structure efficiently

## Invalid Approaches (DON'T USE)
- `createParagraph` — NOT a valid request type in Google Docs API
- `insertText` at `index=0` — no paragraph at index 0
- `insertText` at `index=endIndex` — must be LESS than endIndex
- Creating doc via Drive API then inserting — same problem, no paragraphs

## Updating an Existing Document (Full Rewrite)

To update a doc the user already has (e.g. "revisa y actualiza este informe"), the
most reliable approach is a **full content rebuild** — especially when the doc is
plain markdown-as-text (no rich formatting to preserve). Do NOT try to patch
individual strings; replace everything in one batchUpdate.

### Step 1: Get the document and find the body range
```python
doc = docs_service.documents().get(documentId=DOC_ID).execute()
content = doc.get('body', {}).get('content', [])
end_index = content[-1].get('endIndex', 1)  # last element's endIndex
```

### Step 2: Delete all content + insert new content in ONE batchUpdate
```python
requests = [
    # delete everything after index 1 (keep the section break / first paragraph)
    {'deleteContentRange': {'range': {'startIndex': 1, 'endIndex': end_index - 1}}},
    # insert the full new text at index 1 (inside the surviving paragraph)
    {'insertText': {'location': {'index': 1}, 'text': NEW_CONTENT}}
]
docs_service.documents().batchUpdate(
    documentId=DOC_ID, body={'requests': requests}).execute()
```
- `deleteContentRange` endIndex must be `end_index - 1` (exclusive end), otherwise
  you get an error deleting the final section break.
- `insertText` at index 1 lands inside the paragraph that survives the delete.
- Both requests apply atomically in one call — no intermediate empty state.

### Step 3: Verify (always)
Read the doc back and assert key strings are present AND stale strings are absent:
```python
body = docs_service.documents().get(documentId=DOC_ID).execute()['body']
checks = [('new value present', 'deepseek-v4-flash-0731' in body),
          ('old value gone', 'Qwen 3.6 Plus:free' not in body)]
```
Print ✅/❌ per check. Don't say "done" until these pass.

## OAuth: Adding a Scope to an Existing Token (Critical Pitfall)

When you need a NEW permission (e.g. Docs write: `https://www.googleapis.com/auth/documents`),
re-running OAuth **REPLACES the entire scope set** — it does NOT merge with the old token.

- Generate the new auth URL with **ALL** previously granted scopes PLUS the new one.
  Omitting an old scope silently revokes it.
- The full 9-scope set in use: gmail.readonly, gmail.send, gmail.modify, calendar,
  drive, drive.file, contacts.readonly, spreadsheets, documents, documents.readonly.
- After the user pastes the callback, exchange with:
  `python3 setup.py --auth-code "http://localhost:1/?code=..."`
  (NOTE: in this environment setup.py rejects `--format json` — omit it.)
- Verify afterwards with `setup.py --check` and a real API call before relying on it.

## Moving Document to Folder
After creating content, move to folder using Drive API:
```python
drive_service.files().update(
    fileId=doc_id,
    addParents='FOLDER_ID',
    removeParents='root'
).execute()
```

## Authentication
- Token at `/opt/data/google_token.json`
- Scopes needed: `https://www.googleapis.com/auth/docs`
- Google Docs API must be enabled in Google Cloud Console

## Token Expiry: ALWAYS use google-auth, never raw urllib (Critical)

Access tokens expire (~1h). A raw `urllib.request` call with the stored token
fails with **HTTP 401 Unauthorized** — even though the refresh_token is valid.
The token file has a `refresh_token` that google-auth uses to auto-refresh.

**DON'T:**
```python
# 401 after ~1h — the stored access token is stale
req = urllib.request.Request(url, headers={'Authorization': f'Bearer {token}'})
```

**DO:** Use `google.oauth2.credentials.Credentials.from_authorized_user_info`,
which refreshes automatically on expiry:
```python
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

with open('/opt/data/google_token.json') as f:
    creds = Credentials.from_authorized_user_info(json.load(f))
# creds.refresh_token is used transparently when access token expires
service = build('docs', 'v1', credentials=creds)
doc = service.documents().get(documentId=DOC_ID).execute()
```

Same pattern applies to Drive, Sheets, Gmail — any `build()` call with these
creds auto-refreshes. If you ever see 401, the first suspect is raw-token usage.