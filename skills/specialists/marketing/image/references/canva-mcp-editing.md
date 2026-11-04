# Canva MCP editing — verified workflow

Verified 2026-11 on the connected account via the Canva MCP tools.

## What works

| Step | Tool | Notes |
|---|---|---|
| 1. Create base design | `create_design` / `generate_design` | 1920x1080 works for TV banners. Costs AI credit quota. |
| 2. Swap background art | `update_item` with `update_fill` | Inject our own rendered art as the fill of the background element. |
| 3. Replace texts | `update_item` with `replace_text` | Accents and ñ survive: `miércoles`, `PREGUNTA EN TAQUILLA`, `$1.000.000`. |
| 4. Commit | `commit_editing_transaction` | Required, or edits are discarded. |
| 5. Export | `export_design` | PNG/PDF export returns a CDN URL. |
| 6. Duplicate | `copy_design` | Does NOT burn AI credits. |

## Hard limits

- The API CANNOT create new text elements — it can only replace text in and reformat existing elements. Any text the base design lacks must be baked into the background art or added in a new base design.
- No brand templates in the account by default (`get_brand_templates` empty) → the "one base design + duplicate + swap" pattern replaces templates.
- Every `create_design` / AI generation action consumes Canva AI credit quota (~7% used by one design + a few ops during testing).

## Production pattern (cheap, repeatable)

1. Build ONE base design per brand with all needed text slots (kicker, headline, ribbon, amount, dates, CTA, venue, legal bar).
2. Verify the text slots by reading the design (`get_design`).
3. For each variant: `copy_design` → `update_fill` with that venue's art → `replace_text` with that venue's copy → `commit_editing_transaction` → `export_design`.
4. Download each export and run the same QA as local renders (safe zones, text overflow, legal bar legibility).

## Interop with local composer

The local PIL composer (see chroma-cutout-compositing.md) replicates Canva typography. Decision rule: if the client needs editable Canva files, produce variants via copy+swap; if the client needs PNGs only, the local composer is faster and free of Canva credits.
