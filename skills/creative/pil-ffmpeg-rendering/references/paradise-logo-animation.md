# Paradise Club — "Corona Dorada" logo animation (client work, 2026-08)

Session-specific detail for the entry animation developed for Paradise Club
Casinos (Lucky Brothers SAS / The Grand Paradise Club). Reuse as a worked example.

## Brand assets

- Real logo PNG: `/opt/data/brain/raw/lucky_brothers/Logo_2026.png` (1290x1102 RGBA)
  - Circular badge: white interior, thick red ring, gold crown top, red script
    "The Grand Paradise", green palms on the P/e strokes, gold "CLUB", red
    "DIVERSIÓN Y SUERTE" curved along the bottom. Transparent OUTSIDE the circle.
  - `Logo_2026_blanco.png` — white/light variant (same badge).
  - `logo_paradise.jpg` — same badge, JPEG no alpha.
  - LOGOS.pdf — image-only, no extractable text (pypdf returns empty).
- Drive folder "Paradise Club Casinos Website" only holds a Leads spreadsheet;
  brand assets live in brain raw storage.

## Crown extraction (worked example of the keying in SKILL.md)

- Crown tight region inside the 1290x1102 badge: x 470-830, y 150-470.
  (The red ring top arc occupies y < ~150 — cropping from y=150 removes it.)
- Keying rules used (numpy, RGBA int array):
  - neutral white bg: `(max-min < 14) * (min > 230)` -> alpha 0
  - strong red (ring/text): `(r>120) * (g<100) * (g-b<40)`
  - pink AA halos: `(r>170) * (abs(g-b)<25) * (b>110)`
- Feather alpha: GaussianBlur(1.5) on the alpha channel, then `getbbox()` trim.
- Result: ~351x320 keyed crown. Verify by compositing over dark bg — leftover
  artifacts appear as thin rosy/red lines at the crop edges; iterate rules.
- Pitfall found: dark gold gradient edges (e.g. 150,95,40) have g-b>40 and survive
  the red key; bright gold highlights (e.g. 245,214,110) have g-b>25 and survive
  the pink key. Both guards are load-bearing.

## Badge geometry for 1920x1080 output

- Badge displayed at 796x680, centered (960, 545). Badge top = 205.
- Crown inside badge (original bbox x470-830, y122-470 scaled):
  - CR_X = 562 + int(470/1290*796) = 852; CR_Y = 205 + int(122/1102*680) = 280
  - CR_W = int(360/1290*796) = 222; CR_H = int(348/1102*680) = 215
  - Crown center ~ (963, 387)
- Keep this alignment if re-rendering: the standalone crown must land exactly on
  the badge's own crown when the badge pops in (it is the same artwork).

## Final animation timeline (5.2s, 1920x1080 @ 60fps)

1. 0.0-0.9s  — dark luxury bg, radial gold glow builds, gold dust particles
2. 0.7-1.6s  — real crown appears large (scale 1.7->2.2, alpha ramps), slight
   entry rotation (max 6 deg, eases to 0)
3. 1.5-2.6s  — badge pops in with ease_out_back + drop shadow; standalone crown
   shrinks+fades 1.9-2.4s (fade via alpha-channel multiply, NOT a dark patch —
   a patch produced a visible gray rectangle over the logo); sparkle burst on
   landing (2.3-2.9s)
4. 2.6-3.4s  — gold shimmer: 3 diagonal parallelogram bands sweeping across
5. 3.0-5.2s  — rim-light pulse (blurred gold ring), breathing glow, settle

## Deliverables (in /opt/data/entregables/paradise_clips/)

- `Paradise_Corona_Dorada_v2_logo_real.mp4` — final single animation
- `Paradise_Opciones_Animacion_Entrada.mp4` — comparison of the 5 concepts
- `paradise_anim_{1..5}_*.mp4` — individual concept clips (older hand-drawn
  versions; user feedback: "demasiado básicas" -> the real-logo v2 was the fix)

## Recurring user preferences (animation work)

- Quality/depth of ONE developed idea > several basic options. Reference quality:
  "las que hiciste con Golden".
- Use the REAL brand logo components, not hand-drawn approximations.
- Deliver actual MP4 clips, not descriptions. Verify frame-by-frame before sending.
