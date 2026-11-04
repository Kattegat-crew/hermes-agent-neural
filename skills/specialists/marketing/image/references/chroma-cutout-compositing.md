# Chroma-cutout compositing — preserve the original photo

Problem it solves: AI image models erase real-world signage/logos from photos of physical locations, even with corrected prompts (verified twice). The deterministic fix is to never let the model touch the photo.

## Pipeline

1. **Chroma plate** — generate ONLY the overlay element (mascot, character) alone, full body, on flat pure magenta `#FF00FF`: no gradient, no floor, no shadow on the background, generous margin on all four sides, crisp silhouette. Attach the character's identity references + styling references. Prompt must ban text in the ELEMENT only, never globally.
2. **Cutout (PIL)** — alpha from Euclidean distance to the key color: 0 below tolerance T, 255 above 1.7T, linear ramp between; extra suppression for pixels that are low-green and high red/blue (magenta residue); Gaussian-blur the matte ~2px for feathering; crop to alpha bbox.
3. **Base** — original photo untouched. Landscape ≥16:9: center cover-crop to 1920x1080. Portrait: blurred darkened fill (scale to width, GaussianBlur ~34, brightness 0.62) + sharp photo aspect-fit right-aligned, so facades stay visible next to the text column.
4. **Composite** — paste cutout at ~0.76–0.86 of canvas height, bottom-right (or side opposite the text column), with a blurred contact shadow (alpha * 0.55, GaussianBlur ~18) and ~90px clearance above any bottom legal bar.
5. **Typography** — translucent rounded panel (deep brand color, alpha ~0.68, blur 22) behind the text block; kicker, bevel-gradient headline, ribbon, amount bar, data lines, pill CTA, venue line, full-width legal bar with 18+ badge. Fit-to-width sizing with a floor so no line overflows.

## Deterministic QA

- Diff the composed output vs the original photo in the signage region: near-zero mean difference = signage survived (the AI pipeline could never pass this).
- Measure text block geometry in the DOM/canvas at final width — never trust thumbnails for typos; OCR at full resolution only.
- Vision QA is helpful but intermittent — always pair it with geometric checks that work without it.

## Working implementation

`compose_v6.py`/`compose_v7.py` + `driver_cutout.py` pattern (as used for the 2026-11 Aguinaldo TV banners, Golden Game / Grand Paradise): spec-driven JSON (`compose_spec.json`), per-brand palettes, chroma driver retries on provider quota exhaustion and writes a log; keep retry loops out of the composer so renders stay pure functions of inputs.
