---
name: amazon-sp-api-listings
description: "Trigger: Amazon SP-API, seller central, listing Amazon AU, snuffle mat, FBA fee, create/update Amazon listing, seller partner API, populate Amazon product. Publica y optimiza listings de Amazon AU vía Listings Items API con payloads validados contra el schema real de PET_TOY."
license: Apache-2.0
metadata:
  author: "digital-expressions"
  version: "1.0"
---

# Amazon SP-API Listings

## Activation Contract

Activate when the user needs to create, update, optimize, or debug listing details on **Amazon AU** via the Selling Partner API, or when dealing with **FBA fees/labels** for an existing ASIN. Reusable for snuffle mats or any PET_TOY-style product.

## Hard Rules

- **Do not change the brand.** The catalog brand is `Generic`. Using any other value returns error 5995 and blocks the update. Sets `BRAND = "Generic"` in payloads.
- **No promotional claims** in description/bullets ("tires more than a walk", "% money-back guarantee"): error 99300. Use factual, descriptive copy.
- **Do not send generic `language_tag: "en"`** on attributes: error 90244. Only `unit_count.type` uses it, with `en_US`.
- **No `mode=PREVIEW`** query param: returns 400 on API 2021-08-01. A normal PUT validates and publishes together (0 issues = live).
- Use exact enum values: weight `kilograms` (lowercase), unit count type `Count` (capitalized).
- Custom lookup for per-SKU keyword: separate `target_audience_keyword` per SKU; `generic_keyword` shared.

## Decision Gates

| Situation | Action |
|---|---|
| Brand change requested | Reject; keep `Generic`; route via file upload |
| Product description rejected 99300 | Rewrite factual; no warrants/claims |
| FBA fee looks too high (e.g. $90+) | Check item_package_<b>dims/weight</b> corrupt in catalog; re-PUT correct folded dims |
| Dimensions/tier reload | Catalog vs FBA system are async; wait 24-48h |
| Need to add/update one field | Use PATCH (requires productType in body) |
| Full create/update | Use PUT (replaces all attributes) |

## Execution steps

1. Read config from `/opt/data/amazon-spapi-setup/.env` (client_id, client_secret, refresh_token, seller_id).
2. Get product type schema with `sp_api_client.py defs PET_TOY` and validate payload fields.
3. Generate/validate payloads: `python3 listing_fields.py --product-type PET_TOY --validate`.
4. If adding only a few attributes, use PATCH with `productType` in body. For full update use PUT.
5. Optionally check `catalog` API to confirm dims/weights propagated; catalog and FBA inventory are async.
6. Manual tasks go to Seller Central (images, FBA shipping/labels).

## Output Contract

Return:
- HTTP status + `issues` array for each submitted SKU (`ACCEPTED` + 0 issues = success).
- Any catalog lookup values (dims, weight, price) for record.
- Note which SKUs are in `Standard` vs `Oversize` FBA tier if FBA label/fee was the goal.

## References

- `references/payload_format.md` — exact validated enum/schema values for PET_TOY (Count, kilograms, browse node, required fields).
- `/root/Digital Expresions/README.md` — project state, products, gotchas.
- `/opt/data/amazon-spapi-setup/` — live Python pipeline (auth, client, payloads, upload).