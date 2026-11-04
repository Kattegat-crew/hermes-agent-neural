# Debug de la puerta de conexión (caso NeuralCrew, 2026-08)

Transcripción del debugging real del flujo "Conectar con NeuralCrew" para una
conexión Gmail vía ActivePieces. Orden de los síntomas → causa → fix.

## Síntoma 1 — 400 FST_ERR_VALIDATION

```
{"statusCode": 400, "code": "FST_ERR_VALIDATION", "error": "Bad Request",
 "message": "querystring/redirect_uri Invalid input: expected string, received undefined,
 querystring/response_type Invalid input: expected string, received undefined,
 querystring/code_challenge Invalid input: expected string, received undefined"}
```

**Causa:** el SDK `activepieces.authorizeMcp()` se llamó SIN configurar la instancia
primero (`activepieces.configure({ instanceUrl })`), o con `jwtToken: ''`. AP entonces
recibe query params vacíos y los rechaza.
**Fix:** `activepieces.configure({ instanceUrl, jwtToken })` con un JWT MCP OAuth real
firmado (HS256, 15 min TTL — payload completo en el skill `activepieces-lead-automation`,
sección Implementation). El JWT lo genera un endpoint backend `/api/jwt` con
`AP_JWT_SECRET`; nunca hardcodear el secret.

## Síntoma 2 — "❌ Error: faltan authRequestId o code"

**Causa:** el frontend no recibió `authRequestId` del backend (`start-connect` falló,
normalmente por el mismo JWT ausente → AP devolvió 400) o el callback llegó sin `code`.
**Diagnóstico con datos:** exponer `/api/debug` que escriba a `connect-debug.log`
(probar con `{"test": true}` primero). Luego, cuando el usuario reintenta, el log dice
cuál eslabón se rompe:
- `authRequestId` vacío → el backend de start-connect falló (JWT de AP rechazado).
- `result: null` → el popup no devolvió nada (cerrado o Google no completó).
- `result` con otra shape → el code está en otro campo; extraer con tolerancia:
  `code` / `authorizationCode` / `accessToken`.

## Síntoma 3 — el botón "sigue pensando" (spinner infinito)

**Causa probable:** la authUrl no dispara la apertura del popup/pestaña (el SDK embed
se cuelga en algunos navegadores) o el popup está bloqueado.
**Test que separa navegador de backend:** click derecho → "abrir en pestaña nueva".
Si la URL de Google abre (aunque la página quede "pensando") → backend OK, fix del
popup. Si ni la pestaña abre → la URL no dispara.
**Fix definitivo en este caso:** abandonar el SDK embed y usar **flujo OAuth directo**:
`start-connect` construye la authUrl (client_id, response_type=code, redirect_uri,
access_type=offline, prompt=consent, scopes) y el navegador navega directo a Google.

## Síntoma 4 — "Acceso bloqueado: error de autorización" (Google)

```
You can't sign in to this app because it doesn't comply with Google's OAuth 2.0 policy...
Error 400: invalid_request  Detalles: redirect_uri=http://100.73.30.29:8648/callback
```

**Buena noticia camuflada:** confirma que frontend + backend + Google reconocen el
flujo; solo falta registrar la redirect URI en el OAuth Client (config de una vez en
Google Cloud Console → APIs & Credentials → Authorized redirect URIs).
**Decisión de producto:** crear un OAuth Client NUEVO con la marca del producto
("NeuralCrew Labs") en vez de reusar el client interno de dev ("Ragnar Gmail"):
1. console.cloud.google.com/apis/credentials → + Create Credentials → OAuth Client ID
   → Web application.
2. Name = marca del producto; Authorized redirect URIs = `<public>/callback`.
3. (Recomendado) OAuth consent screen: declarar scopes `gmail.modify`,
   `calendar.events`, `drive.file` → el consent muestra "marca quiere: gestionar tu
   correo, calendario y archivos".
4. Actualizar `client_id` en el backend y probar de nuevo.

## Lecciones de patrón

- Instrumentar ANTES de pedir reintentos al usuario: un `/api/debug` que loguea el
  resultado del SDK convierte el siguiente intento en evidencia, no conjetura.
- El redirect URI del OAuth client debe coincidir EXACTO (incluye protocolo y puerto)
  con el que usa el backend; "localhost" vs IP pública es el clásico.
- Para producción usar subdominio con marca (`connect.<dominio>`) + nginx; el camino
  rápido (puerto directo vía socat sobre Tailscale) sirve para validar el flujo hoy.