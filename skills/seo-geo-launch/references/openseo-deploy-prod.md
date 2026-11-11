# Despliegue de servicio web en PROD detrás de NPM + SSO Pocket ID (receta verificada 09-nov-2026, OpenSEO)

## Principios
- Servicio persistente → PROD (169.58.189.222), compose independiente en `/opt/docker/<srv>` (NO Coolify; Coolify solo para apps con repo+CD).
- Web bind solo a `127.0.0.1:<port>` del host; el edge lo sirve todo.
- Números de archivo de proxy host NO son establemente mapeados a dominios: SIEMPRE leer el contenido del conf plantilla (`grep server_name`), nunca asumir "20.conf = X".

## Piezas
1. **CF DNS** (zona neuralcrewlabs.com id e9078af868fccbdccff63eea3e563d65): token writer = ítem vault "Cloudflare - API Token NeuralCrew", campo `CLOUDFLARE_MCP_TOKEN_WRITER:` de las notas (el del conector MCP solo tiene Zone/DNS Read → 403). `POST /zones/{z}/dns_records` A<ip> proxied=true. Universal SSL emite el edge para hostnames nuevos en minutos sin config extra.
2. **Cert LE**: dentro del contenedor `nginx-proxy-manager`: `/opt/certbot/bin/certbot certonly --dns-cloudflare --dns-cloudflare-credentials /data/cloudflare-creds.ini --cert-name <dom-con-guiones> -d <dominio> --key-type ecdsa --non-interactive --agree-tos`. Credenciales efímeras (umask 077, borrar después). Si `certbot renew` de NPM corre, hay lock: esperar (~2 min).
3. **Proxy host** `/data/nginx/proxy_host/<N>.conf` (N = max+1 tras ls): server 80→redirect; server 443 con cert propio; `location / { include /data/nginx/custom/forward_auth_guard.conf; proxy_pass http://172.19.0.1:<port>; }` y `include /data/nginx/custom/server_proxy[.]conf;`. **NO declarar `location /oauth2/`** en el host: server_proxy.conf ya los define (upstream docker `oauth2-proxy-universal:4180`); duplicar → `nginx -t` emerg duplicate location. `nginx -t && nginx -s reload`.
4. **Pocket ID SSO**: registrar `https://<dominio>/oauth2/callback` en client `universal-sso`: API key ítem vault "PocketID - API Key Terraform IaC", header **`X-API-Key`** (Bearer no). Campo real **`callbackURLs`** (camel; redirect_uris no existe). Método: `PUT /api/oidc/clients/universal-sso` con el objeto completo MENOS campos calculados (`credentials,hasLogo,hasDarkLogo,clientType,id`); PATCH → 404. Si el URI no está: authorize redirige a `/interaction/error?error=The redirect_uri...`.
5. **Verificación**: externo `curl -o /dev/null -w "%{http_code} -> %{redirect_url}" https://<dominio>/` → 302 a auth.neuralcrewlabs.com/authorize; app interna `127.0.0.1:<port>/api/health` 200; vecinos (`reels` 302, `vault` 200) sanos; `docker ps` diff solo los nuevos.
6. **Egress de este contenedor**: curl externo a ciertos dominios propios puede dar 000 (limitación local) — verificar SIEMPRE desde PROD real (`ssh root@169.58.189.222 curl ...`) o --resolve a IP pública antes de alarmarse.
7. **Discord bot directo** (leer/postear tickets sin Composio): token env **`DISCORD_BOT_TOKEN`** (no DISCORD_TOKEN) del proceso gateway en `scan /proc/*/environ` de ESTE contenedor (PID multiplex, ~937018); POST `discord.com/api/v10/channels/<thread_id>/messages` requiere header `User-Agent: DiscordBot (...)` — sin él, Cloudflare devuelve `error code 1010`. Nunca imprimir el token.

## Trampas verificadas 09-nov (re-auditoría)
- **504 con sesión SSO válida**: el compose oficial publica web en `127.0.0.1:${PORT}:80` (loopback puro) pero NPM proxía a `172.19.0.1:${PORT}` (gateway del bridge, patrón vault/reels) → sin listener → 504 SOLO tras autenticar (los tests sin sesión mueren en el 302 al login y nunca ejercitan el hop upstream). Fix: cambiar el bind a `172.19.0.1:${PORT:-3001}:80` (no expone al exterior) + recreate. **Regla general: verificar el hop proxy→upstream DESDE el contenedor NPM (`docker exec nginx-proxy-manager curl http://172.19.0.1:<port>/api/health`), no solo loopback del host.**
- **Telemetría**: el compose oficial NO declara `OPENSEO_TELEMETRY_DISABLED`/`DO_NOT_TRACK` — escribirlas solo en `.env` NO las inyecta (compose solo propaga lo declarado en `environment`). Fix: añadirlas a `services.{web,runtime,crawl-gateway}.environment` + `up -d`. Verificar SIEMPRE con `docker exec <ctr> env | grep TELEMETRY`, nunca con el .env.
- **Vaultwarden**: `vw` recortado a read-only desde 03-nov (solo get/list/env) y `bw unlock --passwordenv` del bot falla (cuenta `produccion@` queda locked) → `bw create item` = Cryptography error. Respaldo real: copiar .env a DEV `/opt/data/secrets/<srv>-prod.env` (600) + import Vaultwarden manual por UI. Escalar permisos de escritura del bot a Chucho.

## OpenSEO estado 09-nov (OP-1 done)
- `/opt/docker/openseo` v0.1.26, web 127.0.0.1:3001 → https://seo.neuralcrewlabs.com (conf 28). mem_limit 2g SOLO en runtime (así viene upstream).
- OP-2: Admin crea 1er admin (registro se cierra tras el alta). OP-3 proyectos/keywords (Heimdall). OP-4 GSC puerta NCL + DataForSEO gated. OP-5 dashboard/backups/skill (Roshi).
- Rollback: compose down + borrar conf + reload + borrar record + revertir callbackURLs.
