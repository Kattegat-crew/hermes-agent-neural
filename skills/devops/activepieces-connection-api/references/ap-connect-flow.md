# Receta verificada end-to-end (26/08/2026)

Contexto real: puerta de conexión `connect.neuralcrewlabs.com` (dominio público, Cloudflare DNS A → 169.58.189.222, nginx-proxy-manager → contenedor hermes :8648, cert Let's Encrypt vía acme.sh dns_cf). AP self-hosted en `http://100.73.30.29:8088` (Tailscale), proyecto `4Bn3xmdg5sPj7l7Q2Sb1U`, usuario `b1rMkHVsoxa6nyPoUbMCp`, plataforma `j8utrJ21jBV2cbx75RHb7`, tokenVersion `M1Mfhw0U4FDzanLZ3ja0I`.

## Traza de la depuración (lo que NO funcionó y por qué)

| Intento | Resultado | Causa |
|---------|-----------|-------|
| `POST /mcp` con JWT `type:"mcp_oauth"`, sin `iss` | 401 Invalid/expired access token | JWT MCP requiere `iss:"activepieces"` + `Accept: application/json, text/event-stream` |
| `GET /v1/projects` (+token) | 200 pero HTML de la SPA | La API real es `/api/v1/`, no `/v1/` |
| JWT `{"type":"user"}` minúscula | 401 `invalid principal type` | `PrincipalType.USER = "USER"` en mayúsculas |
| JWT USER sin tokenVersion | 401 `invalid access token or session expired` | `assertUserSession` compara `identity.tokenVersion` con `decoded.tokenVersion` |
| JWT USER sin `iss` | verify falla | El signer de AP fija issuer activepieces |
| Llamada sin `X-Project-Id` | 401 `Cannot read properties of undefined (reading 'type')` | El security helper necesita el proyecto del header |

## Comandos/scripts verificados

### 1. Obtener el tokenVersion (Postgres de AP)

```bash
ssh root@<host-prod>
docker exec ap-db psql -U postgres -d activepieces -c 'SELECT id, "platformId" FROM "user"'
docker exec ap-db psql -U postgres -d activepieces -c 'SELECT "tokenVersion", verified FROM user_identity'
```

### 2. JWT válido + obtener authorization-url (probado OK)

```bash
# dentro del contenedor hermes (tiene /opt/data/.env con AP_JWT_SECRET)
cd /tmp && cat > ap_check.py <<'PY'
import json, time, hmac, hashlib, base64, urllib.request

def b64url(b): return base64.urlsafe_b64encode(b).rstrip(b"=").decode()

def make_jwt(secret, payload):
    h = {"alg":"HS256","typ":"JWT"}; now=int(time.time())
    payload["iat"]=now; payload["exp"]=now+604800
    s1=b64url(json.dumps(h,separators=(",",":")).encode())
    s2=b64url(json.dumps(payload,separators=(",",":")).encode())
    return f"{s1}.{s2}."+b64url(hmac.new(secret.encode(),f"{s1}.{s2}".encode(),hashlib.sha256).digest())

secret=""
for line in open("/opt/data/.env"):
    if line.startswith("AP_JWT_SECRET="):
        secret=line.split("=",1)[1].strip(); break

cm=json.load(open("/opt/data/connections-map.json"))
e=cm["neuralcrew-gmail"]
uid,pid,plid=e["ap_user_id"],e["ap_project_id"],e["ap_platform_id"]
tok=make_jwt(secret,{"id":uid,"type":"USER","platform":{"id":plid},
    "tokenVersion":"<user_identity.tokenVersion>","iss":"activepieces"})

body=json.dumps({"pieceName":"@activepieces/piece-gmail","projectId":pid,
    "clientId":"<google-client-id>","redirectUrl":"https://connect.dominio.com/callback"}).encode()
req=urllib.request.Request("http://100.73.30.29:8088/api/v1/app-connections/oauth2/authorization-url",
    data=body,headers={"Content-Type":"application/json","Accept":"application/json",
    "Authorization":f"Bearer {tok}","X-Project-Id":pid},method="POST")
with urllib.request.urlopen(req,timeout=20) as r:
    print(json.dumps(json.loads(r.read()),indent=2)[:500])
PY
python3 ap_check.py   # → authorizationUrl de Google (con state de AP)
```

### 3. Enviar el code al callback → conexión guardada en AP

POST `/api/v1/app-connections` con el body CLOUD_OAUTH2 del SKILL.md usando el `code` del callback de Google. Respuesta 201/200 con `{externalId, displayName, ...}`. La conexión aparece ACTIVE en `ap_list_connections` y en Settings → Connections de la UI.

## Puerta white-label (arquitectura que quedó probada)

```
[Botón "Continuar con Google"] 
  → backend POST /api/start-connect → AP authorization-url
  → redirige a Google (misma pestaña; NO popup del SDK embed)
  → Google callback → /callback?code&state → backend POST /api/v1/app-connections
  → conexión en AP
```

- Frontend: index.html con botón + `window.location.href = data.authorizationUrl`. Sin SDK de AP (se colgaba).
- Backend: `connect_server.py` (http.server) en :8648 dentro del contenedor hermes; sirve HTML + /api/start-connect + /callback.
- Exposición: registros DNS A (Cloudflare, DNS-only) + proxy_host manual en NPM + cert LE. Detalle NPM: si no hay credenciales de la UI, insertar fila en `database.sqlite` (proxy_host id) y **escribir el .conf a mano** en `data/nginx/proxy_host/<id>.conf` siguiendo el formato de los existentes (NPM solo regenera sus propias filas en restart). Conectar el contenedor backend a la red de NPM (`docker network connect nginx-proxy-manager_proxy <contenedor>`) y usar la IP en esa red como forward_host.
- Google OAuth Client (project "neuralcrew-labs"): redirect URI debe ser el dominio público HTTPS (`https://connect.dominio.com/callback`); IPs privadas rechazadas. Modo Testing requiere agregar test users.