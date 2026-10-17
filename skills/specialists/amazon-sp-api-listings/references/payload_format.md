# Payload Format — PET_TOY validated against SP-API (2021-08-01)

Valores exactos que AMAZON ACEPTA (verificados con status ACCEPTED, 0 issues, sesión 2026-08-20).

## Requeridos del schema LISTING

- `brand` → `Generic` (NUNCA "Digital Expressions" → error 5995)
- `item_name`, `bullet_point`, `product_description`, `country_of_origin`
- `supplier_declared_dg_hz_regulation` → `[{"value": "not_applicable"}]`

## Valores/enums correctos

| Campo | Formato correcto |
|---|---|
| `unit_count` | `[{"value":1,"type":{"value":"Count","language_tag":"en_US"}}]` |
| `item_weight` / `item_package_weight` | `[{"value":0.35,"unit":"kilograms"}]` (minúscula) |
| `list_price` | `[{"currency":"AUD","value_with_tax":34.99}]` |
| `recommended_browse_nodes` | `[{"value":"5848192051"}]` (numérico) |
| `batteries_required` / `contains_liquid_contents` | `[{"value":false}]` |
| `power_plug_type` | `[{"value":"no_plug"}]` |
| `accepted_voltage_frequency` | `[{"value":"100v_240v_50hz_60hz"}]` |
| `item_length_width_height` | `[{"length":{"value":80,"unit":"centimeters"},...}]` |
| `merchant_suggested_asin` | el ASIN existente del SKU |

## Gotchas (causan errores)

| Error | Causa | Fix |
|---|---|---|
| 5995 | Cambio de brand | Usar `Generic` |
| 99300 | Claims promocionales en descripción | Texto factual, sin garantías/comparaciones |
| 90244 | `language_tag:"en"` en atributo | Quitar; solo unit_count usa en_US |
| 400 InvalidInput | `mode=PREVIEW` | No mandar; PUT normal valida |
| 90220 required missing | Faltan required | Incluir list_price, unit_count, model, browse node |
| Fee FBA altísima | Catálogo con peso/dims corruptos (66kg, 60×50×40) | Re-PUT/PATCH dims plegadas + peso real |

## Endpoint / credenciales

- Endpoint AU (Far East): `https://sellingpartnerapi-fe.amazon.com`
- Marketplace ID: `A39IBJ37TRP1C6`
- Auth: LWA client_id + client_secret + refresh_token (NO AWS SigV4/IAM)
- ProductType: `PET_TOY`

## Catálogo vs FBA — asincronía

- Listings Items (PUT/PATCH) responde ACCEPTED en segundos.
- Catalog API (`/catalog/2022-04-01/items/{ASIN}`) y FBA inventory storage type propagan de forma asíncrona (minutos a 24-48h para reclasificación de fee/tier).
- Para fee FBA: el tier lo decide el **sistema FBA**, no el catálogo. Oversize puede persistir 24-48h tras corregir dims.

## Dims plegadas correctas (FBA standard, ≤45cm)

| SKU | Package (L×W×H) | Weight |
|---|---|---|
| PS-3058 | 45×35×8 cm | 0.35 kg |
| PS-3052 | 45×30×6 cm | 0.30 kg |
| PS-3095 | 40×25×5 cm | 0.25 kg |