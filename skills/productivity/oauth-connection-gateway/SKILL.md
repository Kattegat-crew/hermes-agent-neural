---
name: oauth-connection-gateway
description: "Use when building multi-tenant OAuth connection gateways."
tags: [oauth, conexiones, connections, multi-tenant, activepieces, google]
version: "1.0"
created: 2026-08-26
category: devops
metadata:
  hermes:
    tags: [oauth, conexiones, activepieces, multi-tenant, google]
    related_skills: [activepieces-selfhost-ops, google-workspace]
---

# OAuth Connection Gateway — puerta de conexión de marca para integraciones multi-tenant

## When to Use

- Un cliente debe conectar su cuenta (Gmail/Google) con un botón "Conectar con <Marca>", sin ver ActivePieces ni consolas técnicas.
- Hay que decidir/implementar DÓNDE vive el token de una cuenta: en storage de los agentes (google_api.py) o como conexión EN ActivePieces (flows de AP).
- Diagnóstico de "no veo la conexión en AP" / "Google rechaza el redirect" / "401 del API de AP".

## Los DOS mundos (la confusión más común del cliente)

| Mundo | Cómo se crea | Para qué sirve | Lo veo en AP |
|-------|--------------|----------------|--------------|
| Token en storage nuestro (`token_storage.json`) | OAuth directo a Google desde tu página | Los agentes leen/envían correo vía `google_api.py` | ❌ NO |
| Conexión EN ActivePieces | UI de AP o SDK embed `activepieces.connect()` | Flows de AP (trigger/acciones con auth resuelta) | ✅ SÍ |

- El MCP de AP **no crea conexiones** — solo `ap_list_connections` / `ap_setup_guide` (que devuelve "vaya a Settings → Connections").
- Insertar filas en `app_connection` a mano NO vale: el `value` va cifrado con clave interna de AP (`iv`+`data`).
- Si el cliente espera ver la conexión en AP: UI de AP (2 min/cuenta) o embed SDK con signing key de la plataforma (RS256) — nuestro despliegue no tiene signing keys → hoy solo UI.

## Reglas duras de Google OAuth

1. **El redirect URI debe ser dominio público con TLD real** (`.com`, `.org`). Google rechaza IPs privadas (Tailscale 100.x, localhost) con `invalid_request: must end with a public top-level domain`. Esto bloquea pruebas por IP — el subdominio + HTTPS es requisito, no opción.
2. Client OAuth: crear en proyecto de la empresa (no personal), `Authorized redirect URIs` = `https://connect.<dominio>/callback`. Test users necesarios en modo Testing.
3. Scopes recomendados para agente de comunicaciones: `gmail.modify`, `calendar.events`, `drive.file` (UN solo consentimiento, cero scope innecesario — Google rechaza apps con scopes de más).
4. Params del flujo directo: `access_type=offline` (refresh token), `prompt=consent`, PKCE S256 (verifier guardado por `state` en sesión).
5. El SDK embed `activepieces.authorizeMcp` se cuelga en la práctica; usar OAuth directo de Google en la página propia como camino confiable.

## JWT de la API REST de AP (Bearer /api/v1/*)

- Firma HS256 con **AP_JWT_SECRET** (el sistema lee `AP_<PROP>`), `iss: activepieces`.
- Payload principal tipo USER: `{id, type: "USER" (MAYÚSCULA), platform: {id}, tokenVersion}`.
- **`tokenVersion` obligatorio**: debe coincidir con `user_identity.tokenVersion` de la DB, o 401 "invalid access token or session expired". Obtener vía:
  `SELECT u.id, u."platformId", i."tokenVersion" FROM "user" u JOIN user_identity i ON i.id=u."identityId";`
- Headers: `Authorization: Bearer <jwt>` + `X-Project-Id: <project_id>`.
- Endpoint que genera la URL de autorización de una pieza (usa el embed SDK):
  `POST /api/v1/app-connections/oauth2/authorization-url` body `{pieceName, projectId, clientId, redirectUrl}` → `{authorizationUrl, codeVerifier}`.

## JWT del MCP de AP (para ap_call / tools MCP)

- Payload: `{sub, projectId, platformId, type:"mcp_oauth", aud:"MCP_OAUTH_ACCESS", iss:"activepieces", exp: now+900}` (HS256, AP_JWT_SECRET).
- Headers: `Content-Type: application/json` + **`Accept: application/json, text/event-stream`** (sin él → 406 Not Acceptable).
- Sin `iss=activepieces` → 401.

## Estandarización del proceso de conexión (SOP 28/08, completo)

**Plan completo:** `/opt/data/plans/SOP-CONEXION-CLIENTES-GOOGLE.md` · **Skill de proceso:** `devops/client-connection-flow` (user-owned — pendiente `hermes curator adopt`).

- **externalId es clave única** — reconectar otra cuenta con el mismo nombre SOBRESCRIBE la anterior. 1 cuenta Google = 1 set `{slug}-{servicio}`; segundo correo = `-gmail2`, jamás reusar nombre.
- **G1 (en el gate, implementado en prod)**: `/go` sobre una conexión con `status: active` en el mapa devuelve error anti-sobrescritura; solo reconecta con `?force=1` explícito.
- **G2 `provision_client.py`**: colisiona slug contra mapa Y DB de AP antes de registrar; crea entries `pending` + link + borrador de correo + sync prod. `--force` AÑADE los servicios que falten SIN tocar los existentes (never overwrite — verificado con Nancy: gmail intacto, añadidos drive/calendar).
- **G3 `verify_connection.py <slug>-<svc>`**: descifra AP → refresh → resuelve cuenta REAL del `id_token` → compara vs mapa (🚨 si mismatch) → prueba funcional → marca `active` + sync prod. `--no-write` para auditoría.
- **G4 sync dev→prod**: cron `sync-connections-map` cada 30 min (5dacffbb1dbc, no_agent) — solo diff sha256 del mapa.
- Scripts corren como usuario `hermes` (docker exec root NO tiene las claves SSH prod).
- Pitfall decifrado AP: `{iv,data}` en HEX (no b64), key cruda utf-8 32B de `AP_ENCRYPTION_KEY`, librería `cryptography` (pycryptodome solo en sandbox).

## Email estándar de invitación (regla dura, corrección de Jonathan 28/08)

- **Remitente SIEMPRE `NeuralCrew Labs <captain@neuralcrewlabs.com>`** (buzón real de Google Workspace, MX smtp.google.com; conexión AP `neuralcrew-gmail` ACTIVE sirve para enviar vía Gmail API). NUNCA correos personales (jonathaun124, jemadiar1).
- **Firma: Jonathan Parra — Founder, NeuralCrew Labs.**
- **Formato ÚNICO** (plantilla de Chucho 28/08, 3 tarjetas con botón): cabecera oscura `NEURALCREW LABS` + dorado `#C9A227` + sello "MARKETING POWERED BY AI" → título "{Nombre}, conecta tu cuenta con NeuralCrew Labs" → intro con correo objetivo + nota de separación de cuentas → tarjetas: 1 Gmail (`#C0392B`), 2 Drive (`#1E8E3E`), 3 Calendar (`#1A73E8`) → ayuda "elige {email}" → firma Founder → pie institucional (Bogotá · 316 691 0728 · captain@).
- **Script oficial:** `/opt/data/scripts/send_client_invite.py --slug X --email Y --nombre Z [--empresa E]` (envía + imprime links). Piloto Nancy OK (message 1a04a73a5e26bb08) con QA de 7 checks contra la bandeja real (ver `references/email-qa-recipe.md`).
- Lección del incidente: el primer envío salió desde jonathaun124 con formato distinto y solo Gmail → Jonathan lo corrigió ("los correos de neural siempre salen de neuralcrew, firmado por mí como Founder, usa el formato de ayer con los 3 botones"). Antes del primer envío a un cliente con el template, confirmar remitente+formato; después el estándar no se pregunta.

- "No veo la conexión en AP" casi siempre es porque el flujo guardó en nuestro storage, no en AP. Explicar la diferencia ANTES de prometer.
- NPM sin credenciales UI: se puede insertar en su SQLite (`proxy_host`) pero **NPM no regenera el .conf** para filas a mano → escribir `/data/nginx/proxy_host/<id>.conf` manualmente + `nginx -t` + reload; conectar el upstream al network `nginx-proxy-manager_proxy` para ruteo cross-network.
- CERT Let's Encrypt sin NPM UI: `acme.sh --issue --dns dns_cf` con `CF_Token`/`CF_Zone_ID` (token de Cloudflare con permiso Edit zone DNS), copiar `fullchain.cer`→`fullchain.pem` y key a la ruta de letsencrypt del contenedor.
- Record: puerta desplegada en prod = `https://connect.neuralcrewlabs.com` → nginx (proxy_host 16) → `connect_server.py` :8648.

## Apex corporativo (landing estática en nginx, 29/08/2026)

- La verificación de Google re-rastrea el DOMINIO autorizado (`neuralcrewlabs.com`), no solo la homepage declarada. El apex era el Next.js de Jesús con login → "página protegida" rebota otra vez.
- Fix: `/opt/nc-landing/index.html` en el VPS prod, copiado a `nginx-proxy-manager:/data/www-static/index.html`, servido vía `/data/nginx/custom/server_proxy.conf` (include del proxy_host 3) con `location = / { root /data/www-static; try_files /index.html =404; }`.
- PITFALL CRÍTICO (causó incidente 29/08): NPM incluye `custom/server_proxy.conf` en **TODOS los proxy hosts** (15), no solo el apex. Un `location = /` sin guard por host reemplazó la home de wiki/docuseal/docs/etc. por la landing. SIEMPRE acotar: `if ($host !~* ^(www\.)?neuralcrewlabs\.com$) { rewrite ^ /__nc_apex_static__ last; }` + `location = /__nc_apex_static__ { include conf.d/include/proxy.conf; }` para que cada subdominio recupere su upstream.
- `/login`, `/_next/*`, `/api/*` siguen proxyeados al Next (neuralcrew-landing:9003) — cero riesgo para el build de Jesús. Revert = borrar `server_proxy.conf` + reload.
- connect_server.py ahora implementa `do_HEAD` (antes 501 → crawler de Google choca). Backup pre-cambio: `connect_server.py.bak-20260829-scopes`.

## Scopes reales de las piezas de AP (verificado 29/08/2026)

Las piezas de AP definen sus scopes en la authorization URL — **no se pueden overridear** (el endpoint `/api/v1/app-connections/oauth2/authorization-url` ignora el parámetro `scope`). La lista que el usuario ve durante el consent = scopes de las piezas.

| Pieza | Scopes en auth URL |
|---|---|
| piece-gmail | `gmail.send` + `gmail.readonly` + `gmail.compose` + `email` |
| piece-google-drive | `drive` (COMPLETO) |
| piece-google-calendar | `calendar.events` + `calendar.readonly` |

**Scopes a declarar en OAuth consent screen (7 scopes):**
```
openid
https://www.googleapis.com/auth/userinfo.email
https://www.googleapis.com/auth/gmail.send
https://www.googleapis.com/auth/gmail.readonly
https://www.googleapis.com/auth/gmail.compose
https://www.googleapis.com/auth/drive
https://www.googleapis.com/auth/calendar.events
https://www.googleapis.com/auth/calendar.readonly
```

**Pitfall:** el callback del gate (linea `scope` en POST /api/v1/app-connections) envía scopes como metadata a AP — pero el token real tiene los scopes del auth URL. El callback puede enviar un SUBSET pero no scopes nuevos. `email` en el callback de Drive/Calendar no se concede (no está en el auth URL) pero no causa error.

**Nota:** `gmail.modify` NO está en el auth URL de la pieza Gmail — no se puede usar sin modificar la pieza AP. `drive.readonly` TAMPOCO está — la pieza Drive pide `drive` completo. Si se quiere minimizar, hay que fork/overridear las piezas AP (futuro).

## Requisitos de verificación de Google (app no verificada, 29/08)

Al verificar la app en Google Search Console/OAuth, Google exige en la homepage:
1. **Explicar el propósito de la app** en la página principal (qué hace, qué servicios conecta, para qué).
2. **Nombre de la app = nombre en la homepage**: el "App name" del consent screen debe coincidir EXACTAMENTE con el nombre visible en la landing (NEURALCREW LABS).
3. Links a **/terms** y **/privacy** funcionando (200, contenido real) — enlazados también desde el footer de la landing.
Fix aplicado: h1 "Conecta tu cuenta con NeuralCrew Labs" + párrafo de propósito + footer con links legales. El "App name" se cambia en Console → OAuth consent screen (manual del usuario).

## Referencias

- `references/puerta-conexion-neuralcrew-2026-08.md` — deploy real: files, proxy, cert, client OAuth, token_storage.
- `references/email-qa-recipe.md` — QA del correo de invitación contra la bandeja real (7 checks, Gmail API).