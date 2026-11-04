# Diario de diagnóstico — Desktop remoto → VPS (2026-08-20)

Sesión real con Desktop v0.20.4 (+310) b5455fd contra `vps-dev-neural`.
Resultado: causa raíz identificada y pasos de remediación dados; la verificación
final de reconexión quedó pendiente del usuario.

## Contexto

- Usuario: Jesús Díaz, PC personal (`portatil-chucho`, Tailscale `100.116.169.91`).
- VPS: `vps-dev-neural` / `100.86.8.81`, IP pública host `147.93.3.250`.
- Hermes gateway corre en contenedor `hermes-agent` (s6, `main-hermes`).
- `hermes serve` corre EN EL HOST como `hermes-serve.service` (systemd).

## Comandos reales usados (host-side, vía docker socket)

```bash
# Estado del serve
docker run --rm --pid=host --privileged alpine sh -c \
  'nsenter -t 1 -m -u -n -i systemctl status hermes-serve'
# → active, HERMES_BACKEND_READY port=9112

# Listeners e IPs
docker run --rm --pid=host --privileged alpine sh -c \
  'nsenter -t 1 -m -u -n -i netstat -tlnp | grep 9112'
# → tcp 0.0.0.0:9112 LISTEN 1372193/python

# Env del proceso serve
docker run --rm --pid=host --privileged alpine sh -c \
  'nsenter -t 1 -m -u -n -i cat /proc/<pid>/environ | tr "\0" "\n" | grep -iE "HERMES|HOME=|PROFILE"'
# → HOME=/root/hermes-agent-legacy-docker/data, HERMES_HOME=/root/hermes-agent-legacy-docker/data
#   HERMES_DASHBOARD_SESSION_TOKEN, HERMES_DASHBOARD_BASIC_AUTH_USERNAME=desktop

# Credenciales (NO compartir; solo confirmar presencia)
docker run --rm --pid=host --privileged alpine sh -c \
  'nsenter -t 1 -m -u -n -i cat /root/.hermes-serve.env | sed -E "s/=(.*)$/=<set>/"'
# HERMES_DASHBOARD_BASIC_AUTH_USERNAME=desktop
# HERMES_DASHBOARD_BASIC_AUTH_PASSWORD=<set>

# Probes de salud
curl -s http://127.0.0.1:9112/api/status     # 200 JSON (versión 0.20.0)
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:9112/api/sessions  # 401 no_cookie

# state.db (compartido, mode WAL)
sqlite3 /root/hermes-agent-legacy-docker/data/state.db "PRAGMA journal_mode;"   # → wal
```

## Listener del gateway (contenedor) — para comparar

En `/proc/<gwpid>/net/tcp` (a través del sin socket en el contenedor):
- `9900`  A2A (`Agent-to-Agent`, `ragnar-neuralcrew`)
- `8644`  webhook platform
- `3000`  WhatsApp bridge
- `43679` puerto interno del gateway (no es el serve)

El api_server OpenAI del gateway (8642) NO estaba activo — `api_server_enabled:
true` en config.yaml pero faltaba `API_SERVER_KEY` en `.env`, que es el guard de
arranque de la plataforma `api_server`. NO afecta al Desktop (usa 9112).

## Firma exacta del log del Desktop (síntoma)

```txt
[2026-08-20T09:51:24.747Z] [hermes] [boot] Connecting to remote Hermes backend at http://100.86.8.81:9112
[2026-08-20T09:51:30.087Z] [hermes] [backend] serve supported ... C:\Users\Jesús Díaz\AppData\Local\hermes\hermes-agent
[2026-08-20T09:51:30.087Z] [hermes] Starting Hermes backend for profile "default" ...
[2026-08-20T09:51:38.154Z] [hermes] HERMES_BACKEND_READY port=56007       ← LOCAL embebido
[2026-08-20T09:51:38.234Z] ... could not read served dashboard token: 404 ... web UI disabled
[2026-08-20T09:20:22.102Z] [hermes] Cached remote Hermes backend failed liveness probe (1/3)
[2026-08-20T09:36:28.615Z] [hermes] Hermes backend for profile "default" exited (1)
```

El patrón "Remote backend ready → luego un local HERMES_BACKEND_READY por
perfil default → exit(1)" es la firma de la causa raíz: el Desktop levanta su
propio backend local a la vez que el remoto, y el crash del local tira la vista.

## Tailscale (multi-PC)

```
100.86.8.81     vps-dev-neural    linux   -
100.70.53.110   celu-joni         android offline, last seen 121d ago
100.102.79.4    jonathanpc        windows offline, last seen 1h ago
100.116.169.91  portatil-chucho   windows active; direct ...
100.112.47.126  portatil-joni     windows offline
100.73.30.29    vps-prod-neural   linux   -
```
Nota: `jonathanpc` estaba OFFLINE durante el incidente → no era el causante.
Siempre verificar `tailscale status` antes de culpar a otro equipo.

## Restart seguro del serve (no corta el turno)

```bash
docker run --rm --pid=host --privileged alpine sh -c \
  'nsenter -t 1 -m -u -n -i systemctl restart hermes-serve'
```
Sirve para limpiar un serve viejo/atascado SIN tocar el gateway (no interrumpe
la conversación actual).