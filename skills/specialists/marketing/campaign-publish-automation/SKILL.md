---
name: campaign-publish-automation
description: "Use when automating campaign publishing with approval."
tags: [campanas, publicacion, instagram, facebook, composio, cron, aprobacion]
version: 1.0.0
author: Ragnar (curator)
license: MIT
platforms: [linux]
metadata:
  hermes:
    category: marketing
    tags: [campaigns, publishing, instagram, facebook, composio, drive, cron, approval-gate]
    related_skills: [composio-social-publishing, content-performance-analytics, social-media-content-calendar, cron-watchdog-scripts]
---

# Campaign Publish Automation (calendario → aprobación → publicación → métricas)

End-to-end pattern for automating a marketing content calendar where **a human owns approval and scripts own
execution**. Built and verified in production 08/09/2026 for the NeuralCrew bingo-sep2026 campaign (Golden Game +
Lucky Brothers, IG+FB), in repo `marketing-campaign-generator/planning/calendario-sep2026/`. Complements the
how-to-publish skill `composio-social-publishing` and the how-to-measure skill `content-performance-analytics`.

## Architecture: three surfaces, one source of truth

1. **JSONL in the git repo = truth.** One row per piece: `id, brand, type, asset_drive_id, cover_drive_id, copy,
   hashtags_ig/fb, canales, slot (ISO), estado, aprobacion, media_ids, portal_url`. Diffable, auditable, consumable
   by scripts. Never let the calendar live only in a spreadsheet or in chat memory.
2. **XLSX generated from JSONL → Drive campaign folder = human review surface.** Hyperlinks per row to the piece
   (portal/Drive). The admin edits copy/hashtags/estado **there** ("yo edito la tabla, tú actualizas los otros
   lados"). Re-upload must **replace in place (same Drive file ID)** so existing links never break.
3. **Sync script XLSX(Drive)→JSONL** downloads the latest XLSX, diffs cell-by-cell, propagates human edits,
   commits. Run it on EVERY publisher tick, not just the morning package — an approval written at 9 AM must make
   the 11 AM slot.

## State machine (the safety core)

`listo_para_aprobacion` → human OK (chat "Dale <id>" or Estado cell = `Aprobado` in the XLSX) → `aprobado` →
publisher cron fires at slot → `publicado` (+media_ids) → metrics harvest in following days. `a_producir` =
planned production gap.

**Hard rule: the publisher ONLY touches `aprobado` rows. Nothing external is ever posted without an explicit
human gate.** Add an anti-double-publish guard: a row that already carries `media_ids` gets flipped to `publicado`
without re-posting (covers "published but git commit failed").

## The cron trio (Hermes, validated)

| Cron | Schedule | Job |
|---|---|---|
| `calendario-paquete-diario` | 7:30 AM | sync XLSX→JSONL + today's pieces + pending approvals + recent metrics → WhatsApp package. Agent formats the script's structured stdout; "Nada pendiente hoy" is a valid reply |
| `calendario-publicacion-horaria` | every hour | publish ONLY `aprobado` rows inside slot ±2h window; register media_ids; regenerate XLSX+dashboards; git commit/push; announce successes. Stdout = only human-actionable lines (`✔ PUBLICADO id: IG=… FB=…`); JSON detail to stderr; silent return when nothing due |
| `calendario-metricas-diario` | 6:00 AM (no_agent) | harvest IG+FB insights per brand account → posts.jsonl → dashboards |

Script-path guard note: `script` fields (CLI and `cronjob_manage`) only accept paths under HERMES_HOME/scripts.
Pattern: logic lives versioned in the repo; the scripts dir holds a 3-line wrapper `#!/bin/bash` + `exec python3
/ruta/repo/.../cron_x.py`. `chmod +x` it, and smoke-run `bash <wrapper>` in foreground **before** creating the job.

## Publishing mechanics (what each type needs, verified live)

- **Assets need a public URL Meta can fetch** (IG strictly): host on the portal's SSO-exempt asset path (e.g.
  `reels.neuralcrewlabs.com/assets/<mes>/`), verify with curl before use. Beware Cloudflare caching a 404 on fresh
  uploads → cache-buster `?v=<epoch>`.
- **IG**: two-step — create media container (REELS/STORIES/CAROUSEL; single image: omit media_type) then publish.
  Reels: `cover_url` + `share_to_feed` so it also lands on the grid. Stories: only via IG — **FB has no stories
  publishing API; don't fake it, label the channel difference in the calendar.**
- **FB**: `FACEBOOK_CREATE_VIDEO_POST` / `FACEBOOK_CREATE_PHOTO_POST` / `FACEBOOK_CREATE_MULTI_PHOTO_POST`
  (carousel = array of photo_url). **Local file upload 413s on ~100MB+ videos → use `file_url` pointing at the
  same public portal URL.**
- **Carousels IG**: create child containers in order, then parent `CAROUSEL` with `children` ids.
- **Multiple brands = one Composio connection each**: resolve account IDs once via Composio tooling and store them
  in the publish script (per-brand dict), not in chat memory.

## Metrics harvest gotchas (each cost a debugging cycle)

- IG insights parameter is **`ig_media_id`** — `media_id` returns a validation error.
- Requesting a single deprecated metric name (`replies`, `follows`, `link_clicks`, `reels_skip_rate`) **fails the
  entire insights call** — request only the currently-valid list: `views, reach, likes, comments, saved, shares,
  total_interactions`.
- Insights work below 1,000 followers (verified on small brand accounts) — the docs' limit is statistical, not a
  hard API gate.
- Scripts calling the Composio CLI from the cron environment may need `COMPOSIO=$(which composio)` exported —
  hardcoded container paths break across host/container boundaries.

## Cadence design lessons (content side)

- Fixed weekly template beats ad-hoc planning: Lunes reel 11:00 · Martes–Domingo story 12:00 M (1/día, en orden
  de historia) · Jueves post estático 11:00 · Viernes story temática del día ancla 17:00 · Sábado carrusel 11:00.
- **Stories live 24h, not 12h** — at 1/day exactly one is ever live; don't double-publish to "show two".
- The anchor day of the promotion (viernes de bingo) gets the themed story; teaser reels land 2–3 days before it.
- Inventory existing assets BEFORE planning production — week 1 can be 100% covered at zero production cost if a
  Drive inventory (taxonomized Reels/Posts/Stories/Carruseles) exists. Build it with drive IDs; they become the
  `asset_drive_id` column.

## Asset integrity: truncated PNGs and the silent-rescue trap (verified 25-oct-2026)

- **Validate PNG integrity BEFORE any publish**, not just `Image.open()`: a truncated PNG (missing IEND chunk) opens fine with `PIL.ImageFile.LOAD_TRUNCATED_IMAGES = True` and only the actually-downloaded rows contain pixels — Meta renders the missing bottom as **solid black** on the live story. Check for IEND: `b'IEND' in open(path,'rb').read()` (fast, definitive) or decode with strict mode and compare content height vs. canvas height.
- **Never make a converter "rescue" a corrupt asset.** A validation shield added to the image pipeline (write_pdf→png step) that fills missing area instead of crashing converts a visible build error into a silent PUBLIC error — the worst failure mode (client sees the broken story live). Shield must **fail loudly**, not repair.
- If a broken story is already live: it **cannot be deleted via API** (Meta has no story-delete endpoint) — the admin must remove it manually in the app. Correct remediation is: repair asset → republish (`publish.py --id X --force`) → update the JSONL row's `media_ids` to the NEW id and note the superseded one as "ELIMINAR A MANO" → new `registry.register()` entry → commit/push. Distinguish clearly from a **republicación editable** (feed posts) where API delete/edit IS possible.
- **Repair recipe for a truncated story image** (validated with vision, publishable): (1) pixel-stretch the last intact row per column to fill the missing band; (2) heavy Gaussian blur over the first ~220px of the stretch to fuse the seam; (3) scrim = dark gradient layer composited behind the closing text for contrast; (4) rebuild the footer with the sibling-piece pattern (tagline gold+white → divider → +18 legal → fade to black), centered, matching brand colors sampled from the image; (5) vision_analyze the result and iterate. If the original footer text was lost with the file, reconstruct from campaign language and FLAG it to the admin — never present invented copy as the original.
- **IG story safe zones**: keep all text/legal above ~250px from the bottom edge (UI "Enviar mensaje" bar covers it) and ideally below the top ~150px. Verify final PNG at 1080×1920; lucky-style assets delivered at other 9:16 sizes (e.g. 941×1672) need upscaling before publish.
- `get_drive`-style download helpers **cache by filename** when the local file exists and is >10KB — to feed a repaired file into the publish script, overwrite the cached copy in its output dir (`/tmp/publish-out/<piece-id>/asset.png`); the script will pick up the repair with no code change. For the canonical copy in Drive, replace in place with `files().update(fileId=…, media_body=…)` (same file ID, links preserved).
- **Manual `--force` publishing skips the cron's bookkeeping.** After any out-of-window/manual publish, replicate the hourly cron's full chain yourself: register in content-intel registry (`registry.register` with calendario_id), set row estado/nota/media_ids in the JSONL, regenerate + re-upload XLSX to all Drive copies, git commit/push — otherwise the piece is live on IG but invisible to the calendar, dashboards, and anti-double-publish guard.
- When repo `.git/objects` shows `root:root` ownership (root-tick artifact of the Desktop backend), `git push` fails for the agent user — fix via SSH as root: `chown -R <agent>:<agent> .git/objects`.

## Failure handling

Publisher errors exit with the error text in stdout → chat notification, and the row stays `aprobado` (not
consumed), so the next hourly tick retries automatically. Use generous script timeouts: ≥560s for harvest /
≥400s for publishing (large video uploads).

## Verification checklist before trusting the automation

- [ ] dry-run mode publishes nothing but prints the plan; ran on a live row.
- [ ] Foreground smoke of every cron wrapper done (publish-due silent when nothing due).
- [ ] Anti-double guard exercised (row with media_ids never re-posts).
- [ ] `cronjob_manage list`: all jobs `scheduled`, next_run_at populated, correct deliver targets.
- [ ] First real package + first real publish verified by reading back the live feeds.

## References

- `references/bingo-sep2026-runbook.md` — concrete run: file layout, account/connection IDs, cron job IDs, exact
  Composio tool slugs and payload fields, XLSX column set, and the error transcripts that drove each fix.
