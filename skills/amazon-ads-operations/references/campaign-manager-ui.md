# Verified selectors & snippets — Amazon Ads Campaign Manager (AU console)

All verified live 07-nov-2026 via browser_exec (local browser, user session).

## Locating the real campaign

- All-campaigns table renders row metrics only with correct `entityId` in URL. Wrong entity → all metric widgets stuck on "Loading", zero console errors, zero data XHRs. Extract `entityId` from the campaign row link.
- Campaign detail URL shape: `/cb/sp/summary?campaign=<CAMPAIGN_ID>&publicCampaign=<NUM>&entityId=<ENTITY_ID>`.
- Legacy campaigns from other marketplaces (US 2023) may sit in the same merchant account — check country before reading metrics.

## Reliable text injection (React-controlled fields)

```js
el.focus();
document.execCommand('selectAll');
document.execCommand('insertText', false, value);
```

Applies to: campaign name, ad group name, daily budget, keyword bulk textarea ("Enter list" tab). Plain `el.value = ...` leaves React state stale and the value disappears on the next render.

## Keyword bulk add

- Tab path: Keywords section → "Enter list" → textarea (placeholder: "Enter keywords separated by a new line.") → Add keywords.
- One keyword per line. Inelegible ones (no suggested bid) are silently excluded from the table; only an info banner reports the count.
- After add, table rows carry pre-filled suggested bids. Use a per-row bid override only for strategy outliers; otherwise accept suggestions (real market data).
- "Apply all" control copies the top suggested bid to every row — avoid when row-level suggestions differ meaningfully.

## Negative keywords

- Section header "Negative keyword targeting" contains an inner `expand` button — expand it; tabs "Negative exact" / "Negative phrase"; same textarea recipe; its own "Add keywords" button (the second one on the page — target by last matching button).
- Phrase match is the safer default for category-blocking (blocks any query containing the term).

## Reading metrics that innerText hides

`document.body.innerText` returned no impressions/ACOS columns even though fully rendered. Workflow that worked:

1. `capture_screenshot()`
2. `vision_analyze(path, question)` asking for the specific columns
3. For columns off-screen: scroll the table container, screenshot again.

## Buttons & state checks

- `Launch campaign` is a plain bottom-of-page button (`button` with exact innerText match).
- Success: redirect to summary page with banner "Congratulations, your campaign has launched successfully" + "up to one hour to process". Summary page lists every setting — read it back as verification before reporting success.
- `aria-expanded` scan (`[aria-expanded]` filtered by `offsetParent`) is a quick way to find collapsed optional sections (negative keywords, bid adjustments).
