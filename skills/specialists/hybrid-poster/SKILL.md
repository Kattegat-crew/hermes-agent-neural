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

## Execution Steps

1. Write the prompt with RESULT, REFERENCES (identity plate, logo placement-only), IDENTITY, LAYOUT, STYLE, EXACT TEXT, QR SLOT, CONSTRAINTS, OUTPUT.
2. Generate under `spend-gate` (one authorized run, native print ratio, best supported quality).
3. Post-production: OCR against the verbatim list, visual identity check vs plate, logo restore, real QR paste, manifest with model, params, request id, hashes, cost, QC.
4. Mark `draft_internal_review`. Never claim print-ready: resolution, ICC, bleed, and substrate belong to the print master step.

## Output Contract

Return: poster PNG path, dimensions, hash, request id, cost, OCR result per line, identity/logo/QR verdicts, and flagged defects for human review.

## References

- `references/hybrid-poster-prompt.md` — prompt block template and post-production checklist.
