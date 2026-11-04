# Notion TikTok Watch — estado y receta (28/08/2026)

## Estado de la DB
- El contexto del grupo 'TikToks' cita `335853a7-3369-81e3-b261-e4e44c10fc36` → **404 object_not_found** con la integración "Viking clan" (ntn_357632...).
- No aparece entre las 13 DBs accesibles vía `POST /v1/search` (filter: database). Drift documentado en `github-repo-ingestion/references/notion-db-id-drift.md`: los IDs con prefijo `335853a7-3369-81` provienen de un estado viejo del workspace.
- `.env` tiene `NOTION_DB_TIKTOKS=335853a7-3369-81e3-b261-e4e44c10fc36` (mismo ID caído).
- Pendiente: que el Admin comparta la DB TikTok Watch con la integración o confirme el ID actual. Entonces: actualizar `.env` y esta nota.
- Mientras tanto: guardar SOLO en Brain Wiki (`/opt/data/brain/raw/`) y reportar el bloqueo al grupo.

## Receta de verificación (usar SIEMPRE antes de escribir)
```bash
# 1) ¿El ID citado existe?
curl -s "https://api.notion.com/v1/databases/<id>" \
  -H "Authorization: Bearer $NOTION_API_KEY" -H "Notion-Version: 2022-06-28"
# 404 → buscar el ID actual:
curl -s -X POST "https://api.notion.com/v1/search" \
  -H "Authorization: Bearer $NOTION_API_KEY" -H "Notion-Version: 2022-06-28" \
  -H "Content-Type: application/json" \
  -d '{"filter":{"value":"database","property":"object"}}'
```
El search con `query:"TikTok"` puede devolver 0 resultados aunque la DB exista bajo otro nombre — listar TODAS y filtrar por título en cliente (lección de `notion` skill: 2025-09-03 también funciona).

## Create (patrón verificado en la DB hermana 'Links de X')
POST `https://api.notion.com/v1/pages`:
```json
{"parent":{"database_id":"<id>"},
 "properties":{
   "Name":{"title":[{"text":{"content":"<título>"}}]},
   "Link":{"url":"<url del video>"},
   "Fecha":{"date":{"start":"YYYY-MM-DD"}},
   "Relevancia":{"select":{"name":"⭐⭐⭐⭐"}},
   "Resumen":{"rich_text":[{"text":{"content":"<≤2000 chars>"}}]}}}
```
- Si `database_id` da 404 como parent, reintentar con `{"parent":{"data_source_id":"<id>"}}` (comportamiento varía por versión de API/integración).
- Inspeccionar el schema con GET antes de crear: los nombres de columnas cambian (verificado en Links de X 27/08).
- Dedup: query por la propiedad Link con `{"filter":{"property":"Link","url":{"equals":"<url>"}}}` (endpoint: `POST /v1/databases/<id>/query`) → `results: []` = no existe aún. La shape legacy con `database_id` en el body devuelve 400.
