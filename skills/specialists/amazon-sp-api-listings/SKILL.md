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

Activate when the user needs to create, update, optimize, or debug listing details on **Amazon AU** via the Selling Partner API, when dealing with **FBA fees/labels** for an existing ASIN, when diagnosing **account status / store inactive / stranded inventory with "Please verify your account status"** (report-based API diagnosis + activation workflow in `references/account-status-diagnostics.md`), or when computing **unit economics / margins / launch pricing / fees for Amazon AU** (landed cost, Products Fees API, finance Sheet + sales watcher in `references/unit-economics-and-sales-watcher.md`). Reusable for snuffle mats or any PET_TOY-style product.

## Hard Rules

- **Do not change the brand.** The catalog brand is `Generic`. Using any other value returns error 5995 and blocks the update. Sets `BRAND = "Generic"` in payloads.
- **No promotional claims** in description/bullets ("tires more than a walk", "% money-back guarantee"): error 99300. Use factual, descriptive copy.
- **Do not send generic `language_tag: "en"`** on attributes: error 90244. Only `unit_count.type` uses it, with `en_US`.
- **`mode=PREVIEW` returns 400**, but **`mode=VALIDATION_PREVIEW` works on PATCH** (verified: HTTP 200, `status: VALID`, `issues: []`, publishes nothing). Always dry-run a PATCH batch here before the real send.
- **A 200 + `ACCEPTED` is not publication evidence.** Read the listing back and compare attribute by attribute; a PATCH is partial and Amazon's image pipeline can revert a set minutes after it briefly appears complete.
- **GST (AU) is not optional for a non-resident holding stock in Australia**: registration is mandatory from day 1 — the AUD 75,000 threshold applies only to local businesses. `amazon.com.au` prices are GST-inclusive (1/11 of every sale is tax, not revenue), and a registered seller reclaims the ~10% GST charged on Amazon fees. Model margins net of GST and state this explicitly before proposing launch prices.
- Use exact enum values: weight `kilograms` (lowercase), unit count type `Count` (capitalized).
- Custom lookup for per-SKU keyword: separate `target_audience_keyword` per SKU; `generic_keyword` shared.
- **`productType` differs per SKU — never assume.** Read `summaries[0].productType` from `GET /listings/2021-08-01/items/{sellerId}?marketplaceIds=...` first. Real case: PS-3095 is `PET_PLACEMAT` while PS-3052/PS-3058 are `PET_TOY`; patching with the wrong one is accepted but doesn't apply.
- **Price changes via Listings Items do NOT move the live price.** `PATCH /attributes/purchasable_offer` (whole-attribute replace only — nested paths like `/attributes/purchasable_offer/0/our_price/0/schedule/0/value_with_tax` return `InvalidInput: Invalid path`) returns `200 ACCEPTED, issues: []` and the attribute reads back correct, yet the offer book keeps the old price. The legacy `POST_PRODUCT_PRICING_DATA` feed returns **403 — the app lacks the *Product Listing* role**. Verify price with `GET /products/pricing/v0/competitivePrice` (CompetitivePriceId `1`), never with the listing attribute. Escalation: add the Product Listing role in Developer Central, or set the price once in Seller Central.
- **Duplicated offers are a red flag for stuck prices**: `getListingOffers` returning 2 offers from the same seller means a stale mirror offer can keep serving the old price.
- **Amazon has no webhooks.** The Notifications API only pushes to **Amazon SQS or EventBridge**, never to an arbitrary HTTP URL. "Webhook" for Amazon events means SQS (ORDER_CHANGE, LISTINGS_ITEM_STATUS_CHANGE) or 5-minute polling — never promise an HTTP callback.

## Decision Gates

| Situation | Action |
|---|---|
| Brand change requested | Reject; keep `Generic`; route via file upload |
| Product description rejected 99300 | Rewrite factual; no warrants/claims |
| FBA fee looks too high (e.g. $90+) | Check item_package_<b>dims/weight</b> corrupt in catalog; re-PUT correct folded dims |
| Dimensions/tier reload | Catalog vs FBA system are async; wait 24-48h |
| Need to add/update one field | Use PATCH (requires productType in body) |
| Price PATCH accepted but live price stale | Confirmed SP-API limitation, not a bug in the payload: offer book separate from listing attribute; needs *Product Listing* role for the price feed or a Seller Central edit |
| User asks for "a webhook instead of a cron" for Amazon events | Explain SQS/EventBridge are the only push channels; offer 5-min polling as the immediate option |
| User asks how to register / comply with AU GST (ABN, ARBN, BAS) | Step-by-step non-resident pathway in `references/au-gst-registration-non-resident.md`: ABN via ABR (no ARBN needed), standard GST, BAS agent, then ABN in Seller Central to stop the 10% GST on fees |
| Full create/update | Use PUT (replaces all attributes) |
| Gallery images submitted via PATCH/PUT get ACCEPTED with 0 issues but never persist (or fluctuate: 5 imgs -> 1 img minutes later) | Normal: Listings Items API is not reliable for image sets. Use a JSON_LISTINGS_FEED feed with PATCH messages per SKU (recipe in `references/image-gallery-uploads.md`); poll the feed to DONE, then poll listings — Amazon's image pipeline is async and can take 15+ min per feed |

## Execution steps

1. Read config from `/opt/data/amazon-spapi-setup/.env` (client_id, client_secret, refresh_token, seller_id).
2. Get product type schema with `sp_api_client.py defs PET_TOY` and validate payload fields.
3. Generate/validate payloads: `python3 listing_fields.py --product-type PET_TOY --validate`.
4. If adding only a few attributes, use PATCH with `productType` in body. For full update use PUT.
5. Optionally check `catalog` API to confirm dims/weights propagated; catalog and FBA inventory are async.
6. Images CAN be automated end-to-end via JSON_LISTINGS_FEED (host files publicly, e.g. Cloudflare Pages, and reference by URL in `media_location`). Manual Seller Central tasks reduce to FBA shipping/labels. Never judge a gallery by a single listings read: read state after the feed is DONE and re-check 10-15 min later (pipeline fluctuates mid-processing).
7. **Closing ritual before telling the user anything**: (a) `GET` each SKU and count `*_image_locator` keys (expect 5, with the new `media_location` on the main), (b) confirm the corrected title/bullets, (c) confirm `BUYABLE` + `DISCOVERABLE`, (d) repeat the read 4-5 min later and require the same result. Only then hand over `https://www.amazon.com.au/dp/{ASIN}`.

## Output Contract

Return:
- HTTP status + `issues` array for each submitted SKU (`ACCEPTED` + 0 issues = success).
- Any catalog lookup values (dims, weight, price) for record.
- Note which SKUs are in `Standard` vs `Oversize` FBA tier if FBA label/fee was the goal.

## References

- `references/payload_format.md` — exact validated enum/schema values for PET_TOY (Count, kilograms, browse node, required fields).
- `references/image-gallery-uploads.md` — working JSON_LISTINGS_FEED recipe for image galleries: feed document upload (presigned URL), feed creation, gzip report parsing, monitor script, image attribute keys.
- `references/published-run-2026-11-03.md` — ejecución real completa (3 ASIN, copy v2 + galería): comandos, tiempos de estabilización, evidencia final y trampas encontradas.
- `references/account-status-diagnostics.md` — API diagnosis of stranded/inactive store (report types, NoBuyableOffers check, getAccount 404 quirk, SIV/activation forum findings).
- `/root/Digital Expresions/README.md` — project state, products, gotchas.
- `references/unit-economics-and-sales-watcher.md` — landed cost / margin / break-even model, Products Fees API recipe, finance Sheet hub (locale + cell-reference pitfalls), idempotent sales/refund watcher (Orders + Finances → Sheet Finanzas + Discord `📦・amazon-au`), and the silent Hermes cron registration (`no_agent` + `deliver='local'` + script under `/opt/hermes-agent-data/scripts/`).
- `references/au-gst-registration-non-resident.md` — AU GST compliance for a non-resident FBA seller: ABN without ARBN, why standard GST (not simplified) applies with stock in Australia, BAS agent requirement, ABN → Seller Central, costs and the ASIC/ARBN grey zone.
- `/opt/data/amazon-spapi-setup/` — live Python pipeline (auth, client, payloads, upload). PROD creds live in Vaultwarden (`vw get "Terceros/Amazon SP-API - NeuralCrew"`), AU endpoint is `sellingpartnerapi-fe.amazon.com`.