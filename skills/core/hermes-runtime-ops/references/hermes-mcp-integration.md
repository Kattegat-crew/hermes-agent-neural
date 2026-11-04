---
name: hermes-mcp-integration
description: Use when adding or auditing MCP servers on Hermes fleet.
category: devops
---

# Integración de servidores MCP en la flota Hermes (NeuralCrew Labs)

Cómo declarar, asegurar y auditar MCPs (stdio y remotos) en los `config.yaml` de la flota, y qué es realmente viable contra la infra self-hosted (PROD por Tailscale).

## Declaración y secretos (verificado en el código de Hermes, 15-sep-2026)

- stdio: `command:` + `args:` (+ `env:`). Remoto: `url:` + `headers:` (+ `transport: sse`). Si hay `url` y `command`, gana `url` con warning (`tools/mcp_tool.py:3938,3996,4308`).
- **`mcp_servers` SÍ expande variables** — `${VAR}` y `${env:VAR}` vía `hermes_cli/config.py:3091 _expand_env_vars` (aplicado en `:4203`) y `tools/mcp_tool.py:6294 _interpolate_env_vars`, que además resuelve desde el **scope de secretos del perfil** (probado empíricamente). Por tanto: NUNCA tokens literales en el YAML; escribir `Authorization: Bearer ${VAR}` con la variable en un `.env` 600. (La creencia contraria estuvo en la v1 del plan de MCPs y fue desmentida por auditoría.)
- Recarga: `/reload-mcp` del gateway (pide confirmación; `gateway/run.py:19976`) o —método usado el 16-sep— **restart del servicio s6 del perfil** (`s6-svc -r /run/service/gateway-<perfil>`; ver `hermes-gateway-s6-ops`). Preflight HTTP salvo `skip_preflight` y salvo `transport: sse` (`mcp_tool.py:4342`).
- Permisos: config por perfil `600`, global `640`, owner `hermes`, gateway uid 10000.
- Coste de contexto: cada MCP registra tools en el prompt del perfil → activar por rol, tope ~30 tools/perfil.

## Qué es viable por servidor (resumen; detalle y comandos en references/)

- **Twenty v2.31.1**: MCP nativo SOLO por Tailscale `http://100.73.30.29:3020/mcp` (el dominio público pasa por oauth2-proxy SSO → 302, inservible headless). API key con rol read-only por Bearer; expone 2 tools.
- **ActivePieces**: RESUELTO 16-sep-2026 — corre para default+roshi vía usuario dedicado + tokens JWT (firmados con `AP_JWT_SECRET`, 90 días, renovación por timer) + proxy multi-proyecto. `/mcp` SOLO acepta JWT `aud=MCP_OAUTH_ACCESS` (el token estático de la UI no sirve). En Community el RBAC del MCP es allowAll → el candado real es `enabledTools` por proyecto. Runbook: skill `activepieces-mcp-ops`.
- **Composio**: `x-consumer-api-key` de alcance de CUENTA completa (todas las toolkits, con escritura) → cuenta dedicada + tools de escritura deshabilitadas.
- **Cloudflare**: Bearer estático verificado OK el 16-sep (issue #95 no aplica); par ro/write con confirmación (`CLOUDFLARE_MCP_TOKEN[_WRITER]`), zone-scoped.
- **Nginx Proxy Manager**: NO existe token con scopes; el MCP exige credenciales admin de NPM → `NPM_READONLY=true`, paquete pineado (`@kukolabs/mcp-nginx-proxy-manager@0.1.6`), último del lote o descartar si basta la API REST.
- **Postgres**: `uvx --from postgres-mcp --with 'mcp<2' postgres-mcp --access-mode restricted <dsn>` (sin `--with 'mcp<2'` falla). LIVE 16-sep-2026: el par `pg_ro` ya opera en la flota y su DB es la del CRM Twenty — verificado: database `default`, esquema `core` (71 tablas de metadatos Twenty: objectMetadata, fieldMetadata, userWorkspace, role…) + 3 esquemas `workspace_*` (~28 tablas c/u). Lecciones: (a) pg_ro puede caerse EN SILENCIO (incidente 15-sep: caído sin que nadie lo notara) → hacer una consulta barata (`list_schemas`) antes de confiar en un "sin datos"; (b) identificar la DB por su contenido (tablas core de Twenty), no asumir qué hay detrás del DSN; (c) con SQL directo sobre el CRM sí son viables agregados que la API Twenty no da (conteos por objeto, joins entre workspaces).
- **Stirling-PDF**: MCP nativo, apagado por defecto (`mcp.enabled:false`, auth oauth) → `enabled:true` + `auth.mode:apikey` + restart; allow-list con `allowedOperations`. **Paperless**: sin MCP nativo; community `chrisguidry/paperless-mcp` read-only es el preferido.
- **Vaultwarden NO como MCP**: daría al modelo lectura/escritura de todo el vault y rompe el mínimo privilegio. Si algún día: host-only, allow-list, solo-escritura.

## Uso en vivo del MCP AP: patrones de la primera auditoría (16-sep-2026)

- Los run IDs de AP NO son globales: `ap_get_run` bajo un proyecto equivocado devuelve
  `ENTITY_NOT_FOUND`, y `ap_list_runs` no dice de qué flow/proyecto viene cada run → mantener
  mapeo flowId→proyecto (videogen: 3 flows; jonathan: 4; lucky: 1) o probar proyecto a proyecto.
- El parámetro `project` usa la KEY del manifiesto (`videogen`/`jonathan`/`lucky`), no el nombre
  visible del proyecto en AP.
- Diagnóstico de FAILED: `ap_get_run` muestra step + error + body del trigger. Flows webhook sin
  cortocircuito de probes generan FAILED falsos que entierran los reales — hallados en la primera
  pasada: SMTP `No recipients defined` con triggers `HEAD` y `POST {"ping":true}` (health checks
  tratados como leads), y HTTP 400 `body inválido` con curl GET sin body. El error vivo del step
  manda sobre el conteo: distinguir probe ruidosa de fallo de negocio antes de escalar.
- El runbook completo de operación AP MCP vive en `activepieces-mcp-ops` (pendiente
  `hermes curator adopt` para poder extenderla; esta sección es el respaldo editable).

## Protocolo de auditoría antes de declarar (patrón validado)

1. Probe del endpoint FUERA de Hermes (curl 401/405/400 + `WWW-Authenticate`) antes de tocar config.
2. Dos auditores en contexto fresco y solo lectura, en paralelo: (A) afirmaciones técnicas del plan con archivo:línea; (B) viabilidad viva con curl/docker inspect/npm view. Ambos encontraron errores escritos por el propio autor del plan.
3. Bloqueantes de credencial primero: separar lo que ya está en Vaultwarden (Cloudflare/Twenty/AP/Paperless/Postgres tienen item) de lo que se EMITE en la app (API key Twenty, consumer key Composio, token MCP AP, token Paperless).
4. Veredicto APROBADO / CON RESERVAS / RECHAZADO + nota 1-10; un RECHAZADO bloquea la fase siguiente. Orden de fases por riesgo creciente (datos de cliente read-only primero, infra destructible al final).

## Escritura con confirmación (patrón F2.1, validado 16-sep-2026)

- **Par de entries**: `<mcp>` (tools de lectura, silencioso) + `<mcp>_write` (solo escritura, `trust: untrusted`) ⇒ confirmación humana por llamada. Fail-closed verificado (en frío: "The command was NOT run"; en gateway vivo: `[o]nce/[s]ession/[d]eny`).
- **Uniformidad**: todos los perfiles con el MCP llevan el MISMO par; lo que tenga un agente lo tienen los orquestadores.
- **Annotations**: el trust gate de Hermes (`_annotation_read_only_hint`) lee camelCase mientras el SDK emite snake_case ⇒ en tools vivas ninguna se exime; el gate de escritura igual funciona por `trust: untrusted` (no depende de annotations).
- **Remotos project-scoped** (AP): tokens por proyecto ⇒ proxy con parámetro obligatorio `project` (evita N×M entries).

## Referencias

- `data/brain/plans/plan-mcps-2026-09-15.md` — plan de la flota MCP; Anexo B = F0–F5.1 con evidencia y reviews.
- `references/mcp-fleet-feasibility-2026-09-15.md` — inventario del vault (57 items), evidencia por endpoint con comandos, y hallazgo vault-sync roto.
