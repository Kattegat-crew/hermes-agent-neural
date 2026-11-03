---
name: hybrid-poster
description: "Trigger: pendón, poster, cartel, banner impreso, gpt-image, baked text. Generate campaign posters with baked-in text plus deterministic restoration and QC."
license: Apache-2.0
metadata:
  author: "neuralcrew"
  version: "1.0"
---

# Hybrid Poster

## Activation Contract

Load this skill when generating a print poster with an image model. The model renders layout and display text; deterministic steps certify identity, logo, QR, and legal-critical copy.

## Hard Rules

- Order the model to render ONLY an explicit verbatim text list: exact spelling, accents, numbers, line breaks. Forbid paraphrase, extra copy, fake QR matrices, and invented URLs or amounts.
- NEVER deliver model output as final: always run post-production before showing it as approved.
- Restore the official logo 1:1 whenever the model drifts letterforms, proportions, or colors.
- NEVER let the model draw the QR: reserve an empty white square with quiet zone, then paste a real QR from a verified source file.
- Preserve the approved character identity against its reference plate (features, colors, costume); fix drift locally or re-run, never silently accept it.

## Decision Gates

| Situation | Action |
|---|---|
| Display headline vs dates/prize/legal | Model may bake display text; dates, amounts, and legal stay verified by OCR and corrected locally if wrong |
| Logo drifted | Replace 1:1 with the official asset, keep placement |
| Character anchor missed (model moved/reshaped it) | Adapt layout deterministically around measured geometry, or request a new authorized run |
| Exact-text line missing or misspelled | Local composite fix when cheap; new run only with fresh spend authorization |
| Whole palette off-balance (accent color flooding, protagonist colors weak — e.g. gold overwhelming red/green) | Do NOT re-roll from scratch: iterate on the output with a second pass ordered to 'keep layout, character and ALL text character-for-character; change ONLY the color balance'. Verified to converge in one refinement with gpt-image-2.5 while preserving typography and identity. |

## Execution Steps

1. Write the prompt with RESULT, REFERENCES (identity plate, logo placement-only), IDENTITY, LAYOUT, STYLE, EXACT TEXT, QR SLOT, CONSTRAINTS, OUTPUT.
2. Generate under `spend-gate` (one authorized run, native print ratio, best supported quality).
3. Post-production: OCR against the verbatim list, visual identity check vs plate, logo restore, real QR paste, manifest with model, params, request id, hashes, cost, QC.
4. Mark `draft_internal_review`. Never claim print-ready: resolution, ICC, bleed, and substrate belong to the print master step.

## Model Notes: gpt-image-2.5 (fal)

- Renders verbatim Spanish text — accents, dates and the legal line included — without typos, verified across consecutive runs. Bake ALL copy into the prompt (headline, dates, tagline, legal); the OCR verification pass stays mandatory, but local composite correction is usually unnecessary with this model.
- `image_size: portrait_4_3` returns 768×1024 (3:4), NOT 4:5. For a 1080×1350 feed post: resize to 1080 wide and crop 3% from the top and 3% from the bottom (centered vertical crop); verified no text clipping at those margins.
- `image_size: landscape_4_3` returns 1024×768 — native ratio for counter-print pieces: boletas de urna, tarjetas de sellos, cupones. 4:3 ≈ A6 apaisada (148×105 mm) casi sin recorte; verified for the Aguinaldo ticket set (front, back, stamp card).

## Reference order (edit endpoint)

The ORDER of `image_urls` drives identity: character turnaround plate FIRST, logo SECOND. With that order the mascot identity (features, costume, proportions) survives every run; verified across the ticket set. The identity plate must be the flat production turnaround, not a stylized hero render — hero renders reintroduce scene lighting and angle drift.

## Empty-form-fields pattern (fillable print pieces)

For boletas/cards the cashier fills in: order each field explicitly and terminate with a global ban — checkboxes described as 'two empty square checkboxes... completely empty (no checkmarks, X's or fills)', writing fields as outlined label + 'empty writing line'. Close the prompt with 'Render no other text, letters, numbers, watermarks or logos than the ones specified.' GPT-image-2.5 respects emptiness and the ban; verified both sides of the ticket in one run each. Printing the date under each checkbox (e.g. the 5 Wednesday draw dates on a stamp card) is a design pattern that physically prevents out-of-window stamping.

## Orthography-only correction pass

When OCR finds accent/typo defects in an otherwise-approved piece, do NOT re-roll and do NOT hand-composite: run a second edit pass over the SAME output ordered 'Fix ONLY X. Change nothing else: same layout, same colours, same fields, same ornaments, same typography and sizes', listing each correction verbatim. Verified to converge in one pass with zero collateral (CÉDULA and protección accents fixed, everything else pixel-stable). Needs its own spend-gate authorization like any run.

## Output Contract

Return: poster PNG path, dimensions, hash, request id, cost, OCR result per line, identity/logo/QR verdicts, and flagged defects for human review.

## References

- `references/hybrid-poster-prompt.md` — prompt block template and post-production checklist.
- `references/bendabal-approved-direction.md` — load for Bendabal flyers: user-approved final artwork, illustrated-band treatment, event-title hierarchy and reusable composition rules; includes the persistent visual reference.
