# Caso: Hermes Desktop no arranca (nodo Tailscale offline) — 2026-09-11

## Síntoma

`desktop.log` de Windows: bucle de

```
[boot] Resolving Hermes backend
[boot] Desktop boot failed: Could not reach the remote Hermes gateway while refreshing its WebSocket ticket. Try reconnecting.
```

tras ~13 s. Variante cuando la sesión SÍ caducó (mensaje distinto, arreglo distinto):
`Your remote gateway session has expired. Open Settings -> Gateway and click "Sign in" again.`
→ esa se arregla con **Sign in**, no tocando red.

## Arquitectura del caso

- Desktop remoto = cliente Electron que habla con un **dashboard/serve del host** en una IP del tailnet
  (`http://100.86.8.81:9112`), no con un servicio público.
- El boot hace: resolver backend → probe HTTP → **POST `/api/auth/ws-ticket`** (bootstrap del WebSocket, single-use, TTL 30 s) → WS. El fallo del ticket = síntoma de que no hay camino al gateway.
- El gateway corría como unit systemd: `hermes dashboard --host 0.0.0.0 --port 9112 --skip-build` con `HERMES_HOME=/root/hermes-agent-legacy-docker/data`.

## Diagnóstico que resolvió (orden)

1. **Servicio sano:** proceso del host escuchando (`/host/proc` + netns del host) y
   `curl -s -o /dev/null -w '%{http_code}' http://<ip>:9112/login` → **200** en 0.03 s;
   `POST /api/auth/ws-ticket` sin cookie → **401** (existe y exige sesión).
2. **Otras máquinas sí entraban:** `dashboard-auth.log` mostraba `ws_ticket_minted` de otra IP horas antes ⇒ no es el servicio.
3. **Fingerprint del cliente:** los 4 `[native-oauth] loopback listening` del `desktop.log` casaron exactos con los 4 `native_authorize_start` desde una sola IP del tailnet ⇒ PC identificado (DNS `portatil-chucho`).
4. **Audit silencioso:** en las ventanas de fallo (10-sep 14:45 y 11-sep 09:14 UTC) **cero** eventos del gateway para esa IP ⇒ las peticiones no llegaban.
5. **Tailnet:** `tailscale status --json` → ese peer `Online=false`, `LastSeen` 15 días atrás; `tailscale ping` → *no reply*; el otro VPS tailnet respondía en 119 ms y `netcheck` OK ⇒ red Tailscale **sana**, ese PC **desconectado**. `KeyExpiry` futuro ⇒ no era llave vencida.

Conclusión: ni app ni server — el PC no estaba en el tailnet, así que la IP del gateway no existía para él.

## Checklist de arreglo entregado

1. Abrir Tailscale en el PC → `Connect` / `Sign in` con la cuenta del tailnet.
2. `tailscale status` conectado y `tailscale ip -4` con la IP esperada.
3. `Test-NetConnection <ip-gateway> -Port 9112` → `TcpTestSucceeded: True` (o `curl.exe http://<ip>:9112/login` → 200).
4. Si Tailscale dice conectado y el puerto no responde: firewall / otro VPN (kill-switch) bloqueando la interfaz.
5. Reabrir Desktop; si pide sesión → **Settings -> Gateway -> Sign in**.

## Prevención

- Admin console → Machines → dispositivo → **Disable key expiry**.
- Tailscale del PC: "Connect on start-up" / segundo plano (y unattended si se quiere antes del login).
- Mejor arquitectura: no colgar el Desktop de una **IP cruda del tailnet**; exponer el dashboard con hostname HTTPS + `dashboard.public_url` (auth ya puesta), o correr backend local para el perfil principal.
- Watchdog (cron) que avise cuando un peer del tailnet o el puerto del gateway se caiga.

## Trampas vistas

- Líneas `Connecting to remote Hermes backend` + `Remote Hermes backend is ready` **sin** ticket registrado en el server = descriptor cacheado, no sesión real. No contarlo como "conectó".
- "Could not reach ... WebSocket ticket" y "session expired" **parecen** el mismo problema y no lo son: mirar si hubo o no eventos en el audit.
