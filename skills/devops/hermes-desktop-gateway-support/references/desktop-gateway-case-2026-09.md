# Caso resuelto: Hermes Desktop no booteaba (11-sep-2026)

Síntoma del usuario: "Hermes Desktop no está iniciando en mi PC" + `desktop.log` (Windows).
Resultado: **el gateway estaba sano; el portátil del dueño llevaba 15 días fuera del tailnet.**

## Topología confirmada

- Desktop (Windows) se conecta al **backend remoto** `http://100.86.8.81:9112` (IP tailnet del VPS dev, host `vmi3151337`).
- Ese puerto lo sirve en el host: `hermes dashboard --host 0.0.0.0 --port 9112 --skip-build --no-open`
  (unidad systemd `hermes-serve.service`, `HERMES_HOME=/root/hermes-agent-legacy-docker/data`, venv `/opt/hermes-venv`, Hermes **v0.20.4**).
- Auth del gateway: provider `basic`, `user_id=desktop`, endpoints `/login` y `POST /api/auth/ws-ticket`.
- Auditoría: `/host/root/hermes-agent-legacy-docker/data/logs/dashboard-auth.log`.
- El contenedor de Roshi corre otra versión (v0.21.0) — irrelevante para el caso (otros clientes minteaban tickets).

## Evidencia que resolvió el caso

1. Gateway sano: PID del dashboard vivo desde 8-sep 19:18 (-05); `GET /login` → 200 en 0.03 s; `POST /api/auth/ws-ticket` → 401 (vivo, pide sesión).
2. Otros clientes entraban: `ws_ticket_minted` para `100.102.79.4` (JonathanPc) el 11-sep 02:37 UTC.
3. **Cero entradas server-side** para la máquina que fallaba en los timestamps de fallo (11-sep 09:14–09:17 UTC y 10-sep 14:45–15:17 UTC) ⇒ las peticiones nunca llegaron.
4. **Huella de máquina:** el `desktop.log` tenía exactamente 4 `[native-oauth] loopback listening` (20-ago 11:26:49 / 12:03:20 / 12:35:01 y 22-ago 20:48:07) y `dashboard-auth.log` tenía exactamente 4 `native_authorize_start` desde `100.116.169.91` en esos mismos timestamps ⇒ esa PC = **LAPTOP-2C38SCPF / DNS `portatil-chucho` / 100.116.169.91**. Su último evento: 27-ago 06:03 UTC.
5. Tailnet del host: `portatil-chucho` con `Online=False`, `LastSeen=2026-08-27T10:42Z`, `KeyExpiry=2026-10-04` (no vencida). `tailscale ping` a esa IP → *no reply*; al VPS prod (`100.73.30.29`) → pong en 119 ms ⇒ tailnet sana, peer caído.

## Trampa que casi llevó a mal diagnóstico

El `desktop.log` mostraba el 10-sep 12:03 y 12:35 `Connecting to remote Hermes backend … / Remote Hermes backend is ready`
**aunque el nodo ya estaba offline**: el lado servidor no registró ni un solo `ws_ticket_minted` en esa franja.
Ese "ready" venía de un descriptor remoto cacheado/pooled, no de la red. **Regla: el log del Desktop no prueba alcance; el `ws_ticket_minted` del servidor sí.**

## Mensaje de error y su significado

```
[boot] Desktop boot failed: Could not reach the remote Hermes gateway while refreshing its WebSocket ticket. Try reconnecting.
```
→ falló el HTTP POST del ticket a nivel red (13 s de timeout en el paso `Resolving Hermes backend`), con el stack en `gatewayTicketFailure` / `buildRemoteConnection` de `electron-main.mjs`.
Muy distinto de `Your remote gateway session has expired … Sign in again` (que aparece cuando el gateway responde rechazando la sesión — eso pasó el 20 y 22-ago y se resolvió con el Sign in nativo).

## Arreglo entregado al usuario (lado PC)

1. Tailscale → Connect/Sign in al tailnet.
2. `tailscale status` conectado + `tailscale ip -4` = 100.116.169.91.
3. `Test-NetConnection 100.86.8.81 -Port 9112` → True.
4. Si Tailscale OK y el puerto no: firewall de Windows / VPN con kill-switch.
5. Reabrir Desktop; si pide sesión → Settings → Gateway → Sign in.
6. Prevención: Disable key expiry del nodo, autoarranque de Tailscale, HTTPS público + `dashboard.public_url` o backend local, y watchdog de peer/9112.

## Peers del tailnet (2026-09-11, cambian con el tiempo)

| HostName | DNS | IP | OS | Nota |
|---|---|---|---|---|
| vmi3151337 | vps-dev-neural | 100.86.8.81 | linux | self, gateway dev :9112 |
| vmi3513784 | vps-prod-neural | 100.73.30.29 | linux | prod |
| JonathanPc | jonathanpc | 100.102.79.4 | windows | cliente Desktop activo |
| LAPTOP-2C38SCPF | portatil-chucho | 100.116.169.91 | windows | PC de Jesús (la del caso) |
| Mkt-Golde-Lucky | mkt-golde-lucky | 100.112.161.72 | windows | cliente Desktop |
| DESKTOP-S76R4NO | portatil-joni | 100.112.47.126 | windows | inactivo |
| Xiaomi 13T Pro | xiaomi-13t-pro | 100.71.104.32 | android | — |
| motorola edge 50 fusion | celu-joni | 100.70.53.110 | android | — |

## Rutas útiles en este host

- Logs del host: `/host/root/hermes-agent-legacy-docker/data/logs/` → `dashboard-auth.log`, `agent.log`, `errors.log`, `gateway.log`.
- Procesos del host desde el contenedor: `/host/proc/<pid>/cmdline` (con `tr '\0' ' '`), carga en `/host/proc/loadavg`.
- Docker del host accesible desde el contenedor (`docker ps`); `/host` es el root fs del host.
- Tailscale del host: binario `/host/usr/bin/tailscale` + socket `/host/run/tailscale/tailscaled.sock` (el binario Go corre desde el contenedor sin problema).
