# Acceso y verificación de precios por retailer

Recetas verificadas para confirmar precio/stock sin navegador cuando es posible.

## Falabella (.com.co)
- curl con UA de escritorio + `Accept-Language: es-CO,es;q=0.9` basta; no requiere navegador.
- Las páginas de búsqueda (`https://www.falabella.com.co/falabella-co/search?Ntt=<query+con++>`) incluyen un `<script type="application/ld+json">` con `@type: ItemList`: name, url completo del producto, offers[], brand.
- El JSON-LD viene HTML-escapado (`&quot;`): aplicar `html.unescape` ANTES de `json.loads`. Sin eso el parseo falla en silencio (un try/except devuelve 0 items y parece "sin resultados").
- `offers[]` = [precio venta, precio lista].
- Regex naive sobre el HTML crudo encuentra los nombres pero NO los precios: parsear el JSON-LD completo, no ventanas de texto.

## Tiendas Shopify (boutiques locales, p. ej. Casa Viva)
- `GET https://<dominio>/products/<slug>.json` devuelve title, `variants[].price` (COP con decimales, "75000.00"), tags y disponibilidad. Vía más rápida y robusta para confirmar precio/stock.
- Encontrar el slug con web_search `"<producto>" <tienda>`; el link canónico es `/products/<slug>`.
- La variante puede venir como `Default Title` con el precio único: eso confirma precio aunque no haya tallas.

## MercadoLibre
- curl directo y proxies de lectura (p. ej. r.jina.ai) pueden caer en challenge o redirect de verificación de cuenta desde IPs de datacenter. No pelear el muro: conseguir el listing por web_search, entregar el link y marcar el precio "no verificado".

## VTEX / JS-heavy (Panamericana, Alkosto)
- El HTML inicial no trae productos; antes de descartar la tienda, buscar `__STATE__` o `__NEXT_DATA__` en el fuente. Si no están, no gastar navegador salvo que el usuario pida explícitamente esa tienda.
