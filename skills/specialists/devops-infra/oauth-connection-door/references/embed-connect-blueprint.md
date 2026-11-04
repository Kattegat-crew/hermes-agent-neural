# Blueprint: Embed SDK `connect()` para conexiones DENTRO de ActivePieces

Validado en el build de la puerta NeuralCrew (`connect.neuralcrewlabs.com`, 2026-08-26).
Objetivo: que el cliente autorice con un click bajo TU marca y la conexión nazca en AP
(no en storage propio), usable en flows de AP y visible en Settings → Connections.

## Por qué falló el primer intento (lección clave)

`activepieces.authorizeMcp({ authRequestId })` NO crea conexiones de app — crea un
token MCP para conectar un cliente de IA al proyecto. Por eso el embed original
mostraba el diálogo pero nada aparecía en AP. El método para conexiones de piezas
(auth cloud OAuth) es `activepieces.connect({ pieceName, connectionName })`.

## Arquitectura

```
Cliente → https://connect.<dominio>  ("Continuar con Google")
  → GET /api/jwt (backend firma JWT embebido tipo USER, HS256, AP_JWT_SECRET)
  → activepieces.configure({ instanceUrl, jwtToken })
  → await activepieces.connect({ pieceName, connectionName })  // por pieza
  → diálogo embebido OAuth → usuario autoriza en Google
  → AP guarda la conexión cifrada en su DB (Postgres) con externalId = connectionName
```

## JWT embebido (distinto del JWT MCP de la skill activepieces-lead-automation)

```json
{
  "sub": "<user_id de AP>",
  "platformId": "<platform_id>",
  "projectId": "<project_id>",
  "type": "USER",
  "tokenVersion": 1,
  "iat": <now>, "exp": <now + 3600>
}
```
Firma HS256 con `AP_JWT_SECRET`, `iss: activepieces`. Obtener los IDs:
`docker exec ap-db psql -U postgres -d activepieces -tAc "SELECT id FROM platform LIMIT 1;"`
(mismo para `project` y `"user"` — la tabla user va entre comillas). `tokenVersion`
se extrajo de la DB: sin él, AP rechaza el token.

## Una conexión por pieza

| Pieza | connectionName | Scopes que pide (consent screen de Google) |
|-------|----------------|---------------------------------------------|
| `@activepieces/piece-gmail` | `{tenant}-gmail` | gmail.send, gmail.readonly, gmail.compose, gmail.modify, email |
| `@activepieces/piece-google-drive` | `{tenant}-drive` | drive |
| `@activepieces/piece-google-calendar` | `{tenant}-calendar` | calendar.events, calendar.readonly |

El cliente autoriza 3 veces (correo, drive, calendar) la primera vez. Alternativa
si NO se exige vivir en AP: OAuth directo con un solo consent (3 scopes juntos) →
token en storage → agentes vía google_api.py.

## Checklist Google Cloud (una vez por proyecto)

1. Crear proyecto con la marca (ej. `NeuralCrew Labs`), NO el dev personal.
2. `OAuth consent screen`: External; app name = marca; support email + developer
   contact; **URLs públicas vivas**: homepage (`https://connect.<dominio>`),
   `/privacy`, `/terms` (generarlas con marca y contacto; Google rechaza el guardado
   si la URL no carga).
3. Habilitar las 3 APIs: Gmail API, Google Calendar API, Google Drive API.
4. Data Access (scopes): agregar los de la tabla de arriba (los pieces piden scopes
   específicos; habilitar APIs NO basta → `INVALID_CLOUD_CLAIM`).
5. Credentials → OAuth Client ID (Web): redirect URIs = `https://connect.<dominio>/callback`.
6. Test users: agregar las cuentas que probarán (estado Testing); pasar a Production
   cuando haya que abrirlo a clientes.

## Errores vistos y su causa

| Síntoma | Causa |
|---------|-------|
| `400 FST_ERR_VALIDATION` (redirect_uri/response_type/code_challenge undefined) | SDK `configure()` sin JWT válido (o con el JWT MCP en vez del USER) |
| `{"code":"INVALID_CLOUD_CLAIM","params":{"pieceName":"..."}}` | Scopes del piece no están en el consent screen de Google |
| Google "redirect no válido: debe terminar con dominio público" | redirect URI con IP privada (Tailscale 100.x) o IP pública → usar dominio + HTTPS |
| Popup/login se abre solo al cargar la página | autostart disparado por `?next=` residual → solo autoarrancar con `auto=1` real del callback |
| "Acceso bloqueado: error de autorización / invalid_request redirect_uri" | el Client no tiene la redirect URI registrada |

## Verificación

- `curl -s https://connect.<dominio>/api/health` → `{"status":"ok"}`.
- Click completo en navegador → las 3 conexiones `{tenant}-gmail/-drive/-calendar`
  aparecen en AP Settings → Connections con esos externalIds.
- `ap_call` con perfil dueño pasa; perfil ajeno → BLOCKED (Capa 5).

## Servidor de referencia

`templates/embed_connect.py` — incluye la página, `/api/jwt`, `/api/health`,
`/privacy` y `/terms`. Ejecutar con las env vars del encabezado del script.