# Diagnóstico real (2026-08-20) — VPS hermes-agent

Escenario: el Hermes Desktop del Administrador (usuario Jesús Díaz) hizo
remote-login al gateway del VPS, mostró `Gateway ready` pero SESSIONS vacío y
opciones grises.

## Estado del gateway verificado

- `hermes gateway status` → ✓ Running (PID 3428, manual bajo s6 `main-hermes`).
- Socket LISTEN del PID (via `/proc/3428/net/tcp`, estado 0A):
  9900 (A2A, `GET /` → `{"status":"ok","agent":"ragnar-neuralcrew"}`),
  8644 (webhook, 404 en `/`), 3000 (WhatsApp bridge), 43679 (efímero/otro).
- **8642 NO estaba escuchando** → el adaptador api_server nunca se enroló.
- `/opt/data/.env`: `API_SERVER_KEY` AUSENTE (solo A2A_BEARER_TOKEN,
  WEBHOOK_SECRET). `API_SERVER_ENABLED=true` en config.yaml NO bastaba.

## Fix aplicado

En `/opt/data/.env` (script python desde execute_code):
```env
API_SERVER_ENABLED=true
API_SERVER_KEY=sk-<secrets.token_urlsafe(32)>   # nueva, ≥16
API_SERVER_HOST=0.0.0.0
API_SERVER_PORT=8642
```
Clave guardada aparte en `/opt/data/.api_server_key` (solo-servidor).

Reinicio programado vía cron one-shot `no_agent` (patrón s6):

## Quedó pendiente del lado red (no se resolvió en la sesión)

- El HOST solo publicaba el puerto 3000 (docker-proxy `0.0.0.0:3000`). El
  `8642` no estaba publicado hacia fuera → aunque el gateway quede escuchando,
  el Desktop externo no lo alcanza hasta que el host publique 8642 (Docker
  mapping / firewall) y Tailscale mapee. Esto es un requisito FUERA del
  gateway, hay que tocarlo a mano en el host.

## Datos de red del VPS (para el operador)

- IP pública: 91.93.3.250 (ethernto eth0). Tailscale: 100.86.8.81 (tailscale0).
- Ver puertos del host: `nsenter ... netstat -tlnp | grep 8642`.