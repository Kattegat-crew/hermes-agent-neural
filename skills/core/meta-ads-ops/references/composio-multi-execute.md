# Composio MULTI_EXECUTE — transporte de ejecución Meta Ads (verificado 16-oct-2026)

## Patrón de transporte

Las tools de acción `METAADS_*` NO se exponen como tools directas del MCP de Composio
(llamada directa `tools/call` de `METAADS_*` devuelve `Tool not found`). La única vía:

```
POST https://connect.composio.dev/mcp
headers: x-consumer-api-key: <COMPOSIO_MCP_KEY, exportada por el caller>, Accept: application/json, text/event-stream
body: {"jsonrpc":"2.0","id":1,"method":"tools/call","params":{
  "name":"COMPOSIO_MULTI_EXECUTE_TOOL",
  "arguments":{"tools":[{"tool_slug":"METAADS_CREATE_CAMPAIGN","arguments":{...}}]}}}
```

La respuesta llega como SSE — parsear las líneas `data: ` y tomar la última.
Formato de resultado: `{"successful":bool,"data":{"results":[{...,"tool_slug","index"}],"total_count","success_count","error_count"}}`.
Los errores llegan EN-BANDA (`results[0].error`) como éxito HTTP — un executor ingenuo los lee como id nulo.

## Routing multi-cuenta (BLOQUEO ABIERTO, ticket 1560875784246399059)

Con 2 conexiones metaads activas ("Golden Game Adds" / "Lucky  Brothers Adds") toda
llamada devuelve: `Multiple metaads accounts connected. Specify which to use via the
'account' field`. El campo `account` NO se acepta:
- dentro de `arguments` de cada tool entry → mismo error
- como top-level del MULTI_EXECUTE → mismo error
- los schemas (`COMPOSIO_GET_TOOL_SCHEMAS`) NO declaran ningún campo `account` (solo `account_id` = ad account de Meta)

NO reintentar esas shapes en ciclo — verificar estado de la cuenta y esperar el fix.

## Gotchas verificados

- `COMPOSIO_MANAGE_CONNECTIONS` con `action='list'` + `toolkits` NO lista:
  INICIA una conexión nueva pendiente y devuelve `redirect_url`. Descartar links
  pendientes generados por error (no abrirlos).
- Los schemas de tools metaads declaran `account_id` (ID de Meta, ej. act_...),
  `lifetime_budget`, `daily_budget`, `targeting`, `promoted_object` (pixel),
  `optimization_goal`. Presupuesto lifetime: sumas por adset, período vía
  `start_time`/`end_time`; campos extra violan el schema.
- No existe UPLOAD_AD_VIDEO en el toolkit → creativos video (reels 9:16) no se
  suben por API; vía manual en Ads Manager mientras.

## Executor persistido

`marketing/ads-optimizer/scripts/ads_execute_composio.py` (skill ads-optimizer):
lee dryrun.json del plan, resuelve refs `${campaign:...}/${adset:...}` con IDs
reales de respuestas previas, salta creatives/ads, extrae IDs de campaña/adset
con regex `23\d{13,17}` de la respuesta JSON serializada. La key va por variable
de entorno `COMPOSIO_MCP_KEY` (el script nunca lee archivos de secretos).
