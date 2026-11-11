---
name: amazon-ads-operations
description: Use when operating Amazon Seller Central or Amazon Ads.
version: 1.0.0
author: ragnar
license: internal
metadata:
  hermes:
    tags: [amazon, ads, seller-central, sponsored-products, ppc, ecommerce]
    related_skills: []
---

# Amazon Ads & Seller Central Operations

## When to Use

- Creating, editing, or monitoring Sponsored Products campaigns in Amazon Ads console (any marketplace).
- Debugging SP-API or Ads API access (403 with valid LWA token, app registration, redirect URIs).
- Checking live listing/ASIN state (price, Buy Box, indexation) for the Digital Expressions Amazon AU store.

Domain knowledge for the Digital Expressions Amazon AU store (snuffle mats, 3 ASINs) and any future Amazon marketplace work. Covers console UI automation, API auth boundaries, and campaign launch workflow.

## API auth boundaries (verified 07-nov-2026)

- An SP-API app registered as **self-authorization (no redirect URI) CANNOT be used for the Amazon Ads API**. Ads requires an LWA app with a registered redirect URI and a separate OAuth grant from the ad account.
- SP-API role grants can silently lose scope: LWA token stays valid (token endpoint returns 200) while Listings/FBA endpoints return **403**. Verify role scope, not just token validity, when a previously working integration starts failing.
- Credentials for the store live in `/opt/data/.env` (SP-API) on the runtime host; vault item holds the same SP-API set only.
- Amazon AU blocks plain `curl` on public ASIN pages; use the browser for live listing checks.

## Campaign Manager UI automation (browser_exec recipe)

Verified working end-to-end launching a Sponsored Products manual campaign (07-nov-2026). Gotchas in the React SPA:

- **Wrong `entityId` → widgets hang on "Loading" forever** (no errors in console, no data requests). The ad account has multiple entities (e.g. legacy US `ENTITY24CTELJR8JE53` vs AU). Take the `entityId` from the row of the target campaign in the all-campaigns table, not from the merchant URL param.
- **`document.body.innerText` misses rendered widget content.** Use `capture_screenshot()` + `vision_analyze()` to read metrics tables (clicks, CPC, spend, impressions) — this found data innerText claimed was absent.
- If the SPA hangs, **open a fresh tab and navigate again** — first navigation per tab renders; reloads of the same SPA instance often stay stuck.
- React inputs/textareas ignore naive `value=` writes. Always: `element.focus(); document.execCommand('selectAll'); document.execCommand('insertText', false, text)`. This fires the change events React needs (used for keyword list paste, campaign name, budget).
- Bulk keywords: use the **"Enter list"** tab next to "Suggested" — one keyword per line in the textarea.
- Keywords with **no suggested bid are inelegible** and get dropped with an informational banner — they never enter the table. Filter them out rather than debugging the paste.
- The bid input that appears when clearing a group-level error (`kwp:kwp-bid-input-field`) sets the **ad group default bid**, not a keyword bid. Leave it only if the default you want.
- Budget forecast widget only appears when the daily budget is **≥ $20**; below that the forecast section stays empty.

## New Seller Incentives (AU) — credit mechanics (verified 07-nov, official page sell.amazon.com.au/grow/nsi)

- **Credits are spend-match, NOT free money.** Gasta A$75 → A$75 credit; gasta A$300 → A$300; gasta A$1.500 → A$1.500. Effectively 2x ad value, but cash is spent first.
- **Qualifying spend window: 30 days from campaign LAUNCH** (not from listing). Credits appear ≤14 business days after completing a tier, and **EXPIRE 30 days after being granted** — they must be spent fast.
- **Where to check:** Ads console → left nav **Billing → Promotions** (`/ads-bg/promotion?entityId=...`): shows "No active promotions" / Offer progress / Redeemed / promo-code box. Credits auto-apply to statements BEFORE charging the default payment method. The offer itself is viewed/accepted in **Seller Central → ≡ Menu → Benefits** (requires Seller Central login — session may not exist in the shared browser even when the Ads console does).
- **Escalón strategy:** at ~A$20/day the A$75 and A$300 tiers are captured with normal spend; going for the A$1.500 tier means A$50/day sustained — only chase it if CVR is proven, since the earned credits expire.
- **Other NSI credits:** A$150 Partnered Carrier (first FBA shipment via PCP within 90 days of first buyable ASIN) and A$300 Amazon SEND — check how the supplier shipped; the credit may be owed without claiming.
- **Brand Registry AU accepts PENDING IP Australia trademarks** (registered OR pending — verified via Seller Central forums + sell.amazon.com FAQ). No trademark → no Vine, no A+, no 5% referral credit. The unlock is ~1h online filing (~A$250-400/class), not months — do not repeat the "camello" assumption.
- Reviews without Brand Registry: "Request a Review" button per order (100% compliant).

## Launch workflow (tested pattern)

1. Read existing campaign metrics first (all-campaigns table + screenshot) before creating anything.
2. Manual campaign structure used: core keyword set (broad/phrase/exact), negative phrase list blocking adjacent product categories (e.g. dog bed, pee pad, yoga mat), dynamic bids **down only** for launch-phase spend control, ~A$15/day, no end date.
3. Collect Amazon's suggested per-keyword bids at creation — they are real market data (AU snuffle-mat core terms: A$0.75-0.94 in nov-2026, cheaper than expected).
4. After `Launch campaign`, verify on the resulting summary page (URL contains `campaign=<ID>&publicCampaign=...`): it echoes name, budget, bidding strategy, keyword count. "Can take up to one hour to process" before impressions.

## Store baseline (for continuity)

- 3 ASINs live in Amazon AU, Buy Box ours, prices A$39.99/44.99/36.99; 0 organic visibility (not in top ~70 results for "snuffle mat for dogs") — paid traffic is the launch lever. New-seller incentives + sponsored-products credits fund initial spend.
- Weekly loop: check spend/ACOS in console → at ~2 weeks, mine Search Term Reports → promote converters to Exact campaigns, negate losers.
