---
name: composio-social-publishing
description: "Use when publishing to Instagram/Facebook via Composio."
tags: [instagram, facebook, composio, publicacion, social, api]
version: 1.0.0
author: Ragnar
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [social, instagram, facebook, composio, publishing, automations]
    related_skills: [xurl]
---

# Composio Social Publishing (Instagram / Facebook)

Publish campaign content to Instagram Business accounts and Facebook Pages via the **Composio CLI**
(`composio search / link / execute`). Composio uses **managed auth**: for most toolkits it uses Composio's
own OAuth app, so you do NOT register a Google/Meta developer app — you just hand the user a Composio
Connect Link and they authorize their account.

Reference file: `references/verified-flows-and-schemas.md` — exact tool slugs, required fields, and the
commands that were verified end-to-end against a live IG Business account and a real FB Page.

## When to use this (and when to use your OAuth hub instead)

Use Composio for **our/agency-side publishing** and quick connections: posting to the client's IG/FB,
sending from our own Gmail, Sheets for internal tracking. It is fast, no app registration, generous free tier
(100K tool-calls/mo, 50K triggers, free tier hard-capped).

Do NOT route **client multi-tenant OAuth custody** through Composio: tokens land in Composio's cloud, not our
VPS. For client Google/Meta connection custody + white-label branding, keep the self-hosted ActivePieces OAuth
hub and its branded connect gate (`connect.neuralcrewlabs.com`). Composio is a complement, not a replacement.

## Install (no root / no sudo on the VPS)

Composio's installer needs `unzip`. On a Debian box running as a non-root user (`hermes`) there is no sudo, so
provide a user-level `unzip`:

```bash
mkdir -p ~/.local/bin
cat > ~/.local/bin/unzip <<'PY'
#!/usr/bin/env python3
import sys, os, zipfile
def main():
    argv = sys.argv[1:]
    dest = "."; files = []; i = 0
    while i < len(argv):
        a = argv[i]
        if a.startswith("-"):
            flags = a.lstrip("-")
            if not flags: i += 1; continue
            if "d" in flags:            # -oqd <dir> <file>: the 'd' takes the NEXT arg
                if i + 1 < len(argv): dest = argv[i + 1]; i += 2
                else: i += 1
                continue
            i += 1; continue
        files.append(a); i += 1
    if not files: sys.stderr.write("unzip: no archive specified\n"); return 1
    archive = files[-1]
    os.makedirs(dest, exist_ok=True)
    with zipfile.ZipFile(archive) as z: z.extractall(dest)
    return 0
sys.exit(main())
PY
chmod +x ~/.local/bin/unzip
# ensure PATH for this and future sessions:
grep -q '.local/bin' ~/.bashrc || echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
export PATH="$HOME/.local/bin:$PATH"
curl -fsSL https://composio.dev/install | sh
```

PITFALL (installer invocation): the binary is `composio-linux-x64/composio`, but the check can fail with
"failed its version check" if the shell CWD was deleted (broken `getcwd`) — run from a valid working dir.
Also, a deleted CWD keeps stomping every later terminal call ("cd: /tmp/x: No such file"); reset it with
the terminal `workdir` param. `composio --version` returns `0.4.0`.

## Login (interactive — hand the URL to the human)

```bash
composio login --no-browser --no-wait --no-skill-install   # prints a dashboard URL
composio login --poll --no-skill-install                   # after the human authorizes
composio whoami
```
The user opens the printed `https://dashboard.composio.dev/?cliKey=...` URL, then you run `--poll`.

## Link an account (per toolkit) — the "sin crear app" flow

```bash
composio link gmail     --no-browser --no-wait   # returns a connect.composio.dev/enhanced/link/... URL
composio link instagram --no-browser --no-wait
composio link facebook  --no-browser --no-wait
```
Hand the Connect Link to the human; it is a link IN the chat (safe — credentials never pass through us).
After they authorize, verify with `composio connections list --toolkit <tk>` (status should be ACTIVE).

## Publish flows (VALIDATED)

**Instagram** is TWO steps (create a container, then publish it):
1. `INSTAGRAM_POST_IG_USER_MEDIA` — create the container with `ig_user_id`, `image_url`/`video_url`, `caption`.
   Returns `data.id` (the container/creation_id).
2. `INSTAGRAM_POST_IG_USER_MEDIA_PUBLISH` — `{ig_user_id, creation_id}` → returns the published media id.

**Facebook** is ONE step: `FACEBOOK_CREATE_PHOTO_POST` with `{page_id, url, message, published:true}` →
returns `post_id`.

Full field lists and exact commands with the working accounts are in `references/verified-flows-and-schemas.md`.

To build an on-brand Story from raw event footage (upscale to 1080x1920 + ffmpeg cartela overlay + IG safe zones), see `references/story-editing-ffmpeg.md`.

## Hard pitfalls (each one cost real time)

- **IG `media_type` is NOT `IMAGE`.** Accepted: `REELS`, `CAROUSEL`, `STORIES`. For a single image post
  **omit** `media_type` entirely (the API defaults to an image container). Passing `IMAGE` fails validation.
- **IG public URLs required**: `image_url`/`video_url` must be a URL Meta can download. Host it yourself — see
  hosting below. Composio's `--file` helper fails on IG with "multiple file_uploadable inputs (image_file,
  video_file) — pass the target field explicitly with -d".
- **FB wrong-page risk**: the same Meta account often manages MANY pages (e.g. Golden AND Paradise). Always run
  `FACEBOOK_LIST_MANAGED_PAGES` first and pick the exact page `id` — never post to the first page returned.
- **Dry-run stderr**: `composio execute ... --dry-run` can print errors to stderr, so `subprocess(capture_output=text)`
  can swallow it as empty stdout. Capture both streams (or run directly in the terminal) when diagnosing.
- **Verification limits**: `INSTAGRAM_GET_IG_MEDIA` errors on a video-only field for image posts (it still proves
  the media exists); `FACEBOOK_GET_POST` needs `pages_read_engagement` and 400s. For FB, trust the create
  `post_id` response; for IG, confirm by listing `INSTAGRAM_GET_IG_USER_MEDIA` (read its saved output file) and
  grepping for the media id / caption.
- **Stories do NOT show up in `INSTAGRAM_GET_IG_USER_MEDIA`** (that edge lists feed media only). To verify a live
  story, hit the node directly: `INSTAGRAM_GET_IG_MEDIA -d '{"ig_media_id":"<id>","fields":"id,media_type,
  media_product_type,permalink,timestamp,thumbnail_url"}'` → expect `media_product_type: "STORY"` plus a
  `https://www.instagram.com/stories/<handle>/<n>` permalink. **Strongest proof**: download `thumbnail_url` and
  review it (`vision_analyze`) — it is Meta's own render of the published file, so it proves the exact asset
  (text burned in, crops, no leftover app watermark) made it to the feed.
- **A 409 on publish means SUCCESS.** Re-running the publish step returns
  `Container <id> has already been PUBLISHED. Each container can only be published once.` Do NOT treat that as an
  error and never branch on the string `error` (the JSON always carries an `"error"` key): branch on
  `successful: true`. Video story containers created from a public mp4 were ready to publish ~60s after creation.
- **Do not publish a story straight from a phone screen recording.** Footage captured with apps like
  *MixCam Dual Video Recorder* carries an app watermark and a picture-in-picture window that must be cropped out
  first (see `references/story-editing-ffmpeg.md`).
- **Typical shell-quoting breaks JSON**: build `-d` payloads in a script with `json.dumps(...)` rather than
  a shell single-quoted literal (emoji + `$` + `#` break the inline string and make the tool return `{}`/parse
  errors).
- **Cloudflare caches a 404 on a freshly-uploaded asset** (verified 03/09): after `scp` of a NEW mp4 to
  `/opt/reels/assets/`, the public URL can return `404` with `server: cloudflare` / `cf-cache-status: HIT` even
  though the origin (`reels-web :9020`) serves it 200. Before handing a `video_url`/`image_url` to Meta, verify
  it with `curl -s -o /dev/null -w '%{http_code}'`; if 404 + `cf-cache-status: HIT`, either purge the CF cache for
  that URL or append a cache-buster query (`?v=<epoch>`) — the query-param URL returns 200 and Meta fetches it
  fine.

## Host the image/video at a public URL Meta can fetch

Meta must download the asset over a public URL. Host it on the VPS docroot served by `reels-web` (`:9020`):
```bash
scp /tmp/piece.png root@<prod-vps>:/opt/reels/assets/<slug>.png
curl -s -o /dev/null -w '%{http_code}' https://reels.neuralcrewlabs.com/assets/<slug>.png  # expect 200
```
`reels.neuralcrewlabs.com` serves `/opt/reels/` statically (200). NOTE: `goldengame.com.co` 404s the same
`/assets/...` path (its app does not serve static assets) — do not rely on it for URL hosting.

**Cloudflare caches a 404 on freshly-hosted MP4s.** `reels.neuralcrewlabs.com` is orange-cloud (proxied) via
Cloudflare. When you `scp` a new `.mp4` into `/opt/reels/assets/`, a public `curl` of the clean URL can return
`404` with `cf-cache-status: HIT` even though the origin (reels-web `:9020`) serves it 200 — Cloudflare cached
a 404 (often from a first request made before the file finished uploading, or from the *.png-verified cache).
Diagnose with `curl -sD - -o /dev/null <url> | grep -iE 'server:|cf-cache-status'` — `server: cloudflare` + `HIT`
= cached 404. **Fix: cache-bust with a query param** — `?v=<epoch>` makes a different cache key → origin → 200:
`curl -o /dev/null -w '%{http_code}' 'https://reels.neuralcrewlabs.com/assets/<slug>.mp4?v=1788491325'`. That URL
works for Meta to fetch (a query string is fine). If you want the clean URL to work, purge the Cloudflare cache
for that exact URL via the CF API token, otherwise just use the `?v=` URL. `INSTAGRAM_POST_IG_USER_MEDIA` with
`media_type: STORIES` accepts a `video_url` with the query — no need to strip it.

## Scheduling

Composio has **no native one-shot scheduler** for "post tool X at time Y". Triggers are event subscriptions.
To publish at a fixed time, use a Hermes **cron job (no_agent, script)** that runs the `composio execute`
at the desired time. It is deterministic (no LLM, no rate-limit risk, never deviates from the approved copy).
The creative/calendar decision belongs to the Social agent (Freyja); the mechanical trigger is a script cron;
the human gate (Jonathan / Review) must approve each piece before it is loaded into the calendar.

## Account ownership on this VPS

- Composio logged in as `captain@neuralcrewlabs.com`, org `captain_workspace` (`ok_HnCmqzb4jovQ`).
- IG connected: `@goldengame_casinos` (BUSINESS account, `ig_user_id 40006158832316994`), word_id `instagram_demal-molala`.
- FB connected: account `facebook_uncite-skyish`, manages pages including Golden Game Casinos (`820898971112738`)
  and The Grand Paradise Club Casino (`765896786617957`).
- IG @thegrandparadiseclubcasino (Paradise/Lucky): `ig_user_id 27571270162548342`, word_id `instagram_scot-linked` (connected 03/09/2026).
- Each IG account is a SEPARATE Composio connection (the Meta account's IG + FB are not one connection). To
  publish to a second IG (e.g. Paradise), `composio link instagram --alias <name>` and have the human authorize.

## Day-one copy/hook lesson (this user)

Jonathan's approved tone: warm, tuteo, "de pueblo", hook that pulls, then the CONCRETE prize number early in the
narration (not vague "algo grande"), and a clear CTA. Lead with the real draw (3 bingos, $50K→acumulado $1.6M,
viernes 5PM), not just atmosphere. See the campaign examples in the reference file.
