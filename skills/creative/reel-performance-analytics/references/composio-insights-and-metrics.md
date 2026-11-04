# Composio Insights & Platform Metrics (verified 04/09/2026)

Reading POST-INSIGHTS from Instagram/Facebook via the Composio CLI — used to score the FINAL
published reel against real platform performance (not just to publish). Verified end-to-end against a
live IG Business account and a real FB Page (Golden Game).

## Why pull insights at all

Publishing is half the loop. The other half is `rendimiento = f(características del reel final)`.
Characteristic features (ffprobe/ffmpeg/scipy/faster-whisper) only become a useful benchmark when
joined to platform views/engagement. With <10 reels there is no regression signal; the first step is
palleting a base dataset of what you already published.

## Valid metric tools (slug → what they return)

**Instagram**
- `INSTAGRAM_GET_IG_MEDIA_INSIGHTS` — `{ig_user_id, media_id, metric}` → views, reach, likes,
  comments, saves, shares for a media object (photo, video, reel, carousel).
  - CONSTRAINT: insights only for media published within the **last 2 years** AND account with
    **≥1,000 followers** AND a **Business/Creator** account (personal profiles unsupported).
  - Metrics can lag the publish: verify status is `FINISHED` before asking; may be unavailable a few
    minutes after publishing.
  - Carousel children do NOT support insights — query at the parent carousel level.
- `INSTAGRAM_GET_IG_USER_MEDIA` — list media. `{ig_user_id, limit, fields}`. Add
  `id,caption,media_type,permalink,timestamp,like_count,comments_count,media_product_type` to match
  published reels to their ids; also use it to confirm a publish landed.
- `INSTAGRAM_GET_USER_INSIGHTS` — account-level reach/follower count; `metric_type=total_value` returns
  a `total_value` object instead of a time series.

**Facebook**
- `FACEBOOK_GET_PAGE_POSTS` — `{page_id, limit, fields}`. `fields=id,message,created_time,permalink_url`
  gives each post's real `permalink_url` (a `reel/<id>` URL identifies reels). Drop the `type` field —
  it's deprecated since Graph v3.3 (use `status_type`/`attachments`).
- `FACEBOOK_GET_POST_INSIGHTS` — `{post_id, period:'lifetime', metrics}`. The ONLY valid metric now is
  `post_media_view` (times the post entered the screen).

## ⚠️ FB deprecation that catches you (as of Nov 15, 2025)

The classic FB post metrics — `post_impressions`, `post_impressions_unique`, `post_clicks`,
`post_engagements`, `post_engaged_users`, `post_reactions_by_type_total` — are **deprecated and no
longer supported**. Requesting them yields errors. Only `post_media_view` is live. Request only the
metric you need to keep the payload small (large metric lists risk rate-limit errors 4/613 when looping
many posts).

## Composio CLI invocation (no shell-quoting breaks)

`composio execute <SLUG> --account <word_id> -d '<json>'`. Account selectors: the alias
("Golden Game"), the `word_id` (`instagram_demal-molala`), or the connected-account id
(`ca_vxw9d1oTla_a`).

Pitfalls:
- **`--account <alias>` must match the toolkit's registered alias** — a wrong alias →
  `ConnectedAccountResolutionError`. Use the `word_id` to be exact.
- **`ig_user_id` for `_GET_IG_USER_MEDIA`/`_GET_IG_MEDIA_INSIGHTS` is the numeric IG business id**, NOT
  the username and NOT the publish `ig_user_id`. Omit `ig_user_id` on `INSTAGRAM_GET_IG_USER_MEDIA` to
  target the CURRENT authenticated account; passing the wrong numeric id returns Graph error `code 100`
  ("Object ... does not exist or does not support this operation").
- Build `-d` payloads with `json.dumps(...)` in a script, never a shell single-quoted literal — emoji,
  `$`, `#` break inline strings.
- `--get-schema` prints `inputSchema.properties` → read the exact required fields before guessing.
- `FACEBOOK_GET_PAGE_POSTS` REQUIRES `page_id` (errors with it missing) — get it from
  `FACEBOOK_LIST_MANAGED_PAGES` first; the Meta account manages several pages.

## Pipeline shape (final reel → platform score)

1. Register `reel → {platform → media_id}` when publishing (or recover it via caption/timestamp using
   `_GET_IG_USER_MEDIA` / `_GET_PAGE_POSTS`).
2. Extract reel features on the FINAL mp4: ffprobe (dur/fps/res), ffmpeg (cuts, take length, LUFS,
   true peak), scipy (band energy, BPM), faster-whisper (words/sec, silences, CTA timestamp, repeated
   phrases) — see video-ai-generator `fit_voice.py` for the local faster-whisper venv pattern.
3. Pull platform performance via the tools above.
4. Cross: `normalized_metric = views / followers` (or per-day) so a newer reel isn't unfairly penalized;
   compare against a sibling reel rather than an absolute.

## Current connected accounts on this VPS

- IG Golden Game: `instagram_demal-molala` (business, `ig_user_id 40006158832316994`).
- IG Paradise/Lucky: `instagram_scot-linked` (`ig_user_id 27571270162548342`).
- FB: `facebook_uncite-skyish`, pages incl. Golden `820898971112738`, Paradise `765896786617957`.
- Composio 0.4.0 binary at `~/.composio/composio` (the `composio-linux-x64/composio` file is
  non-executable; use `$HOME/.composio/composio`).
