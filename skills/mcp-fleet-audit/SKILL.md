---
name: mcp-fleet-audit
description: Use when auditing MCP server health or testing all available MCPs — exact read-only test call per server, verified 27-oct-2026 (17/17 OK).
---

# Auditoría de flota MCP (verificada 27-oct-2026)

Protocolo: una llamada de SOLO LECTURA por servidor, todo en lotes paralelos.
Nunca usar tools de escritura para probar (nada de gmail_send, run_model, deploys).

## Llamada de prueba por servidor

| Servidor | Prueba read-only | Evidencia esperada |
|---|---|---|
| ap | `ap_list_flows(project="videogen")` | N flows ENABLED |
| canva | `help(prompt="...", user_intent="connectivity test")` | job status success |
| chrome_devtools | `list_pages` | lista de tabs |
| cloudflare | `whoami` | "NeuralCrew Labs" |
| composio | `COMPOSIO_SEARCH_TOOLS(queries=[...], session={generate_id:true})` | conexión ACTIVE |
| context7 | `list_prompts` | respuesta (puede ser vacía) |
| coolify | `get_version` | versión |
| docuseal | `search_templates(q="contrato")` | plantillas |
| engram | `mem_search(query, all_projects=true)` | observaciones |
| fal | `get_pricing(endpoint_id="fal-ai/flux-pro/v1.1")` | precios (sin gasto) |
| formbricks | `list_surveys(workspaceId="cmsywjcrj000101prw5rpro8x")` | encuestas |
| github | `search_repositories(query="org:NousResearch")` | repos |
| ncl_google | `google_list_accounts` | buzones |
| opendesign | `list_projects` | proyectos |
| outline | `whoami` | usuario admin |
| paperless | `get_statistics` | conteo docs |
| stirling | `stirling_describe_operation(operation="compress-pdf")` | schema |
| twenty | `get_tool_catalog(workspace="nc")` | catálogo tools |

## Gotchas (lecciones de la auditoría real)

- **Clase de pitfall generalizada (verificada 27-29-oct):** tras la migración,
  `config.yaml` puede contener placeholders LITERALES `${VAR}` (p.ej.
  `${NAN_BUILDERS_API_KEY}`, `${FORMBRICKS_MCP_KEY_RO}`). Todo consumidor que lo
  lea (extractor semántico de graphify, keys de MCP) pasa el texto literal como
  API key → 401 "Invalid API key". Síntoma: 401 con una key de longitud
  sospechosa (~25 chars con `${}`). Resolución: valor REAL desde Vaultwarden →
  D-I-V-E sobre config.yaml (backup → patch → verificación end-to-end
  ejecutando el job/cron manual). NUNCA extraer el literal del yaml.
- **formbricks**: cada llamada exige `workspaceId` (cuid) = `cmsywjcrj000101prw5rpro8x`.
  Vía para descubrirlo: curl a `/api/v1/management/me` con la key REAL (la MCP key
  también es management key).
- **github**: el calificador `user:` en search_repositories a veces devuelve
  `items: []` con `total_count>0` — quirk del índice de GitHub, no falla de auth.
  Token = Kattegat-crew (PAT clásico, scopes completos). Para repos de un usuario
  usar REST directa (`/users/<user>/repos`).
- **ncl_google_write**: solo tiene `gmail_send` — NO probar; mismo backend que
  ncl_google ya verificado.
- Los conectores hosted (Notion, Slack, etc.) aparecen "no conectados" por diseño:
  el acceso Google va por ncl_google/ActivePieces, no por conectores hosted.
- Enlaces t.co de posts: resolver con `curl -sI <url> | grep -i location`.
- Comparativo contra listas virales de "top MCPs" (27-oct): de 15 populares,
  solo 3 nos servían (Context7, Chrome DevTools, GitHub — ya instalados). El resto
  era redundante con nuestra pila (Playwright→chrome-devtools, n8n→ActivePieces,
  MCP Toolbox→Twenty/Paperless MCP, Codebase Memory→Engram+grafo, Figma→Canva MCP)
  o fuera de negocio (Blender, Unity, Xiaohongshu). Único candidato futuro:
  **Apify MCP** (scraping a escala para Ullr/Heimdall) — es PAGO por uso →
  evaluar solo con caso concreto y pasaría por spend gate.
  No instalar MCPs por FOMO: cada servidor infla el catálogo de tools y confunde
  al agente (2-3 MCPs bien elegidos > 15 populares).
