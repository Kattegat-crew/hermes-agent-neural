# Unit Economics Amazon AU + Sales Watcher (verified 2026-11-03)

Verified procedures for landed cost, fees, margin model and the sale/refund
notification stack. Numbers below are real (order QH20260812, 397 units).

## 1. Real fees via Products Fees API (not estimates)

```
POST /products/fees/v0/listings/{sku}/feesEstimate?MarketplaceId={MP}&IsAmazonFulfilled=true
body: {"FeesEstimateRequest": {"MarketplaceId": MP, "IsAmazonFulfilled": true,
       "Identifier": sku, "PriceToEstimateFees": {"ListingPrice": {"CurrencyCode": "AUD", "Amount": price}}}}
```

- Read `payload.FeesEstimateResult.FeesEstimate.FeeDetailList`; the FBA line has
  `FeeType == "FBAFees"` → `FinalFee.Amount`. Referral fee is NOT in the list —
  compute it (13% for PET_TOY / Pet Supplies AU) over the GST-inclusive price.
- Verified fees (ex-GST): PS-3052 AUD 9.81 / PS-3058 11.45 / PS-3095 8.88.

## 2. Margin model (amazon.com.au prices are GST-inclusive)

- `net = P / 1.10` (AU GST 10%; applies from day 1 for non-resident FBA sellers
  — no 75k threshold). Registration pathway (ABN without ARBN, standard GST, BAS
  agent, ABN → Seller Central) in `references/au-gst-registration-non-resident.md`.
  Until the ABN is registered Amazon also charges 10% GST on its own fees.
- `margin = P/1.10 − 0.13·P − FBA_fee − landed_aud`
- **Break-even price:** `P = (FBA_fee + landed) / ((1/1.10) − 0.13)` ≈ `(FBA+landed)/0.779`
- **Price for target margin t:** `P = (FBA_fee + landed) / (0.909 − 0.13 − t)`
- Landed cost allocation (shared freight/cards/payment-fee lines): allocate
  freight & payment fee by goods-value share, custom cards by unit share.
  Cross-check the total against the Alibaba receipt (cash actually paid).
- FX: Frankfurter `https://api.frankfurter.dev/v1/latest?base=USD&symbols=AUD`.
- Key insight from the real run: at launch prices the max affordable ACOS is
  ~5% or negative → current prices cannot fund advertising; price for ≥25%
  margin before enabling ads.

## 3. Finance Sheet (hub) — pitfalls that cost a rewrite

- Sheets live in Drive folder **Finanzas** (`1I63XZcFWF7OlbPw5C68kNh0DPtxtVaVb`);
  hub: *Digital Expressions — Finanzas (Amazon AU)*, id `1Vhzmc1DIJKgSslJqeLvWjZTChzGlrWSE4qL2Fz6v1Cw`.
  Tabs: Parámetros, Costos y landed, Precios y márgenes, Ventas,
  Devoluciones y gastos, Resumen. All money numbers live as formulas referencing
  the Parámetros tab (FX, referral %, GST %, freight, cards, alipay fee) —
  never hardcode a second time.
- **PITFALL — locale:** a spreadsheet with comma-decimal locale (es-CO etc.)
  rejects `USER_ENTERED` values/formulas written with `.` decimals → `#ERROR!`.
  Fix once: `batchUpdate {updateSpreadsheetProperties: {properties:{locale:"en_US"}}}`.
  Formulas always use `.` decimals regardless of display locale.
- **PITFALL — parameter cell references:** writing `Parámetros!$B$8` for freight
  when freight sat in `$B$9` silently allocated the WRONG amounts (cards↔freight
  swapped). After any batch write, read the tab back with
  `valueRenderOption="UNFORMATTED_VALUE"` and verify totals equal known cash
  (e.g. 3190.48) before declaring done.
- Text cells that start with `=` (like "= mercancía + flete") parse as formulas
  → `#ERROR!`. Don't start notes with `=`.

## 4. Sales/refund watcher (idempotent)

`/opt/hermes-agent-data/amazon-spapi-setup/amazon_au_watch.py` +
`build_finance_sheet.py` / `fix_finance_sheet.py`. Pattern:

1. Orders API `GET /orders/v0/orders?MarketplaceIds={MP}&CreatedAfter=<now-3d>`;
   per order `GET /orders/v0/orders/{id}/orderItems`.
2. **Write-once guarantee:** JSON ledger `watch_state.json` keyed
   `orderId|sku` PLUS a read of `Ventas!B2:B5000` (order ids) before appending —
   ledger alone is not enough if state is deleted.
3. Append to Ventas with per-SKU landed cost read from the Costos tab and fees
   from the Fees API; refund events from Finances API
   `RefundEventList` → Devoluciones tab + alert.
4. Notify Discord channel `📦・amazon-au` (`1567184806729486439`, guild
   `1493354289266167808`) via bot token helper `_discord_token`; silence when no
   news (no "all clear" spam).
5. **Hermes cron registration (verified: job `da90255388df`).** The watcher is a
   deterministic script, not an agent prompt: run it with
   `cronjob_manage(action='create', name='amazon-au-ventas', schedule='every 5m',
   script='amazon_au_watch.py', no_agent=true, deliver='local')`.
   - `script` resolves relative to `/opt/hermes-agent-data/scripts/` → copy the
     working file there (`cp …/amazon-spapi-setup/amazon_au_watch.py scripts/`);
     absolute paths also work.
   - `no_agent=true` delivers stdout verbatim; `deliver='local'` keeps that out of
     the chat, because the script already posts to Discord itself. Keep the script
     **silent when there is no news** (guard every `print` with `if DRY or nuevas:`)
     or every tick becomes a message.
   - Test the script standalone first and require empty stdout + exit 0.
6. Status at creation: dry-run verified (0 orders — account activated
   2026-11-03); first real sale still pending → treat cron output with a
   verification pass on first fire.
