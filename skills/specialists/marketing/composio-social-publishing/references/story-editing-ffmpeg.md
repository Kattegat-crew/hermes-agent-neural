# Editing raw event video into an IG Story (ffmpeg)

Verified 03/09/2026: a raw phone clip from a client casino event (bingo hall) → on-brand 9:16 IG Story.

## Source reality
- Event clips come in as smartphone video, already **portrait ~9:16** but **low-res** (e.g. `478x850`, `30fps`, `56s`, `aac` audio) and dark.
- Confirm first: `ffprobe -v error -select_streams v:0 -show_entries stream=width,height,r_frame_rate -of default=noprint_wrappers=1 <file>` and `-select_streams a:0 ...` for audio.

## Goal
1080x1920 vertical with a campaign cartela (title + prize + CTA) over the raw footage, respecting IG safe zones.

## ffmpeg recipe (worked)
```bash
ffmpeg -y -i SRC -vf \
"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,eq=contrast=1.05:brightness=0.02,\
drawbox=x=0:y=0:w=1080:h=300:color=black@0.35:t=fill,\
drawtext=fontfile=FONT_SANS:textfile=$T/eyebrow.txt:fontcolor=0xDDC316:fontsize=54:x=(w-text_w)/2:y=70,\
drawtext=fontfile=FONT_SERIF:textfile=$T/title.txt:fontcolor=white:fontsize=96:x=(w-text_w)/2:y=150:shadowcolor=black:shadowx=3:shadowy=3,\
drawbox=x=90:y=1450:w=900:h=170:color=0xAB0F15@0.92:t=fill,\
drawbox=x=90:y=1450:w=900:h=170:color=0xDDC316@1:t=4,\
drawtext=fontfile=FONT_SERIF:textfile=$T/prize.txt:fontcolor=white:fontsize=58:x=(w-text_w)/2:y=1472:shadowcolor=black:shadowx=2:shadowy=2,\
drawtext=fontfile=FONT_SANS:textfile=$T/sub.txt:fontcolor=0xDDC316:fontsize=34:x=(w-text_w)/2:y=1560,\
drawtext=fontfile=FONT_SANS:textfile=$T/cta.txt:fontcolor=white:fontsize=46:x=(w-text_w)/2:y=1665:shadowcolor=black:shadowx=2:shadowy=2,\
drawtext=fontfile=FONT_SANS:textfile=$T/hashtag.txt:fontcolor=0xDDC316:fontsize=32:x=(w-text_w)/2:y=1748" \
-c:v libx264 -preset medium -crf 22 -pix_fmt yuv420p -c:a copy OUT
```
- Fonts (DejaVu aboard): `/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf` (headline), `DejaVuSans-Bold.ttf` (body/CTA).
- **escape-proof text**: put each overlay string in its own textfile (`textfile=`) rather than inline — avoids shell escaping hell with `¡`, `$`, `#`, emoji. Layout a helper `printf 'BINGO MILLONARIO' > $T/title.txt` per string.
- Keep `-c:a copy` to preserve ambient audio of the event.

## IG safe zones (1092x1920 canvas)
- **Top ~0-300px**: IG covers this with your handle / muted / etc. Put the small eyebrow + campaign title in `y=70..260` (title around y=150).
- **Bottom ~1200-1620**: IG covers the bottom ~250px with the reply/CTA bar, so keep the WHOLE low block higher than you'd guess. Working placement: prize cartela `y≈1240`, CTA `y≈1450`, hashtags `y≈1550`. Hashtags at `y≈1748` get covered by the UI. Same rule via the PIL-overlay path below.
- Keep the action centre of frame clear of text.

## Quality / perf notes
- Upscaling `478→1080` softens; the crop + `eq` lift is acceptable for a story but don't promise crispness. If the clip matters, ask for a higher-res source.
- **Verify before publishing**: extract a frame (`ffmpeg -ss 8 -i OUT -frames:v 1 /tmp/chk.png`) and review with vision_analyze (legibility, nothing cut, safe zones). A 56s clip is long — offer to trim to a ~25s highlight for a punchier story.

## Premium path: PIL overlay layers + ffmpeg `overlay` (stylized, user-preferred)

Plain `drawtext` looks functional. Jonathan asked for "textos más bonitos, estilizados" — the better method renders each element as a **transparent PNG with PIL** and composites with the `overlay` filter. Gives a gold-gradient serif headline, shadowed/glowing text, a rounded red+gold cartela, and the brand logo overlaid small on the right.

1. **Generate overlay layers with PIL** (fonts `/usr/share/fonts/truetype/dejavu/`): transparent RGBA PNGs — eyebrow, title (gold vertical gradient: render text to a mask, build a per-row gradient, paste through the mask, add a blurred black drop-shadow), cartela (rounded rect red + gold border + prize + subtitle), CTA, hashtags. Reuse the brand LOGO; for Paradise use the transparent seal `.../logo-paradise-transparent.png` at ~170px tall.
2. **Compose with ffmpeg `overlay`** — each image is a SEPARATE `-i` input and must be labeled:
```bash
ffmpeg -y -i SRC -i LOGO.png -i ov_eyebrow.png -i ov_title.png -i ov_cartela.png -i ov_cta.png -i ov_hashtag.png \
 -filter_complex "\
 [0:v]trim=start=30:end=50,setpts=PTS-STARTPTS,scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,eq=contrast=1.04:brightness=0.02,setsar=1[v];\
 [1:v]scale=-1:170[l];[2:v]scale=760:-1[e];[3:v]scale=1000:-1[t];[5:v]scale=980:-1[c];[6:v]scale=980:-1[h];\
 [v][l]overlay=x=876:y=310[o1];[o1][e]overlay=x=(W-w)/2:y=90[o2];[o2][t]overlay=x=(W-w)/2:y=170[o3];\
 [o3][4:v]overlay=x=(W-w)/2:y=1240[o4];[o4][c]overlay=x=(W-w)/2:y=1450[o5];[o5][h]overlay=x=(W-w)/2:y=1550[o]\" \
 -map "[o]" -map 0:a? -c:v libx264 -preset medium -crf 22 -pix_fmt yuv420p -c:a copy -t 20 OUT
```
- **Scale to fit before overlaying**: an overlay PNG wider than the canvas (title 1233px, hashtags 1121px) gets clipped at the edges — `scale=1000:-1` (or ≤ canvas width) first. Center with `x=(W-w)/2`.
- **`overlay` needs every image as its own labeled `-i` input**; referencing an unlabelled image fails with `Cannot find a matching stream for unlabeled input pad overlay`. Video `[0:v]`, logo `[1:v]`, then `[2:v]`..`[6:v]` for the text PNGs.
- **Logo placement (user pref)**: keep it small and on the RIGHT side — scale `-1:170`, overlay `x≈876, y≈310`.
- **Trim to a punchy ~20s** highlight (Jonathan's preference) instead of the full ~56s clip; pick the climax with a contact sheet (`ffmpeg ... fps=1/7,tile=4x2`) reviewed via vision_analyze.
- Always extract a frame and `vision_analyze` before publishing: confirm nothing is clipped and the low block clears the UI.

## Cleaning a phone screen-recorder clip (MixCam dual recorder) — verified 11/09/2026

Raw clips arrive as recordings of the phone's own screen: an app watermark and a picture-in-picture window sit on
the LEFT edge, so no rectangle crop that keeps the full height can drop them. Recipe that worked (src `576x1024`
portrait, watermark bottom-left at x≈10-105, PiP top-left at x≈0-210):

```bash
# crop out the left column, then rebuild 1080x1920 with lanczos + mild unsharp to fight the 3x upscale
ffmpeg -y -i SRC -vf "crop=356:633:220:195,scale=1080:1920:flags=lanczos,unsharp=5:5:0.6:5:5:0.0,setsar=1,\
eq=contrast=1.06:brightness=0.03,<drawtext overlay>" -c:v libx264 -preset veryfast -crf 21 -pix_fmt yuv420p -c:a copy OUT
```
- Measure the intrusive regions first with `vision_analyze` on a frame (ask for pixel bounding boxes of the
  watermark and the PiP), then crop left of the widest one: `x_start = max(x_right)+10`, `w = W - x_start`,
  `h = round(w / 0.5625)`, `y = (H - h)/2`.
- The crop removes ~38% of the width → upscale is ~3x: soft but acceptable for a story; add `unsharp` and never
  promise crispness. Ask the user **before** publishing: publish-as-is (watermark visible) vs cropped (tighter
  framing, softer) — Jonathan chose the crop ("para que nos parezca capcut").
- Verify the watermark is gone in the *published* artifact, not only in your local render: fetch the story's
  `thumbnail_url` from `INSTAGRAM_GET_IG_MEDIA` and inspect it.

## Landscape (horizontal) clip → 9:16 story: blurred fill, not black bars

For a `1024x576` (or any horizontal) source, IG would letterbox it with black bars. Better: blurred duplicate as
background + the full frame centred (verified 11/09/2026 on a 38s clip).

```bash
ffmpeg -y -i SRC -filter_complex "\
[0:v]split=2[bg][fg];\
[bg]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,scale=180:320,boxblur=6:1,eq=brightness=-0.06,scale=1080:1920[bgb];\
[fg]scale=1080:-2[fgs];\
[bgb][fgs]overlay=(W-w)/2:(H-h)/2[vb];[vb]<drawtext overlay>[out]" \
-map "[out]" -c:v libx264 -preset veryfast -crf 21 -pix_fmt yuv420p -movflags +faststart OUT
```
- **Blur at low resolution** (`scale=180:320,boxblur=6:1`) and upscale afterwards. Blurring the native 1080x1920
  canvas times out (60s+ for a 38s clip); the low-res trick finishes in seconds and looks the same.
- Story videos via the API allow **3s to 60s**, so a 38s clip publishes fine without trimming.
- The burned-in text lands on the blurred bottom band → excellent contrast; keep `y≈1450-1470`.

## Text size for burned-in story captions

"No muy grande" for `BINGO! FELICITACIONES!` on a 1080-wide canvas = **fontsize 58** (810px wide, 25% side
margin). At 70 it is 977px wide (10% margin) — too big. Measure before rendering:
`ImageFont.truetype(DejaVuSans-Bold, size).getbbox(text)` in PIL. Gold `0xDDC316` + `borderw=3:bordercolor=black`
reads well over both the pale floor and the yellow counter. Keep the text as the user typed it (no "¡" added)
unless they ask.

## Brand palettes
- **Golden Game**: `#DDC316` gold, `#AB0F15` red, `#1A1A1A` bg, `#F5F5F5` text.
- **Lucky/Paradise**: `#8E1026` red, `#C9A227` gold, `#F5EFE0` ivory, `#121A15` midnight, `#0E6B3A` green. Swap hex + logo accordingly.

## Confirm brand before editing
Ask which client/account the story targets (Golden vs Paradise) before overlaying; the cartela hex and logo must match — don't publish a Golden-branded story to Paradise (or vice versa).
