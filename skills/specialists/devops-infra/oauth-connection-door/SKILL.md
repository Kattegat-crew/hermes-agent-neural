---
name: oauth-connection-door
description: "Use when connecting client accounts through the OAuth door."
tags: [oauth, multi-tenant, activepieces, conexiones, credenciales]
---

# OAuth Connection Door (persistent multi-tenant connections)

## Qué hace

Diseña y depura el sistema de conexiones persistentes para agentes: hub OAuth multi-tenant en ActivePieces (AP) + MCP directo para API keys + una "puerta de conexión" (página/botón con marca propia) para que el CLIENTE autorice con un solo click, sin ver AP ni consolas técnicas. Incluye el modelo de gobierno que impide cruzar credenciales entre tenants.

## When to Use

- El usuario pregunta "cómo conectamos el correo de fulano", "integración de herramientas persistentes para los agentes", "cómo se conecta un cliente".
- Construir una página/botón "Conectar con <marca>" para onboarding de clientes (Gmail/Meta/Canva/ML/Amazon).
- Depurar flujos OAuth que fallan (popup que no abre, 400 de AP, "Acceso bloqueado" de Google).
- Asegurar que el agente de un cliente solo use SUS conexiones (multi-tenant).

## Arquitectura recomendada (Opción C híbrida)

1. **AP = hub OAuth multi-tenant** para lo que necesita OAuth por-cuenta: Gmail multi-cuenta, Meta, Canva, MercadoLibre, Amazon, Search Console. Cada tenant = una conexión separada; refresh token vive en Postgres de AP y se refresca solo.
2. **MCP directo = API keys / local**: Twenty (API key local), WhatsApp (gateway bridge), Engram, ElevenLabs, fal.ai. NO pasar por AP donde no hay OAuth multi-cuenta.
3. **Naming desde el día 1**: `{tenant}-{servicio}` (ej. `helmer-gmail`, `golden-meta-ads`, `jonathan-canva`, `neuralcrew-gmail`). Un vistazo a AP o al mapa dice de quién es cada cuenta.
4. **Mapa lógico en Engram** (`topic_key: connections-map`): tenant → conexión → dueño. Credenciales NUNCA en el mapa. Cualquier agente consulta el mapa antes de invocar; si falta, reporta — no adivina.

## Puerta de conexión para clientes (un click, bajo TU marca)

Flujo validado en NeuralCrew (2026-08):
1. Cliente recibe correo/WhatsApp con botón → página con marca (`connect.<dominio>`), NUNCA URL de AP.
2. Backend `start-connect` devuelve `authUrl` OAuth.
3. Navegador va a Google (UNA pantalla de consentimiento con TODOS los scopes que el agente necesita: `gmail.modify` + `calendar.events` + `drive.file` + `access_type=offline`).
4. Redirect a `<public>/callback` con code → backend intercambia, guarda refresh token, conexión lista.

### Pitfalls (aprendidos a golpes)

- **El SDK embed de AP necesita JWT real primero**: `activepieces.configure({ instanceUrl, jwtToken })` con JWT MCP OAuth firmado (HS256, 15 min TTL, `sub`/`projectId`/`platformId`, `aud: MCP_OAUTH_ACCESS`, `iss: activepieces`). Con `jwtToken` vacío/ausente → AP responde `400 FST_ERR_VALIDATION` (querystring redirect_uri/response_type/code_challenge undefined) y el frontend muestra "faltan authRequestId o code".
- **Si el embed se cuelga en el navegador, crúzate a flujo OAuth directo**: construye la authUrl tú mismo (`client_id`, `response_type=code`, `redirect_uri`, `access_type=offline`, `prompt=consent`, scopes). Más robusto que el popup y sigue siendo un click para el cliente.
- **Google "Acceso bloqueado / Error 400 invalid_request: redirect_uri=…"** = el OAuth Client no tiene esa redirect URI registrada en Google Cloud Console (Authorized redirect URIs). Config de una vez, NO es bug de código.
- **Client con marca para flujos de cliente**: crear "NeuralCrew Labs" (o la marca real), nunca reusar un client interno de dev ("Ragnar Gmail") — el consent screen muestra ese nombre al cliente.
- **Un solo consent con todos los scopes** supera a conexiones por-pieza de AP: el cliente autoriza una vez, no 3.

Detalle del debugging: `references/oauth-connection-door-debug.md`.

## Gobierno multi-tenant (quién puede usar cada conexión)

AP Community NO aísla conexiones entre tenants (Projects es premium). Layering:

1. SOUL.md (contrato) — cada perfil declara su identidad y prefijo permitido.
2. Mapa en Engram — consultar dueño antes de invocar.
3. Projects AP (premium, solo >~5 clientes o compliance).
4. Auditoría (health-check puede alertar uso cruzado).
5. **Wrapper `ap_call` (LA LEY)** — todo acceso pasa por un script que valida el perfil llamador contra el mapa y BLOQUEA antes de llamar si no es dueño; log de intentos permitidos y bloqueados.

"El SOUL es el contrato, la Capa 5 es la ley" — nunca confiar solo en el SOUL para correos reales/compliance. Evidencia 2026-08: `ap_call --connection neuralcrew-gmail` desde perfil `helmer` → `BLOCKED: perfil helmer no es dueño de neuralcrew-gmail` (exit 1). Detalle completo: `references/multi-tenant-connection-governance.md`.

## Límites de AP Community (self-hosted v0.82+)

Flows, tasks, conexiones y MCP ilimitados. Lo único premium relevante es Projects (workspaces con RBAC) — no hace falta si naming por tenant + perfiles Hermes resuelven el multi-tenant. Un solo admin crea todas las conexiones; el cliente solo hace click en "Permitir".

## Verification

- Probar enforcement: conexión ajena desde otro perfil → BLOCKED; conexión propia → llega a AP.
- **Auditar una conexión en vivo (sin UI de AP):** reusar los helpers del wrapper — `sys.path.insert(0,'/opt/data/scripts'); from ap_call import get_ap_jwt_secret, make_jwt`, firmar JWT con los ids de la entrada del mapa, y llamar el MCP (`http://100.73.30.29:8088/mcp`, header `Accept: application/json, text/event-stream`, método `tools/call` → `ap_list_connections`) para confirmar `status: ACTIVE` por externalId. Nota: `tools/list` solo devuelve herramientas `ap_*` de administración de flows — las acciones de Google reales se ejecutan dentro de un flow.
- **Responder "¿con qué correo estoy conectado?":** verificar DOS fuentes y reportar ambas — (a) perfil de Gmail con el token local refrescado (ver skill gws-shared-access), (b) entradas del dueño en `connections-map.json` (`cuenta` + `status`). El mapa es la fuente de verdad local; Engram guarda la copia canónica.
- End-to-end de la puerta: el click del cliente abre el consent de Google con los scopes correctos y el `code` llega al callback.
- El `connect-debug.log` con `{test:true}` en `/api/debug` confirma que el logger funciona antes de pedir al usuario reintentar.