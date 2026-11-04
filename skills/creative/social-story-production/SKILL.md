---
name: social-story-production
description: "Use when turning a raw chat video into an IG/FB story."
tags: [instagram, stories, video, ffmpeg, historias, publicacion]
version: 1.0.0
author: Ragnar
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [instagram, stories, video, ffmpeg, vision, publishing, client-brand]
    related_skills: [composio-social-publishing, pil-ffmpeg-rendering, reel-pipeline]
---

# Social Story Production (footage → IG/FB story)

Class of task: the client/user drops one or more raw videos in chat and asks to publish them as
**stories** for a specific brand with a specific text overlay ("publica estos vídeos en las historias de
golden con un texto que diga X, centrado, no muy grande, abajo"). The video usually comes from a phone at
a casino event: low-res, sometimes a screen recording, sometimes landscape, audio or silent.

Publishing mechanics (Composio CLI, tool slugs, hosting, Cloudflare cache-bust, account ids) live in the
`composio-social-publishing` skill (user-owned). This skill covers the production half: **see the footage,
adapt the canvas, burn the text, prove it to the user, then hand off to publish.**

Session detail with the exact verified numbers: `references/chat-video-to-story.md`.

## 1. Never guess what the video contains — look at it

Chat attachments land in `/opt/data/cache/documents/vid_*.mp4`. Re-sends arrive as duplicate files with the
same byte size and a different name: dedupe by size/hash, publish each asset once.

`ffprobe` gives geometry, duration and whether an audio stream exists. Then extract a **timestamped contact
sheet** and read it with `vision_analyze` — that is the evidence, and it doubles as the answer when the user
asks "¿por qué no puedes ver los videos?".

```bash
ffprobe -v error -show_entries format=duration,size:stream=codec_name,width,height,r_frame_rate \
  -of default=noprint_wrappers=1 SRC
# contact sheet, one cell every N seconds, timestamps burned in:
ffmpeg -v error -i SRC -vf "fps=1/4,scale=480:-1,drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:text='%{pts\\:hms}':fontcolor=yellow:fontsize=20:x=5:y=5,tile=2x5" -frames:v 1 /tmp/sheet.png -y
```

- `tile=R x C` must cover `duration/N` cells (38s at `fps=1/4` → 10 cells → `tile=2x5`).
- The burned timestamps let you name the exact second of the climax in your reply ("la tómbola sale en 0:20–0:28").
- The same sheet exposes source-quality defects at a glance: recorder watermarks, PiP windows, watermarked apps.
- One vision call per video is enough to brief the user; individual frames are for legibility/safe-zone checks.
- `-c:a copy` only when the probe showed an audio stream; a silent source needs no audio mapping.

## 2. Canvas: get to 1080x1920 before overlaying anything

- Source ≈9:16 (e.g. 576x1024) → `scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1`.
- Source 16:9 → never crop to 9:16 (it destroys the frame). Blur-letterbox: blurred zoomed copy fills the
  canvas, real video centered over it. Exact command in the reference.
- **Do the blur at low resolution** (`scale=180:320,boxblur=6:1` then scale back). Blurring the full 1080x1920
  canvas over a 38s clip blew a 60s timeout; the downscale→blur→upscale pass finished in ~2 min.
- Use `-preset veryfast` for clips longer than ~20s and pass an explicit generous `timeout=` on the call.
- Meta story video spec: **60s max, 3s min** — do NOT trim a 38s clip for the API's sake. Trimming to a ~20s
  highlight is a style preference of Jonathan's, not a platform limit.

## 3. Text overlay: literal, burned in, measured, bottom-centre

- The Instagram API has **no text sticker field**. Any text must already be in the pixels before the container
  is created.
- Keep the string **exactly as the user typed it** — no auto-added opening `¡`, no "corrections".
- Put each string in its own textfile and use `textfile=` (`printf 'BINGO! FELICITACIONES!' > /tmp/txt.txt`) —
  avoids shell escaping with `!`, `¡`, `$`, `#`.
- **Measure before picking a size** instead of eyeballing fontsize:
  `python3 -c "from PIL import ImageFont; ft=ImageFont.truetype(FONT,58); bb=ft.getbbox(S); print(bb[2]-bb[0])"`.
  On a 1080-wide canvas a 22-char bold uppercase string measures 754px at 54, **810px at 58 (25% margin = the
  user's "no muy grande")**, 865px at 62, 977px at 70 (edge-to-edge = too big).
- Golden brand text that survives a light floor: `fontcolor=0xDDC316:borderw=3:bordercolor=black@0.9`.
- Placement for a single line "abajo": `y=1470` → base ≈1550, i.e. **~370–450px above the bottom edge**,
  clear of the ~250px IG UI zone while still reading as bottom-of-screen. Text at `y≈1748` gets covered.

## 4. Show the artifact, then ask exactly one question

```bash
ffmpeg -v error -y -ss <climax_second> -i OUT.mp4 -frames:v 1 /tmp/preview_<slug>.png
```
Send one preview PNG per asset in the chat (`MEDIA:/path`) with a 2-line summary of what each video contains,
and ask about the ONE material doubt (e.g. recorder watermark). Jonathan approves the artifact, not the plan —
publishing to a client account without showing the edited piece first is the failure to avoid.

## 5. Source-quality flags to raise before publishing to a client brand

- **Screen-recorder artifacts** (e.g. `MixCam: Dual Video Recorder`): a watermark plus a PiP window.
  After a full-canvas scale the recorder watermark tends to fall inside the story's bottom ~250px IG-UI zone
  and is hidden by the app anyway; the **PiP is the real problem** (upper-left, fully visible).
- **Zoom-crop is a proposal, not a default**: cropping clears watermark + PiP but costs a big upscale from a
  small region (e.g. `crop=361:642:215:191` on a 576x1024 source ≈ 3x upscale from 361px → visibly soft).
  State the tradeoff and let the user choose.
- Verify blur/band claims with pixel math, not with vision: vision described recognizable shapes inside a
  heavily blurred band. Mean |horizontal gradient| per band settles it (blurred ≈0.9 vs sharp ≈1.7–4.4 at 1080 wide).

## 6. Hand off to publishing

Upload the finished MP4 to the public host, verify the URL returns 200 with a cache-buster query
(`?v=<epoch>`) before handing it to Meta, then create the story container (`media_type: STORIES`, `video_url`)
and publish it. Tool slugs, account ids and the Cloudflare pitfall are in `composio-social-publishing`.

## 7. Pace (this user)

Media work takes minutes and Jonathan pings "Hey" / "Estás?" when the chat goes quiet. Keep the ffmpeg chain
at the minimum number of passes, and make the reply **lead with what is already ready** (previews attached,
sizes/positions stated) instead of narrating the plan. If a pipeline needs more than one pass, do not spend
that time silently.

## Support files

- `references/chat-video-to-story.md` — the verified 11/09/2026 case: both clips, probe output, the landscape
  blur-letterbox command, watermark/PiP coordinates, gradient measurements and the ffmpeg timings observed.
