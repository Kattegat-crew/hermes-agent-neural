---
name: drive-client-deliverables
description: Use when uploading files to client Google Drive folders.
version: 1.0.0
author: Ragnar (NeuralCrew Labs)
license: internal
metadata:
  hermes:
    tags: [google-drive, upload, deliverables, oauth, verification]
    related_skills: [google-workspace-ops]
---

# Drive Client Deliverables (upload + verification)

## When to Use
- A generated file (Word, PDF, media) must land in a client's canonical Drive folder.
- Before telling the user a file is "on Drive" — the upload must be verified by read-back.

## Context
- Canonical root folder for client deliverables: `1yjLxB4lEZe3n79QKK8vlnladPv4FtM7w` (memory #5). Brand/campaign folders live under it; discover them by listing children rather than assuming ids.
- Composio Drive tools require staging local files through the remote workbench (s3key) before upload; for a one-off local `.docx` this adds failure modes. Direct Drive API with the materialized secret is simpler and verified.

## Upload procedure (multipart, no temp file server)

```python
import json, requests
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

with open('/opt/data/secrets/jonathan-drive.json') as f:
    s = json.load(f)
c = Credentials(None, refresh_token=s['refresh_token'], token_uri='https://oauth2.googleapis.com/token',
                client_id=s['client_id'], client_secret=s['client_secret'])
c.refresh(Request())
h = {'Authorization': 'Bearer ' + c.token}

with open(local_path, 'rb') as f:
    r = requests.post('https://www.googleapis.com/upload/drive/v3/files',
        params={'uploadType': 'multipart', 'supportsAllDrives': 'true',
                'fields': 'id,name,parents,webViewLink,md5Checksum'}, headers=h,
        files={'metadata': ('metadata', json.dumps({'name': local_path.name, 'parents': [folder_id]}),
                            'application/json; charset=UTF-8'),
               'file': (local_path.name, f, DOCX_MIME)}, timeout=60)
```

- Use the secret of the account that OWNS the target folder (`jonathan-drive.json`), never a client's own secret — a client secret passes GET but returns 403 `insufficientParentPermissions` on create (verified 16-sep, memory #5).
- No `share()` call: files inherit folder permissions; only change permissions when explicitly authorized.

## Mandatory verification (read-back, not tool success)
1. GET the file by id (`fields=id,name,parents,webViewLink,md5Checksum,trashed,supportsAllDrives`).
2. Assert `folder_id in parents` — catches silent uploads into root/My Drive.
3. Assert `md5Checksum == hashlib.md5(local_bytes).hexdigest()` — catches truncated/corrupt uploads.
4. Report the `webViewLink`, clearly stating it links the file, not the folder.

## Multi-client split rule
Never upload one combined document to multiple client folders. Split per client (e.g. python-docx: remove the other client's sections, `assert other_client not in text` per output), upload each separately, verify each independently. Clients are distinct tenants — their artifacts never mix.