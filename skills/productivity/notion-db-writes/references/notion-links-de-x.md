# Links de X — recetas verificadas (2026-08-27)

Feed de ingestión del grupo Telegram "Links de X". DB correcta: `3ae853a7-3369-81f4-9581-fcc41b5c5ea4`.

⚠️ Hay DOS DBs con ese nombre. La otra (`2682aa93-97f1-4bc9-9821-9d7ae2423e95`) NO tiene columnas Stack/Acción — no usar. El ID que aparece en el contexto del grupo (`335853a7-3369-810a-8e5e-c79c1ae7fb09`) es la DB de TikToks → 404 al escribir. `3ae853a7-3369-81e7-938e-000b79f5fb43` no existe.

## Schema (verificado GET /v1/databases/{id} el 27/08)
Title: "Links de X" · Parent: "Nexa Labs".

| Propiedad | Tipo | Notas |
|---|---|---|
| Name | title | |
| Link | url | clave de dedup |
| Fecha | date | `{"date":{"start":"YYYY-MM-DD"}}` |
| Relevancia | select | opciones: `⭐⭐⭐⭐⭐` `⭐⭐⭐⭐` `⭐⭐⭐` `⭐⭐` `⭐` + legacy `5 ⭐` `4 ⭐` `3 ⭐` → usar las emoji |
| Tema | select | AI Tools, AI Agents, Marketing, Business, Tech, Open Source, Productivity, DevOps, Other, Business Strategy, Hermes Agent, Video AI, Video IA, Automatización, Seguridad / DevOps, IA / Agentes, Negocios / IA, Scraping / Web, Agencias / Client Success, Producción Video, Automatización / Agentes |
| Resumen | rich_text | ≤2000 chars |
| Key Takeaway | rich_text | ≤2000 chars |
| Acción | rich_text | ≤2000 chars |
| Stack | rich_text | ≤2000 chars |

## Dedup (endpoint correcto)
```
POST https://api.notion.com/v1/databases/3ae853a7-3369-81f4-9581-fcc41b5c5ea4/query
{"filter":{"property":"Link","url":{"equals":"<status_url>"}},"page_size":5}
```
`results: []` = no ingestado aún → crear. La shape legacy (POST `/v1/databases/query` con `database_id` en el body) devuelve 400 `invalid_request_url`.

## Create (verificado funcionando)
POST `https://api.notion.com/v1/pages`:
```json
{"parent":{"database_id":"3ae853a7-3369-81f4-9581-fcc41b5c5ea4"},
 "properties":{
   "Name":{"title":[{"text":{"content":"<título>"}}]},
   "Link":{"url":"<status_url>"},
   "Fecha":{"date":{"start":"2026-08-27"}},
   "Relevancia":{"select":{"name":"⭐⭐⭐⭐⭐"}},
   "Tema":{"select":{"name":"AI Agents"}},
   "Resumen":{"rich_text":[{"text":{"content":"<≤2000>"}}]},
   "Key Takeaway":{"rich_text":[{"text":{"content":"<≤2000>"}}]},
   "Acción":{"rich_text":[{"text":{"content":"<≤2000>"}}]},
   "Stack":{"rich_text":[{"text":{"content":"<≤2000>"}}]}}}
```
Si `database_id` falla como parent (404), reintentar con `{"parent":{"data_source_id":"3ae853a7-3369-81f4-9581-fcc41b5c5ea4"}}` (nota 24/08: con la integración "Viking clan" funcionó al revés — por eso probar database_id primero y tener el fallback listo).

## Provenance
Primera ingestión validada con esta receta: página `3ca853a7-3369-8122-8d84-c28655275ede` (tweet Artie/Hermes de @JacquelineSYC19, 27/08/2026).

## Workflow de ingesta (resumen)
1. Extraer tweet (fixupx OG → FXTwitter API para texto completo + métricas; ver skill `x-tweet-scrape`).
2. Dedup por Link (query arriba). Si existe, reportar y NO recrear.
3. Crear página en Notion + guardar markdown en `/opt/data/brain/raw/x-feed-YYYY-MM-DD-<autor>-<tema>.md` (frontmatter con engagement).
4. Responder en el grupo con el reporte estandarizado (relevancia ⭐, resumen, takeaway, stack, acción) + "Guardado en Brain Wiki + Notion DB ✅".

Ver también: skill `twitter-telegram-ingestion` (workflow completo, user-owned).