# Image Gallery Uploads via JSON_LISTINGS_FEED (verified 03-nov-2026, Amazon AU)

## Why not Listings Items PATCH/PUT
Submitting `main_product_image_locator` / `other_product_image_locator_N` via PATCH or PUT on
`/listings/2021-08-01/items` returns `ACCEPTED` with **0 issues**, but Amazon's async image
pipeline frequently reverts the gallery (single read showed 5 images -> back to 1 image minutes
later). The Feeds API is the reliable route; same schema, processed server-side.

## Image attribute keys
- `main_product_image_locator` (index 0)
- `other_product_image_locator_1` .. `_N` (secondary)
- Each value: `[{"marketplace_id": MP, "media_location": "https://.../file.png"}]
- `media_location` must be a **publicly reachable URL** (verified working: Cloudflare Pages
  `amazon-au-media.pages.dev`, 15/15 files HTTP 200).

## Feed recipe (Python, in /opt/hermes-agent-data/amazon-spapi-setup/feed_images.py)
1. Build JSON doc:
   ```json
   {"header": {"sellerId": SELLER, "version": "2.0", "issueLocale": "en_AU"},
    "messages": [{"messageId": 1, "sku": "PS-XXXX", "operationType": "PATCH",
                  "productType": "PET_TOY",
                  "patches": [{"op": "replace", "path": "/attributes/<image_key>",
                               "value": [{"marketplace_id": MP, "media_location": "URL"}]}]}]}
   ```
2. `POST /feeds/2021-06-30/documents` with `{"contentType": "application/json; charset=UTF-8"}`
   -> returns presigned `url` + `feedDocumentId`.
3. `PUT` the JSON body to that presigned URL (header `Content-Type: application/json; charset=UTF-8`).
4. `POST /feeds/2021-06-30/feeds` with `{"feedType": "JSON_LISTINGS_FEED",
   "marketplaceIds": [MP], "inputFeedDocumentId": ...}` -> `feedId`.
5. Poll `GET /feeds/2021-06-30/feeds/{feedId}` every ~12 s. Statuses: IN_QUEUE -> IN_PROGRESS
   -> DONE. Observed 3-10 min for a 2-message feed; do NOT abort early.
6. On DONE: `resultFeedDocumentId` -> `GET /feeds/2021-06-30/documents/{id}` -> download `url`.

## Report parsing gotcha
The result document is often **gzip-compressed** (first byte 0x1f, second 0x8b). Plain
`json.load()` dies with `UnicodeDecodeError: 'utf-8' codec can't decode byte 0x8b`. Handle:
```python
raw = urlopen(rd['url']).read()
try: rep = json.loads(gzip.decompress(raw))
except Exception: rep = json.loads(raw)
```
Success report: `summary.errors: 0, messagesAccepted == messagesProcessed`, empty `issues`.

## Verification discipline
- After feed DONE, re-read each listing (`get_listing`) and count image keys.
- Gallery state **fluctuates** during Amazon's pipeline: a listing may show 5 images, then 1,
  then settle. Confirm stability with a monitor loop (every 5 min, exit when all SKUs >= 5 imgs,
  3 h timeout) — `monitor_galeria.py` in the same dir writes snapshots to
  `monitor-galeria.json`.
- A feed reporting accepted with 0 errors does NOT guarantee the image persisted; only the
  stabilized listings read does.

## Credentials
If `/opt/data/amazon-spapi-setup/.env` is missing/stale, pull creds from Vaultwarden
(`vw get "Terceros/Amazon SP-API - NeuralCrew"`); AU endpoint `sellingpartnerapi-fe.amazon.com`.
Feeds API requires the same LWA token as Listings (no extra role needed; `createFeedDocument`
201 confirms access).