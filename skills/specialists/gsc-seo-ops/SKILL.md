---
name: gsc-seo-ops
description: "Use when reading Google Search Console via Composio MCP."
tags: [seo, google-search-console, composio, indexacion, sitemap]
version: 1.0.0
author: ragnar
license: internal
metadata:
  hermes:
    tags: [seo, google-search-console, composio, indexacion, sitemap]
    related_skills: [composio-integrations, composio-cli]
---

# GSC SEO Ops (vía Composio MCP)

## When to Use

- Al medir rendimiento SEO (clics/impresiones/posición) de goldengame.com.co o paradiseclubcasinos.com.co.
- Al verificar si una URL quedó indexada, revisar estado de sitemaps o comparar avances contra el baseline.
- NO usar para escribir/cambiar nada en GSC — esta skill es de solo lectura (la escritura pide cuota y va gated).

Leer Google Search Console por Composio MCP: rendimiento por página, inspección de indexación URL por URL y estado de sitemaps. Verificado e2e el 09-nov-2026 contra las propiedades de Golden Game y Paradise (Lucky Brothers).

## Propiedades canónicas (domain properties)

- `sc-domain:goldengame.com.co` — Golden Game
- `sc-domain:paradiseclubcasinos.com.co` — Paradise / Lucky Brothers

## Tool slugs verificados

| Slug | Uso |
|---|---|
| `GOOGLE_SEARCH_CONSOLE_SEARCH_ANALYTICS_QUERY` | clicks/impresiones/posición agrupado por `page`, `query`, `date` |
| `GOOGLE_SEARCH_CONSOLE_INSPECT_URL` | estado de indexación de UNA URL (veredicto oficial) |
| `GOOGLE_SEARCH_CONSOLE_LIST_SITEMAPS` | sitemaps enviados + `isPending` |
| `GOOGLE_SEARCH_CONSOLE_GET_SITEMAP` | detalle: `submitted`/`indexed`, `lastDownloaded` |

Ejecutarlas con el wrapper `mcp__composio_write__COMPOSIO_MULTI_EXECUTE_TOOL` (vive en el server **write**, no en el read). Hasta 25+ llamadas en un solo batch.

## Pitfalls obligatorios (verificados)

1. **Multi-cuenta**: hay 2 conexiones GSC (`Captain-NeuralSearch` y `google_search_console_motley-velvet`). Siempre pasar `"account": "Captain-NeuralSearch"` como clave HERMANA de `tool_slug`/`arguments` en cada item del wrapper — no dentro de `arguments`.
2. **Args en snake_case**: `site_url`, `start_date`, `end_date`, `row_limit`, `aggregation_type`, `inspection_url`, `feedpath`. Los camelCase fallan en silencio/validación. Ante duda, pedir el schema exacto con `mcp__composio__COMPOSIO_GET_TOOL_SCHEMAS` (`tool_slugs: [...]`) ANTES de ejecutar — nunca inventar campos.
3. **`mcp__composio__COMPOSIO_SEARCH_TOOLS`** recibe queries ESTRUCTURADAS: `[{"use_case": "...", "session": {"generate_id": true}}]` — no strings planos.
4. Cobertura de datos con lag 2–3 días (UTC): las fechas finales deben ser T-3. `aggregation_type: "byPage"` para rendimiento por página.

## Cómo interpretar la indexación (lección 09-nov)

La inspección URL devuelve tres veredictos con significado operativo distinto:

- **Indexada (PASS)** — ok.
- **"Descubierta, sin indexar"** — Google la conoce (sitemap funcionó) pero decide no indexarla aún: señal externa débil. Palanca: enlaces internos/GBP posts con UTM hacia esa ruta, tiempo.
- **"URL no reconocida"** — ni descubierta: revisar canonicals/redirects (variantes http/www vs https sin www confunden el descubrimiento) y solicitar indexación vía GSC UI.

El contador `submitted/indexed` del sitemap va REZAGADO respecto a la inspección URL (ej. sitemap decía indexed:0 mientras la inspección ya mostraba 3 indexadas). Fuente de verdad por URL = INSPECT_URL, no el contador del sitemap. `isPending: true` en GET_SITEMAP = Google aún no procesa el sitemap (cola de días, no bug nuestro).

## Referencias

- `references/snapshots-2026-11-09.md` — baseline de las dos propiedades (rendimiento 30d + veredictos de las 22 URLs) para comparar avance futuro.
