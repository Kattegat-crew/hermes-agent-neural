# Deploy real: puerta de conexión NeuralCrew (prod, 26/08/2026)

## Stack desplegado

```
https://connect.neuralcrewlabs.com
  → Cloudflare DNS: A connect → 169.58.189.222 (proxied:false, TTL 300)
  → nginx-proxy-manager (proxy_host id 16, forward 172.19.0.5:8648)
  → contenedor hermes (connect_server.py :8648, Python http.server)
```

- Archivos: `/opt/data/workspace/connect-neuralcrew/` → `index.html`, `connect_server.py`, `token_storage.json`, `sessions/`
- Log: `/opt/data/logs/connect-server.log`; debug: `connect-debug.log` (cuando existió el endpoint)
- Cert: acme.sh en `~/.acme.sh/connect.neuralcrewlabs.com_ecc/` → copiar `fullchain.cer`→`fullchain.pem`, `connect.neuralcrewlabs.com.key`→`privkey.pem` en `/opt/docker/nginx-proxy-manager/letsencrypt/live/connect-neuralcrewlabs.com/`
- nginx .conf manual: `/opt/docker/nginx-proxy-manager/data/nginx/proxy_host/16.conf` (NPM no lo regenera para filas insertadas a mano)

## Google OAuth (project `neuralcrew-labs`)

- `client_id`: `288239405432-...biiufd8.apps.googleusercontent.com` (from Vault / GOOGLE_CLIENT_ID)
- `client_secret`: `GOCSPX-...` (from Vault / GOOGLE_CLIENT_SECRET)
- redirect: `https://connect.neuralcrewlabs.com/callback`
- scopes: `gmail.modify`, `calendar.events`, `drive.file` (access_type=offline, prompt=consent, PKCE S256)
- Modo Testing → Test users (jonathaun124@gmail.com, captain@neuralcrewlabs.com)

## Flujo del backend conectado

1. `POST /api/start-connect` → arma URL de Google con PKCE, guarda verifier por `state` en `sessions/<state>.json`
2. Usuario autoriza en Google → `GET /callback?code&state`
3. Backend hace token exchange a `https://oauth2.googleapis.com/token` (code + code_verifier)
4. Guarda `{access_token, refresh_token, expires_at, scope}` en `token_storage.json` bajo "google"
5. Los agentes usan `google_api.py` con ese storage (refresh automático)

## Aprendizajes del despliegue

- **Redirect URI con IP privada → Google lo rechaza** (`invalid_request ... must end with a public top-level domain`). Forzó el subdominio público + HTTPS.
- El intento previo con el SDK embed de AP (`authorizeMcp`) se colgaba sin respuesta → se descartó; OAuth directo a Google fue el camino que SÍ funcionó end-to-end.
- En AP solo se puede ver una conexión si se crea por su UI o embed SDK `connect()` — el storage nuestro NO aparece en AP (fue la confusión del cliente).
- Para conectar el correo del Comms Bot a AP realmente (flows) falta: UI de AP (Settings → Connections → Gmail → autorizar con captain@) o embed SDK con signing key.

## Enforcement (ap_call.py)

- `connections-map.json` soporta `owner` único o lista `owners: [comms, default, roshi]` para acceso compartido; perfiles fuera de la lista → BLOCKED exit 1.
- El contenedor prod debe tener la versión actualizada del script (`docker cp` hacia `hermes-agent:/opt/data/scripts/`) — el bind mount no siempre refleja de inmediato; verificar con `grep -c owners /opt/data/scripts/ap_call.py`.