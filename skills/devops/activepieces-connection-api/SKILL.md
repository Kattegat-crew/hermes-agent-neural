---
name: activepieces-connection-api
description: "Use when creating ActivePieces connections via REST."
tags: [activepieces, api, oauth, jwt, conexiones, self-hosted]
version: "1.0"
author: Ragnar
created: 2026-08-26
category: devops
metadata:
  hermes:
    tags: [activepieces, api, oauth, jwt, conexiones, white-label, self-hosted]
    related_skills: [activepieces-selfhost-ops, hermes-admin-operations, nginx-proxy-manager-api]
---

# ActivePieces Connection API — crear conexiones por REST (sin UI)

## When to Use

- Necesitas que una página con marca propia (white-label / "Conectar con NeuralCrew") cree conexiones DENTRO de ActivePieces al autorizar el usuario, sin que el cliente ni tú toquen la UI de AP.
- Automatizar la creación de conexiones OAuth (Gmail, Google Sheets, etc.) por tenant/cliente.
- Depurar errores `INVALID_BEARER_TOKEN`, `invalid principal type`, `invalid access token or session expired` en la API de AP.

## Conceptos clave (verificados 26/08/2026)

- **El MCP de AP NO crea conexiones** — solo las lista (`ap_list_connections`) y da instrucciones (`ap_setup_guide`). Las conexiones se crean por la UI o por la **API REST interna**.
- **La API REST vive en el prefijo `/api/v1/`** (NO `/v1/` — eso sirve la SPA y siempre devuelve 200 con HTML).
- Las conexiones se guardan cifradas con la clave interna de AP; insertarlas a mano en Postgres (tabla `app_connection`) es frágil — usar el flujo OAuth oficial.
- Google exige redirect URIs de **dominio público real** (`https://connect.dominio.com/callback`). Rechaza IPs privadas (Tailscale 100.x, localhost) con `invalid_request` — configurar un subdominio propio (+ nginx + TLS) ANTES de armar el flujo.

## Flujo de creación (white-label) — 3 pasos

```
backend → (1) POST /api/v1/app-connections/oauth2/authorization-url  → Google URL
usuario → abre URL, autoriza en Google → Google redirige a redirectUrl?code=...&state=...
backend → (2) POST /api/v1/app-connections (CLOUD_OAUTH2 con el code) → conexión guardada en AP (visible en Settings → Connections)
```

### Paso 1 — Obtener authorization-url

```
POST /api/v1/app-connections/oauth2/authorization-url
Body: {"pieceName":"@activepieces/piece-gmail","projectId":"<pid>",
       "clientId":"<Google client id>","redirectUrl":"https://connect.dominio.com/callback"}
Headers: Authorization: Bearer <JWT>, Accept: application/json, X-Project-Id: <pid>
→ {"authorizationUrl":"https://accounts.google.com/..."}  (incluye state propio de AP)
```

AP genera la URL con su propio `state`/PKCE internos — no hace falta code_challenge manual.

### Paso 2 — El usuario autoriza en Google (navegador)

Redirigir al cliente a `authorizationUrl`. Google → login → consent → vuelve a `redirectUrl?code=...&state=...`.

### Paso 3 — Entregar el code a AP (guarda la conexión)

```
POST /api/v1/app-connections
Body: {"externalId":"<nombre-conexion>","displayName":"<nombre>","pieceName":"@activepieces/piece-gmail",
       "projectId":"<pid>","type":"CLOUD_OAUTH2",
       "value":{"client_id":"<Google client id>","code":"<code del callback>",
                "scope":"<scopes que AP pidió>","type":"CLOUD_OAUTH2"}}
Headers: Authorization: Bearer <JWT>, Accept: application/json, Content-Type: application/json, X-Project-Id: <pid>
```

Para multi-tenant: guarda el `state` del paso 1 en una sesión (ej. `sessions/<state>.json` con `{connection: "<tenant>-gmail"}`) y úsalo en el callback para saber a qué conexión mapear el code.

## JWT de la API REST (el detalle que más cuesta)

- Firmar **HS256 con `AP_JWT_SECRET`** (el sistema lee envs como `AP_${prop}`, así `JWT_SECRET` = `AP_JWT_SECRET`).
- Payload EXACTO:
  ```json
  {"id":"<user.id>","type":"USER","platform":{"id":"<platform.id>"},
   "tokenVersion":"<user_identity.tokenVersion>","iss":"activepieces","iat":<now>,"exp":<now+604800>}
  ```
- `type` = **`"USER"` en MAYÚSCULAS** (`PrincipalType.USER` de `@activepieces/shared`). Minúscula → `invalid principal type`.
- **`tokenVersion` DEBE coincidir** con `user_identity.tokenVersion`; sin él o distinto → el verify pasa pero `assertUserSession` falla con `invalid access token or session expired`. Obtenerlo:
  ```sql
  SELECT id, "platformId" FROM "user";
  SELECT "tokenVersion", verified FROM user_identity;
  ```
- `iss:"activepieces"` obligatorio (el signer de AP lo fija; sin él el verify falla).
- Vigencia 7 días (como `generateToken`); para un servidor interno es aceptable.

## Dónde depurar (siempre dentro de ap-app)

- API server: `/usr/src/app/packages/server/api/dist/src/`
- `app/helper/jwt-utils.js` — `decodeAndVerify` (algorithm HS256, issuer activepieces), `getJwtSecret` (lee `AP_JWT_SECRET`; si el tipo de Redis es MEMORY lo genera y guarda en `~/.activepieces/settings.json`).
- `app/authentication/lib/access-token-manager.js` — `verifyPrincipal` + `assertUserSession` (compara tokenVersion, user status, identity verified).
- `shared/dist/src/lib/core/authentication/model/principal-type.js` — enum: `USER`, `ENGINE`, `UNKNOWN`, `SERVICE`, `WORKER`.
- `app/app-connection/` — controller con las rutas (`app.get('/')`, `app.post('/')`, `app.post('/oauth2/authorization-url')`).
- `shared/dist/src/lib/automation/app-connection/dto/upsert-app-connection-request.js` — schemas de los bodies (CLOUD_OAUTH2 etc.).

## Receta: extraer credenciales OAuth de una conexión AP (28/08)
Para usar Gmail/Calendar/Drive API DIRECTA sin flows (ej. daemon IMAP):
1. `docker exec ap-db psql -U postgres -d activepieces` → tabla `app_connection`, columna `value` (JSON cifrado `{iv,data}` en **HEX**, no b64).
2. Descifrar AES-256-CBC con la key cruda utf-8 de `AP_ENCRYPTION_KEY` (env de `ap-app`) — librería `cryptography` (NO `pycryptodome`; solo existe en sandbox).
3. El blob trae `refresh_token`, `client_id`, `client_secret` (GOCSPX...), `scope`, `id_token`.
4. Refresh contra `oauth2.googleapis.com/token` → access_token → API directa. Materializar JSON plano **chmod 600** en `/opt/data/scripts/` para el daemon; nunca dejar secretos en /tmp.
5. IMAP XOAUTH2 exige scope `https://mail.google.com/` (`gmail.readonly` NO basta). Formato SASL: `user\x01auth=Bearer <token>\x01\x01`.
6. PKCE manual para flujos propios fuera de la puerta: codeVerifier → `code_challenge` en authorization-url → `code_verifier` en el canje.
7. El callback de connect.neuralcrewlabs.com RECHAZA codes de flujos externos → pedir al usuario la URL final del navegador y canjear a mano.
8. `id_token` del refresh permite resolver la cuenta real (JWT, claim `email`) sin llamada extra — Calendar scope sin `openid` da userinfo 401.

## Pitfalls

- `/v1/...` (sin api) devuelve la SPA con 200 — siempre parece "funcionar". Usar `/api/v1/`.
- El SDK embed de AP (`authorizeMcp` del CDN embed 0.13.0) se colgó en la práctica → preferir el flujo REST (idéntico resultado, observable HTTP a HTTP).
- `X-Project-Id` es obligatorio en las llamadas; sin él: `Cannot read properties of undefined (reading 'type')` en 401.
- Errores de validación FST (`FST_ERR_VALIDATION`) = ruta real existe pero body/params mal formados.
- No exponer `AP_JWT_SECRET` ni el tokenVersion en el frontend; el backend genera el JWT.

## Verificación

- `curl -s -o /dev/null -w "%{http_code}" <AP>/api/v1/projects -H "Authorization: Bearer $JWT" -H "X-Project-Id: <pid>"` → 200 con JSON = token válido.
- Tras el flujo completo: `ap_list_connections` (vía `ap_call.py`) debe listar la nueva conexión ACTIVE.
- En la UI: Settings → Connections debe mostrar la conexión.

## Materialización de credenciales para MCP servers (28/08)

Cuando un perfil de cliente necesita operar cuentas Gmail/Drive/Calendar directamente (sin flows de AP), las credenciales se materializan en disco plano para un MCP stdio server:

1. `verify_connection.py` ahora escribe `/opt/data/secrets/{slug}-{svc}.json` (chmod 600) al marcar `active`. Contiene: `connection`, `account`, `refresh_token`, `client_id`, `client_secret`, `scope`.
2. Para conexiones existentes (sin secrets): re-ejecutar `verify_connection.py <slug>-<svc>` sin `--no-write`.
3. El MCP server (`ncl_google_mcp.py`) lee estos archivos, valida ownership, y usa refresh token directo contra Google API.
- `sync_connections_map.py` propaga secrets a prod (junto con el mapa).

Ver `client-connection-flow/references/ncl-google-mcp-bridge.md` para el patrón completo.

## ESTÁNDAR GLOBAL — método de conexión de TODOS los agentes (06/09/2026)

Decisión de Jonathan (06/09/2026): **todo agente usa TODAS sus conexiones (ActivePieces + tokens directos) según lo que necesite.** Regla implementada:

1. **ActivePieces es la fuente única de verdad** de las conexiones Google (estables, no caen a los 7 días: viven en el cliente OAuth `288239405432…`, distinto al del token directo `80712886806…` que sí sigue el ciclo de 7 días en modo Testing).
2. **Capa de credenciales materializadas** en `/opt/data/secrets/{connection}.json` (chmod 600): el agente usa el refresh_token de AP directo contra Google. Cada agente tiene su MCP server `ncl_google_mcp.py --profile <perfil>` registrado en su `config.yaml` (mcp_servers.ncl_google), que carga solo las conexiones cuyo `owner == perfil` y `status == active`.
3. **Fallback:** el token directo (`google_token.json`, `GOOGLE_TOKEN_PATH`) queda disponible como respaldo; el MCP de AP es la vía primaria.
4. **Perfil default (Ragnar):** materializó `jonathan-gmail/drive/calendar` (cuenta `jonathaun124@gmail.com`) vía `verify_connection.py` y se registró `ncl_google_mcp --profile default`. Verificado funcional: Gmail labels, Drive archivos, Calendar eventos OK.

**Para replicar a un agente nuevo:** 1) conexión en AP → 2) `verify_connection.py <conn>` para materializar secret + marcar active → 3) añadir `mcp_servers.ncl_google` (args `--profile <perfil>`) a su config.yaml vía `hermes config set` → 4) reiniciar gateway con cron one-shot `no_agent` (nunca en el propio turno) → 5) verificar handshake MCP.

**Monitoreo:** `verify_connection.py` y el cron `check-verificacion-google-oauth` validan que las conexiones sigan vivas; si una cae, se corrige reconectando en AP (Settings → Connections → Reconnect).

## Pitfalls de implementación del estándar (06/09/2026)

**Registro del MCP en config.yaml — guard del sistema:**
- El tool `patch`/`write_file` **REFUSES** editar `/opt/data/config.yaml` (guard de seguridad: *"Agent cannot modify security-sensitive configuration. Edit ~/.hermes/config.yaml directly or use 'hermes config' instead"*). No intentar la edición directa.
- Vía sancionada: `hermes config set` con claves anidadas. El CLI vive en `/opt/hermes/bin/hermes`:
  ```bash
  /opt/hermes/bin/hermes config set mcp_servers.ncl_google.command python3 --force
  /opt/hermes/bin/hermes config set mcp_servers.ncl_google.args '["/opt/data/scripts/ncl_google_mcp.py", "--profile", "default"]' --force
  ```
  (`args` se pasa como **JSON array**; `--force` silencia el aviso de "unknown key"). Validar con `hermes config get mcp_servers`.
- Verificar YAML tras el cambio: `python3 -c "import yaml; yaml.safe_load(open('/opt/data/config.yaml'))"`.

**Reinicio del gateway — NUNCA en el propio turno:**
- Los cambios de config solo aplican al reiniciar el gateway; **nunca** `hermes gateway restart` dentro del turno (mata la sesión).
- Patrón correcto: cron one-shot `no_agent` que corre el script de reinicio **después** de terminar el turno. Vía `cronjob_manage` (action=create, `schedule='in 4m'`, `no_agent=true`, `deliver='local'`, `script='gateway_restart_once.sh'`); el `script` debe ser **nombre relativo** (resuelve bajo `~/./scripts/`), no ruta absoluta.
- El servicio real es `gateway-default` (NO `main-hermes`); `gateway_restart_once.sh` usa `s6-svc -r /run/service/gateway-default` (ver `devops/hermes-gateway-s6-ops`).

**Verificación end-to-end tras el reinicio:**
1. `hermes config get mcp_servers` → aparece el server.
2. Handshake MCP: `printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"initialize",...}' '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' | python3 /opt/data/scripts/ncl_google_mcp.py --profile default` → lista `gmail_list/gmail_read/gmail_send/drive_search/drive_read_text/calendar_list_events`.
3. Probar una tool real (ej. `calendar_list_events`) y confirmar que devuelve datos de la cuenta.

Ver el modelo de los dos clientes OAuth de Google y la receta de verificación en `references/google-oauth-dual-client.md`.

## Referencias

- `references/ap-connect-flow.md` — receta verificada end-to-end (JWT + authorization-url).
- `scripts/ap_connect_flow.py` — generador de JWT + los 2 POST, listo para adaptar.
- Relación con `activepieces-selfhost-ops` (operación del stack) y `vps-host-access` (acceso al host).