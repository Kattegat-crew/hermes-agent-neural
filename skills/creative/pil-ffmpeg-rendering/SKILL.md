---
name: pil-ffmpeg-rendering
description: >-
  Use when creating video clips with PIL + ffmpeg. Use when creating video clips with PIL + ffmpeg. hermes: tags: [video, animation, ffmpeg, PIL, numpy, rendering, motion, keying]
tags: [video, ffmpeg, pil, animacion, rendering, mp4, motion]
version: 1.0.0
author: hermes
license: MIT
metadata: {}
---

# PIL + ffmpeg Animation Rendering

Produces real MP4 clips (1280x720 or 1920x1080, 30-60 fps) for animation concepts,
logo intros and landing-page motion previews. Preferred over describing ideas when
the user asks for clips ("haz clips", "muéstrame las opciones").

## Workflow

1. **Brand check first.** Read the brand (logo file, palette, tagline) and view the
   logo image before designing — animations must use brand colors and real assets.
2. **Reuse a scaffold** (see `templates/render_scaffold.py`): `encode()` pipes RGB
   frames to ffmpeg; helpers for easing, vertical gradients, glow text, particles.
   One scene function per concept: `scene(t) -> PIL Image`.
3. **Use real logo assets** when available (PNG with alpha from the client Drive).
   For logo intros, extract components (e.g. crown) from the logo itself and animate
   the pull-back: focus detail -> full lockup.
4. **QC every clip** with programmatic pixel stats + extracted frames (see QC below)
   BEFORE delivering. Never deliver unverified renders.
5. **Deliver** individual MP4s plus a concatenated comparison video with title cards
   (concat demuxer: same resolution/fps/pix_fmt required).

## CRITICAL Pitfalls

- **`-pix_fmt` must match bytes-per-pixel.** `img.convert("RGB").tobytes()` is 3
  bytes/px -> ffmpeg must read `-pix_fmt rgb24`. Using `rgba` (4 bytes/px) silently
  produces a garbled, gray/desaturated video with colors shifted (looks "broken",
  not an error). RGBA frames -> `-pix_fmt rgba`.
- **Timeline units: pass real seconds.** The scene function receives `t = i / FPS`
  (0..duration), NOT a normalized 0..1 value. Mixing normalized time with
  second-based conditions silently truncates animations (text never completes,
  final elements never appear). Pick one unit and be consistent.
- **ffmpeg `select` comma escaping.** In a Python subprocess arg, the filter comma
  must be escaped: `["-vf", "select=eq(n\\,75)"]` (the actual arg is
  `select=eq(n\,75)`). Unescaped comma is parsed as a filter separator.
- **Frame index ≠ seconds.** `select=eq(n,75)` picks decoded frame 75 = t=75/FPS.
  To inspect a scene moment at time T use `n = int(T * FPS)`.
- **One extraction per command.** Multiple `-ss` / `-frames:v` with several outputs
  in one ffmpeg invocation misbehaves; run one `-ss T -frames:v 1 out.png` each.
- **Terminal guard vs numpy `&`.** Shell commands containing `&` (e.g. numpy boolean
  `(a>0) & (b>0)`) get flagged as backgrounding. Write analysis scripts to files and
  run them, instead of inline heredocs with `&`.

## QC (do this every time)

1. **Programmatic pixel stats first.** Count color classes (e.g. red/gold/green
   pixels, `bright = sum(axis=2) > 300`), bounding boxes of bright regions, dominant
   colors per region. Verify the elements you expect (text red pixels present, chips
   gold pixels, wave green pixels).
2. **Extract frames at several timeline moments** (focus, assembly, shimmer, final)
   and verify each composition.
3. **Vision model is a secondary check only.** Fallback vision models hallucinate on
   dark/low-contrast renders (claimed non-existent "8 crowns", "scanlines", "gray
   rectangle"). Trust pixel statistics over the vision description; use vision to
   confirm legibility/composition after stats pass.

## Logo/badge component extraction (keying)

To pull a component (crown, icon) out of a badge with a white interior:

- Crop the region generously, then key with numpy:
  - neutral white bg: `(max(r,g,b)-min(r,g,b) < 14) * (min > 230)`
  - strong red (ring/text): `(r>120) * (g<100) * (g-b<40)` — the `g-b<40` guard
    protects dark gold, which has g-b>40
  - pink AA halos (red-on-white antialiasing): `(r>170) * (abs(g-b)<25) * (b>110)`
    — bright gold highlights have g-b>25 so they survive
- Set masked pixels alpha=0, then feather: GaussianBlur(1.5) on the alpha channel.
- Trim with `getbbox()`.
- Verify: composite over a dark background and count remaining red/white pixels;
  iterate the key rules if artifacts remain (red arcs, rosy lines are visible at
  720p+).

## Comparison video

Generate title cards (dark bg, gold frame, number + name + one-line description),
encode each card as its own short segment with the SAME encoder settings, then
`ffmpeg -f concat -safe 0 -i list.txt -c copy out.mp4`. All segments must share
resolution/fps/pix_fmt or concat fails.

## Support files

- `templates/render_scaffold.py` — copy-and-modify scaffold: encode(), easing,
  gradients, glow text, particles, poker chip, crown, wheel, wave.
- `references/paradise-logo-animation.md` — Paradise Club logo geometry, crown
  extraction coordinates and the "Corona Dorada" timeline used in the client work.
