---
name: hermes-desktop-gateway-support
description: "Use when Hermes Desktop cannot reach the remote gateway."
tags: [hermes-desktop, gateway, tailscale, websocket, diagnostico, dashboard, red, sesion]
license: Apache-2.0
metadata:
  author: "roshi"
  version: "1.0"
  tags: [hermes, desktop, gateway, tailscale, troubleshooting, dashboard]
---
# Hermes Desktop ↔ Gateway remoto: triaje y arreglo

Soporte de la topología NeuralCrew: **Desktop Windows → Tailscale → `hermes dashboard` del host dev (`http://100.86.8.81:9112`)**. Aplica igual a cualquier dashboard/gateway expuesto solo por IP del tailnet. Cubre boot fallido, `WebSocket ticket`, `session expired` y "¿está caído el gateway?".

## Activation Contract

- "Hermes Desktop no inicia / no conecta", pantalla de boot que falla.
- Mensajes: `Could not reach the remote Hermes gateway while refreshing its WebSocket ticket`, `Your remote gateway session has expired … Sign in again`.
- Hay que saber qué PC del equipo está conectada al gateway y cuál no.
- Sospecha de gateway caído y hay que probarlo con evidencia, no con corazonadas.

## Hard Rules (evidencia antes que hipótesis)

1. **La única fuente de verdad del lado servidor es** `/host/root/hermes-agent-legacy-docker/data/logs/dashboard-auth.log` (JSON por línea: `login_success`, `ws_ticket_minted`, `refresh_success`, `refresh_failure`, `session_verify_failure`, `native_*`, `ws_ticket_rejected`).
2. **Cero entradas server-side en el timestamp del fallo ⇒ las peticiones NUNCA llegaron** → es red (tailnet/firewall/otro VPN), no la app ni el gateway. Esta regla cerró el caso del 11-sep sin adivinar.
3. **No le creas al log del Desktop**: `Connecting to remote Hermes backend …` / `Remote Hermes backend is ready` pueden venir de un descriptor cacheado/pooled sin haber tocado la red. Valida con un `ws_ticket_minted` del lado servidor.
4. **Que el gateway responda a `curl` desde el host NO prueba que el cliente llegue**: loopback/host vs tailnet son rutas distintas. Prueba las dos.
5. Nunca imprimir secretos del gateway ni del `.env` del host.

## Mapa de errores → causa

| Mensaje en `desktop.log` | Qué significa | Acción |
|---|---|---|
| `Could not reach the remote Hermes gateway while refreshing its WebSocket ticket. Try reconnecting.` | El POST a `/api/auth/ws-ticket` falló a nivel de red (timeout de ~13 s en el paso `Resolving Hermes backend`). No llegó al gateway. | Red del cliente: Tailscale / firewall / VPN con kill-switch. |
| `Your remote gateway session has expired. Open Settings → Gateway and click "Sign in" again.` | El gateway SÍ respondió y rechazó la sesión (`refresh_expired`, `all_providers_rejected_rt`). | Sign in de nuevo en Settings → Gateway (flujo nativo, usuario `desktop`). |
| `could not read served dashboard token … 404 Headless backend (hermes serve) — use hermes dashboard` | Normal en backend headless; no es error. | Ignorar. |
| `Cached remote Hermes backend failed liveness probe (n/3)` | El backend remoto no responde desde esa PC. | Misma ruta que el ticket. |
| `Ignoring stale Hermes backend exit (1)` | Resto de un backend local previo. | Ignorar. |

Diferencia clave: **"could not reach" = no hubo respuesta (red)**; **"session has expired" = hubo respuesta y fue un rechazo de auth**. No mezclarlas al diagnosticar.

## Antes que nada: ¿el dashboard sirve el código actual?

Caso repetido 4 veces (oct-2026): el checkout se actualiza y el proceso `hermes dashboard`
sigue vivo con el código anterior. Se ve **idéntico a un problema de red** (no modelos, plugins
que no conectan, "can't reach that address", timeout de arranque) con el servidor sano por `curl`.

Regla: **si el dashboard responde en el host pero el Desktop no obtiene datos, primero compara
fecha de arranque del proceso vs. fecha del HEAD del repo** (`git log -1 --format=%ci`). Si el
proceso es más viejo que el HEAD, no hay nada que diagnosticar en la red: hay que relanzarlo.
Detalle, comandos y pitfalls en [references/dashboard-stale-code.md](references/dashboard-stale-code.md).

## Triaje (orden obligatorio)

1. **Gateway arrancado y sano (host):**
   ```bash
   for p in /host/proc/[0-9]*; do c=$(tr '\0' ' ' < $p/cmdline 2>/dev/null); \
     case "$c" in *"hermes dashboard"*) echo "$(basename $p) $c";; esac; done
   curl -s -o /dev/null -w 'login=%{http_code} %{time_total}s\n' http://100.86.8.81:9112/login            # 200 = vivo
   curl -s -o /dev/null -w 'ws-ticket=%{http_code}\n' -X POST http://100.86.8.81:9112/api/auth/ws-ticket # 401 = vivo, pide sesión
   ```
2. **Auditoría por cliente:** `python3 scripts/auth-log-summary.py` (conteo y último evento por IP) y `--ip <ip>` para la máquina sospechosa. ¿Hay eventos suyos en el minuto del fallo? ¿Cuándo fue su último evento?
3. **Identifica la máquina por huella** (cuando el usuario manda un `desktop.log` sin decir de qué PC es): correlaciona eventos nativos del log del Desktop (`[native-oauth] loopback listening …`) con los `native_authorize_start` que el gateway registró **con IP** — el número y los timestamps deben cuadrar exactos. Eso nombra la máquina.
4. **Estado del tailnet del host:** `bash scripts/host-tailscale-probe.sh` (self, peers con `Online`/`LastSeen`/`KeyExpiry`, `tailscale ping` a cada peer, y salud del 9112).
5. Si el peer del cliente sale `online=False` → **el arreglo es en esa PC, no en el servidor**. No toques el gateway.
6. Verifica el cierre del ciclo desde el servidor: debe aparecer `ws_ticket_minted` con la IP del cliente.

## Arreglo (lado cliente, Windows)

1. Tailscale en la bandeja: si dice `Logged out` / `Stopped` → **Connect / Sign in** con la cuenta del tailnet.
2. `tailscale status` conectado y `tailscale ip -4` devolviendo su IP del tailnet.
3. `Test-NetConnection 100.86.8.81 -Port 9112` → `TcpTestSucceeded: True` (o `curl.exe http://100.86.8.81:9112/login` → 200).
4. Si Tailscale dice conectado pero el puerto no responde: firewall de Windows o **otro VPN con kill-switch** bloqueando la interfaz de Tailscale. Permitir Tailscale y reiniciar.
5. Reabrir Desktop. Si pide sesión → Settings → Gateway → **Sign in**.

## Prevención (lo que se le propone al dueño)

- Admin console → Machines → `<nodo>` → **Disable key expiry** (revisar antes `KeyExpiry` en el probe; ej. `portatil-chucho` vencía 2026-10-04).
- En la PC: **"Connect on start-up"** / correr Tailscale en segundo plano (unattended si debe conectar antes del login). Clásico: la laptop arranca, Tailscale no se levanta, y el Desktop falla igual que si el nodo no existiera.
- Arquitectura mejor (enterprise): hostname **HTTPS público + `dashboard.public_url`** en lugar de la IP cruda del tailnet, o backend local en la PC para el perfil principal y el remoto como secundario. La IP cruda del tailnet es un punto único de fallo silencioso.
- **Watchdog**: cron en el VPS que revise peer online + puerto 9112 y avise por Telegram/WhatsApp. Habría pitado el 27-ago en vez del 11-sep.

## Pitfalls

- Un `tailscale status` a secas no dice si un peer está online: parsear `--json` y leer `Online` / `LastSeen` / `KeyExpiry` / `Expired`.
- `LastSeen` viejo **no** implica llave vencida: confirmar `Expired`/`KeyExpiry` antes de mandar al usuario a re-autenticar.
- Nodos Windows "registrados pero offline" (Tailscale sin correr) fallan idéntico a un nodo inexistente — el Desktop no distingue.
- Miles de `refresh_failure … all_providers_rejected_rt` son ruido de un Desktop dejado abierto con refresh token muerto; **no** son la causa del "could not reach".
- No acuses al version mismatch contenedor vs host sin evidencia: si otros clientes mintean tickets, el protocolo está bien.
- Si `skill_view` de un skill del perfil falla con `Permission denied` (symlinks ilegibles), usar la copia buena en `/opt/data/skills/<nombre>/`.

## Herramientas del skill

- `scripts/host-tailscale-probe.sh` — estado del tailnet del host visto desde el contenedor (usa el binario y el socket del host) + salud del gateway.
- `scripts/auth-log-summary.py` — resumen de `dashboard-auth.log` por IP / por evento. Sin dependencias.
- `references/desktop-gateway-case-2026-09.md` — caso resuelto completo, con evidencia y mapa de infra (peers, puertos, rutas, unidades systemd).

## Skills relacionados

- `hermes-gateway-ops` (catálogo compartido `/opt/data/skills/`) — operación del gateway del host (s6/docker, perfiles, allowlist, Desktop SSH).
- `docker-service-tailscale` — patrón general de exponer un servicio Docker por Tailscale (bind 0.0.0.0 + IP del tailnet).
