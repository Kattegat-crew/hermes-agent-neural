# Ejecución verificada — 03-nov-2026 · Amazon AU

Seller `A2VHNMV7YZM9CX`, marketplace `A39IBJ37TRP1C6` (AU), product type `PET_TOY`.

| SKU | ASIN | Resultado |
|---|---|---|
| PS-3052 | B0HFVZCNPQ | título + copy v2 + 5 imágenes |
| PS-3058 | B0HFW1Q1GW | título + copy v2 + 5 imágenes |
| PS-3095 | B0HFW54MNC | título + copy v2 + 5 imágenes |

Los tres cerraron en `BUYABLE` + `DISCOVERABLE`.

## Secuencia que funcionó

1. Credenciales desde Vaultwarden (`ssh prod` → `vw get 'Terceros/Amazon SP-API - NeuralCrew'`) → `/opt/data/.env` como `AMAZON_SPAPI_*` (backup previo).
2. `GET` de cada SKU para leer el estado real (guardar JSON en disco; es la base de comparación).
3. Hosting de las 15 PNG en Cloudflare Pages (`wrangler pages deploy` → `https://amazon-au-media.pages.dev/{SKU}/{archivo}.png`), verificando 200 en las 15 URL.
4. `PATCH` con `&mode=VALIDATION_PREVIEW` → `VALID` sin publicar.
5. `PATCH` real → `ACCEPTED`, `issues: []`.
6. `JSON_LISTINGS_FEED` como refuerzo cuando la galería no se fijaba.
7. Monitor cada 5 min releyendo attributes hasta 5/5 en los tres SKU.

## Comportamiento observado del pipeline

- Títulos y atributos de texto: se fijan en < 2 min.
- Imágenes: entre 5 y 20 min, con estados intermedios engañosos — un SKU mostró 5 imágenes y volvió a 1 dos minutos después (submissions solapadas procesándose en orden).
- Tras la estabilización, una segunda lectura 4 min después confirmó los tres sin cambios.

## Trampas concretas

- El reporte del feed llega **gzip**: `json.loads(gzip.decompress(raw))` o falla con `0x8b`.
- `curl` a `amazon.com.au/dp/{ASIN}` devuelve captcha de 2,8 KB: no sirve como verificación.
- `state.db`/`session` no aplican aquí: la verificación es siempre contra la API.
- No tocar precio ni stock sin aprobación explícita.

## Evidencia archivada

- `/opt/digital-expresions-amazon/docs/publicacion-2026-11-03-evidencia.json` (snapshot de attributes, imágenes, bullets, keywords y status).
- `/opt/digital-expresions-amazon/tools/spapi/` (cliente, PATCH, feed, monitor + README).
