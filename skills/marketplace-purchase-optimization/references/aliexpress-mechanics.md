# AliExpress Mechanics (distilled)

## Coupon ladder
- Global 11.11 codes are denominated in USD and applied to Colombian carts as COP at a fixed internal rate (~3500 COP/USD), higher than the checkout conversion rate. Compute minimum-spend gaps in COP using that rate.
- The cart auto-applies its best coupon on the 'Descuentos extra' line. A manually typed code replaces it, it does not stack — always compare before suggesting one.
- 'Nuevo comprador' discounts are per-item, large, one-time, and appear on the listing ('Ahorra $X · Nuevo comprador'). They change effective item price drastically and independently of cart coupons.
- Store/bundle offers ('≥ 2 unidades' tiered price, 'Compra 2 y obtén -1%') apply per listing, not cart-wide.

## Price quirks
- Cart price can exceed the listing price for the same item: variant selected in cart differs from the listing's default SKU, or the listing's flash price expired. Open the listing, read its default price and selected SKU, and tell the user exactly which variant to pick before checkout.
- Listing pages show rating / review count / sold count near the title; search cards show the same in condensed text. Review count on a NEW listing can be near zero even for a reputable store — judge trust by the store's cumulative sales shown under the title too.

## Red flags
- Storage (microSD/USB/SSD) priced far below market (e.g. 1TB at a few USD) = fake capacity. Do not add to cart; offer a real-brand alternative (SanDisk/Samsung EVO) in the user's price range.
- Accessories with 'compatible' branding from unknown makers: check review count before recommending as a gift-quality item.

## Cart scraping
- Cart rows: `.cart-product`; identify items by innerText match, toggle via the row's `input[type=checkbox]`, wait ~2.5s after each toggle for panel totals to update.
- Totals regexes over `document.body.innerText`: `Subtotal\n$X`, `Descuentos extra`, `Envío`, `Estimación total`, and `Continuar (N)` for the selected count.
