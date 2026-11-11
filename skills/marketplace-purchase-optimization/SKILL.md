---
name: marketplace-purchase-optimization
description: Use when Plon asks to optimize AliExpress cart discounts.
---

# Marketplace Purchase Optimization (AliExpress & similar)

## When to Use

- Plon asks to review/optimize his AliExpress cart, pick what to keep/drop, or maximize the discount before checkout.
- Plon asks for promo codes, coupon-ladder math, or whether an item is worth adding (storage, cases, accessories).
- Scope is personal purchases on marketplaces (AliExpress primarily, MercadoLibre secondarily) — not agency procurement.

Optimize the cart for maximum real discount, with verified data per item. Respond in Spanish, concise, with per-item verdicts.

## Always-on rules

- **Never complete checkout or click pay/continue.** The user pays; you only prepare and report. Ending the audit means leaving the cart selection state clean and reporting the total.
- **Never apply a manual promo code over a bigger automatic discount.** AliExpress auto-applies its best cart coupon; typing a code REPLACES it. Compare first: report which is larger and why the auto one wins.
- **Respect the user's spend cap** (ask once if not stated). Report the projected total against it before finishing.
- **Convert coupon minimums at the coupon's own rate (~3500 COP/USD), not the checkout rate.** Minimum-spend thresholds are computed on the COP-converted eligible subtotal, which is why a cart that looks eligible still gets rejected.

## Procedure

1. **Read the cart live.** Open the user's cart tab via CDP (`Target.getTargets` → cart tab). Extract every item: id (from `a[href*="/item/"]`), price, variant, shipping, checkbox state. Do not trust earlier screenshots — prices change.
2. **Measure the coupon ladder with real toggles.** Toggle item checkboxes one at a time and read the cart panel totals (Subtotal / Descuentos extra / Envío / Estimación total / item count on the continue button) before/after. Theoretical ladder math does NOT match what the panel shows — AliExpress mixes auto coupons, store discounts and new-buyer discounts per item. Only toggled totals are truth.
3. **Cross-check every kept item against its listing page** in a second tab (`Page.navigate` to `/item/<id>.html`): listing price vs cart price, rating, review count, sold count. Record all four. Close the second tab at the end.
4. **Audit item by item:**
   - Cart price > listing price → variant mismatch; flag it and tell the user which SKU to select (see references/aliexpress-mechanics.md).
   - Shipping cost on a cheap item (e.g. a poster costing more to ship than to buy) → remove unless the user needs it.
   - Duplicate/overlapping products → keep the cheaper one with comparable review backing (e.g. one cable pack vs another); state the savings.
   - High spend + near-zero review count on the listing → surface the risk explicitly; the store's total sales matter more than the single listing's.
5. **Search alternatives only for flagged items** (user-named ones first, e.g. 'find me a pretty Spider-Man case'): read the first ~12 search cards via DOM, pick the shortlist, open each candidate's listing, and compare price/rating/sold. Recommend one winner with numbers, not a list.
6. **Report:** items kept/removed and why, per-item review verdict, total (subtotal − coupons + shipping), spend cap headroom, and any pending decisions (variant fixes, storage upgrades). No raw logs — Telegram formatting, labeled lines.

## Pitfalls

- **Wait for lazy-rendered search results before scraping** (~9s or poll until `[class*="search-item-card"]` exists); card text is the reliable source, item ids sometimes empty — fall back to innerText.
- **Do arithmetic in execute_code/terminal, never mentally** — totals compound (subtotal, coupon COP conversion, shipping, per-item discounts) and a wrong mental sum misleads the user's buy decision.

## References

- `references/aliexpress-mechanics.md` — coupon types, price quirks, fake-capacity red flags.
