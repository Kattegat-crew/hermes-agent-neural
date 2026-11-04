# Verified Composio publishing flows & schemas

Everything below was verified end-to-end (2026-09-03) against `@goldengame_casinos` (a live IG BUSINESS
account) and a real FB Page, via the Composio CLI `v0.4.0`.

## Account discovery

```bash
composio whoami
# -> account_type:human, email:captain@neuralcrewlabs.com, org:captain_workspace (ok_HnCmqzb4jovQ)
composio connections list --toolkit gmail        # status ACTIVE
composio connections list --toolkit instagram
composio connections list --toolkit facebook
```

## Gmail (single step, read-only check)

```bash
composio execute GMAIL_LIST_LABELS --account gmail_reps-banter -d '{}'
# It was connected via managed auth (no Google app registration). --account uses the word_id from the list.
```

## Instagram — TWO steps

### Step 1: create the media container
```bash
composio execute INSTAGRAM_POST_IG_USER_MEDIA --account instagram_demal-molala -d \
  '{"ig_user_id":"40006158832316994","image_url":"https://reels.neuralcrewlabs.com/assets/<slug>.png","caption":"..."}'
# -> {"successful":true,"data":{"id":"17899717539596245"}}   // data.id = container/creation_id
```
- `ig_user_id` required; `caption`, `image_url`/`video_url` used. For a single IMAGE post **omit media_type**
  (passing `"IMAGE"` fails validation: "Instance does not match any of [REELS,CAROUSEL,STORIES]").
- `INSTAGRAM_GET_USER_INFO` confirms account_type:BUSINESS without an app.

### Step 2: publish the container
```bash
composio execute INSTAGRAM_POST_IG_USER_MEDIA_PUBLISH --account instagram_demal-molala -d \
  '{"ig_user_id":"40006158832316994","creation_id":"17899717539596245"}'
# -> {"successful":true,"data":{"id":"18135376444535152"}}   // published media id
```

### IG formats supported (media_type enum)
`REELS` (needs `video_url` mp4 public; optional `cover_url`, `share_to_feed`), `CAROUSEL` (needs
`children: []` of container IDs created first), `STORIES`. Fields available on the tool: `caption`, `alt_text`,
`children`, `cover_url`, `image_url`, `user_tags`, `video_url`, `audio_name`, `ig_user_id`, `image_file`,
`video_file`, `media_type`, `location_id`, `thumb_offset`, `share_to_feed`, `is_carousel_item`, `graph_api_version`.

## Facebook — ONE step

```bash
composio execute FACEBOOK_CREATE_PHOTO_POST --account facebook_uncite-skyish -d \
  '{"page_id":"765896786617957","url":"https://reels.neuralcrewlabs.com/assets/<slug>.png","message":"...","published":true}'
# -> {"successful":true,"data":{"id":"122146167471096603","post_id":"765896786617957_122146167489096603"}}
```
- `page_id` required; `url` (public image) or `photo`/`media` (local file); `message` caption;
  `published:true` to go live. `scheduled_publish_time` (unix) + `published:false` supports FB-scheduled posts.
- ALWAYS pick the page id from `FACEBOOK_LIST_MANAGED_PAGES` — a Meta account can manage many pages.
  Known page ids: Golden Game Casinos `820898971112738`, The Grand Paradise Club Casino `765896786617957`.
- Other FB tools: `FACEBOOK_CREATE_POST` (text/link), `FACEBOOK_CREATE_VIDEO_POST`, `FACEBOOK_UPLOAD_PHOTOS_BATCH`,
  `FACEBOOK_UPDATE_POST`, `FACEBOOK_DELETE_POST`.

## Verification after posting

- IG: `INSTAGRAM_GET_IG_MEDIA` errors on a video-only field for image posts (proves the node exists) and
  `FACEBOOK_GET_POST` 400s without `pages_read_engagement`. Instead: `INSTAGRAM_GET_IG_USER_MEDIA` (large output
  is written to a file `storedInFile`/`outputFilePath`) and grep the JSON for the media id/caption; for FB trust
  the create `post_id`.

## Hosting an asset for Meta to fetch

```bash
scp /tmp/piece.png root@100.73.30.29:/opt/reels/assets/<slug>.png
curl -s -o /dev/null -w '%{http_code}' https://reels.neuralcrewlabs.com/assets/<slug>.png   # 200 = OK
```
`reels-web` (:9020) serves `/opt/reels/` statically. `goldengame.com.co` 404s `/assets/...` — do not use it.

## Reliability of the execute call (build payloads in a script)

Because captions carry emoji, `$` and `#`, a shell single-quoted `-d` breaks. Use a small Python driver with
`json.dumps({...})` and `subprocess.run(["composio",...], capture_output=True, text=True)` — and read BOTH
`stdout` and `stderr` (dry-run errors go to stderr and can look like empty output otherwise).

## Campaign copy (Golden, approved)

> Hay noches para jugar… y hay noches para vivirlas con Goldie. 🎱✨\n\nEste septiembre es de bingo, música y
> buenos amigos. Y en Golden Game los viernes se juega en grande: tres bingos por noche, desde $50.000 hasta un
> acumulado que llega a $1.600.000 por local.\n\nLa suerte ya se está calentando. ❤️\n\nVen a tu sede de siempre,
> vive la experiencia y deja que Goldie haga el resto. Te esperamos cada viernes desde las 5 p.m. 🎲\n
> #GoldenGame #BingoMillonario #AmorYAmistad #Goldie #JuegoResponsable

The Paradise (Lucky) version swaps the mascot/brand for Lucky / The Grand Paradise and lists the Lucky sedes
(Tunja · La Calera · Chiquinquirá).
