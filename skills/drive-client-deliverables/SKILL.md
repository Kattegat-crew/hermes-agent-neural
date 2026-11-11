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

## Updating an EXISTING file in-place (XLSX binary, verified nov-2026)

When a file already lives in Drive (e.g. a client review workbook) and must be updated WITHOUT changing its id, name, folder or share link, use `files().update` — never delete-and-recreate:

1. **Backup first**: download the current bytes (`files().get_media`) and save them to scratch before touching anything.
2. **Edit in memory**: `openpyxl.load_workbook(io.BytesIO(blob))` → modify → save to a fresh `io.BytesIO()` → `getvalue()`. No intermediate files on disk.
3. **Anti-collision precheck**: re-GET `fields='md5Checksum'` and assert it still equals the md5 captured in step 1. If it changed, someone edited concurrently — STOP and re-download; never overwrite blind.
4. **Upload**: `svc.files().update(fileId=fid, media_body=MediaIoBaseUpload(io.BytesIO(data), mimetype=XLSX_MIME, resumable=False))`. Capture `fields='id,name,modifiedTime,parents'` before and after and assert id, name and parents are unchanged (keeps the shared link working).
5. **Read-back verify**: re-download, assert `sha256(downloaded) == sha256(payload)`, then re-validate content row-by-row against the source data and save a JSON evidence file with counts and hashes (same read-back rule as the upload procedure above).

### openpyxl gotcha with Drive-formatted workbooks

Workbooks with inherited formatting report `max_row=1000` even with ~109 real data rows (empty formatted rows extend the used range). Consequences:

- NEVER iterate `range(2, ws.max_row+1)` or assert counts based on `ws.max_row`.
- Count/iterate only rows whose key column (e.g. ID) is non-empty; assert the set of found IDs equals the expected set.
- In `read_only` mode, filter first: `vals = [v for v in vals[1:] if v[cols['ID']]]` before counting.
- New columns: append at the end and copy the `_style` of an existing header cell so the approved formatting is preserved.

## Multi-client split rule
Never upload one combined document to multiple client folders. Split per client (e.g. python-docx: remove the other client's sections, `assert other_client not in text` per output), upload each separately, verify each independently. Clients are distinct tenants — their artifacts never mix.