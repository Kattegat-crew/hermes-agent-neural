---
name: print-asset
description: "Trigger: boleta, volante, flyer, imprenta, print layout, SVG a PDF, QR reusable. Build vector print pieces with real measurements and production-safe art."
license: Apache-2.0
metadata:
  author: "neuralcrew"
  version: "1.0"
---

# Print Asset

## Activation Contract

Load this skill for physical print pieces (tickets, flyers, stubs). All text is real vector text; the image model is never used for copy.

## Hard Rules

- Build layouts in SVG with physical units (mm) matching the approved size; export PDF for print plus PNG previews for review.
- Keep production notes (safe zones, specs, internal labels) OUT of printable art; they live in the manifest and previews only.
- Embed brand assets only from real repository files; record their hashes. Never redraw logos or QR matrices.
- Generate QR codes from a pinned library version into versioned SVG+PNG assets with documented URL, error correction, and quiet zone.
- NEVER invent legal, privacy, or authorization copy: use only approved text, mark pending fields explicitly.

## Decision Gates

| Situation | Action |
|---|---|
| Missing tool (cairosvg, reportlab) | Deliver SVG + PNG and record the exact gap; install nothing without pinned version plus human approval |
| Slot/cut/substrate unknown | Use the standard proposed size, flag provider validation as blocking for the final master |
| Numbering or personalization | Placeholder in art (`Nº ______`); consecutive numbering applied by the print shop |

## Execution Steps

1. Confirm size, sides, fonts (pinned system fonts), colors, and copy sources with their approval status.
2. Compose front and back with safe margins, fold/cut marks, and writable light areas for hand-filled fields.
3. Export print PDF at final size, PNG previews, and a manifest with dimensions, fonts, hashes, method, cost 0.00, and QC.
4. Verify visually: exact spelling, no production marks in art, occlusion, contrast, safe zone.

## Output Contract

Return: SVG/PDF/PNG paths, verified physical dimensions, hashes, QC results, and the pending list blocking the final print master.

## References

- `references/print-asset-checklist.md` — pre-press checklist and manifest fields.
