---
name: reel-performance-analytics
description: "Use when scoring published reels against platform metrics."
tags: [reels, analitica, metricas, instagram, composio, rendimiento, performance]
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [reels, analytics, metrics, composio, instagram, facebook, performance]
    category: creative
---

# Reel Performance Analytics

Close the loop on reel production: measure the **final published reel** against **real platform
metrics** (views / reach / likes / comments / saves / shares) so editing and scripting decisions are
driven by data, not taste. Complements the generation pipeline (video-ai-generator, reel-pipeline,
scene-consistency-qa) — those produce/QA; this measures how they landed.

Reference file: `references/composio-insights-and-metrics.md` — exact tool slugs, required fields,
verified constraints and the end-to-end pipeline.

## When to Use

- After publishing reels (IG / FB) for a campaign, to see which clips/guiones actually performed.
- The user asks to "analizar el rendimiento de los reels" or wants statistics across a batch.
- Iterating a campaign and needing to know whether an edit (rhythm, CTA timing, music) moved the
  number — the delta is only visible with a prior baseline.

## Core idea: units and labels

The unit of analysis is the **final published reel** (the mp4 master, with music/cartela/palette) —
NOT the raw AI clips. The thing being predicted is the **platform metric** (views, engagement). This
turns it into a regression problem: `rendimiento = f(características del reel)`.

## One-off measurement vs. a real dataset

- With **1 reel** there is no correlation — only a snapshot.
- You need **n ≥ 10 reels** before per-feature regression means anything.
- So the first concrete step is always **pallet a base dataset** of what is already published
  (features + real performance), then compare new reels against that internal benchmark.
- Do NOT adopt someone else's target ranges (e.g. a competitor's notes on rhythm/BPM). Calibrate
  your own from your own reels; format and audience differ.

## What to measure

**Reel features (our side, on the final mp4)**
- ffprobe: duration, fps, resolution.
- ffmpeg scene/cut detection: number of cuts, mean/median take length.
- ffmpeg `ebur128`: integrated LUFS, true peak.
- scipy (FFT): energy per band (bass/mid/treble), estimated BPM of the music.
- faster-whisper (word_timestamps=True): words/sec, seconds of silence, the exact second each beat
  lands (incl. CTA), repeated phrases. The venv pattern lives in video-ai-generator `fit_voice.py`.
- CTA timing via regex on the aligned transcript: `(like|guardar|comenta|sigue|déjanos|...)` → the
  second the call-to-action happens. **A reel/section with no CTA or a late CTA is a flag** — it is
  often the weakest performer, and this check surfaces it instantly.

**Platform performance (Composio)**
- IG: `INSTAGRAM_GET_IG_MEDIA_INSIGHTS` (views/reach/likes/comments/saves/shares).
- FB: `FACEBOOK_GET_POST_INSIGHTS` (only `post_media_view` still valid).
- Full slugs/fields/constraints in `references/composio-insights-and-metrics.md`.

## Pipeline (final reel → platform score)

1. Register `reel → {platform → media_id}` when publishing (or recover it via caption/timestamp
   using `INSTAGRAM_GET_IG_USER_MEDIA` on IG and `FACEBOOK_GET_PAGE_POSTS` on FB).
2. Extract the reel features from the final mp4.
3. Pull the platform performance via Composio.
4. Cross + normalize: `views / followers` (or per-day) so a recently-posted reel isn't unfairly
   penalized; prefer comparing against a sibling reel over an absolute number.
5. Emit a per-campaign report: a row per reel with features + `views/likes/comments` + a verdict
   (✓ ok / ✗ weak: slow, no CTA). The reel with highest views = the target structure to replicate.

## Key pitfall — identify the numeric IG id

`ig_user_id` for the metrics/list tools is the **numeric IG Business id**, NOT the Instagram
username and NOT the `ig_user_id` used at publish time to create the container. Passing the wrong
numeric id returns Graph error `code 100` ("Object ... does not exist / does not support this
operation"). Omit `ig_user_id` on `INSTAGRAM_GET_IG_USER_MEDIA` to target the currently authenticated
account.

## Related

- `scene-consistency-qa` — QA the scene stills before paying for image-to-video (the generation-side
gate).
- `reel-voice-lipsync` / `monid-seedance-clips` — production-side voice/lip sync.
- `composio-social-publishing` (user-owned) — publishing; this skill is the read-back/analytics
complement. Overlap with `composio-cli` / `composio-integrations` exists (all Composio); the curator
may consolidate.
