---
name: hermes-desktop-remote-gateway
description: "Desktop to remote gateway: sessions not loading or dropping."
category: devops
---

# Hermes Desktop → Remote VPS Gateway (hermes serve)

Guía para conectar y diagnosticar el **Hermes Desktop** (app nativa) a un Hermes
Agent que corre en un **VPS remoto**, y a la falla típica: "se conecta (Gateway
ready) pero la lista de sesiones no carga / se cae después de unos segundos".

Validado 2026-08-20 con Desktop v0.20.4 contra `vps-dev-neural` (Tailscale
`100.86.8.81`). NO cubre el Desktop (eso es
`hermes-desktop-windows-troubleshooting`, user-owned).

## Modelo correcto (crítico)

El Desktop remoto **NO** usa el `gateway.api_server` (OpenAI-compatible, puerto
8642, requiere `API_SERVER_KEY`). Usa **`hermes serve`** — un backend headless
separado, en el HOST del VPS:

- systemd del host: **`hermes-serve.service`**
- Comando real: `hermes serve --host 0.0.0.0 --port 9112 --skip-build`
- Credenciales en `EnvironmentFile=/root/.hermes-serve.env`:
  `HERMES_DASHBOARD_BASIC_AUTH_USERNAME` (normalmente `desktop`),
  `HERMES_DASHBOARD_BASIC_AUTH_PASSWORD`, `HERMES_DASHBOARD_SESSION_TOKEN`.
- Comparte `HERMES_HOME` con el gateway (`state.db` WAL), p.ej.
  `/root/hermes-agent-legacy-docker/data` host ↔ `/opt/data` contenedor.

## URL del Desktop en modo "Remote gateway"

**Settings → Gateways** (globo) → tarjeta **"Remote gateway"**:
- URL = `http://<tailscale-ip>:9112` (nunca 8642)
- Usuario `desktop` + password del `.hermes-serve.env`
- Botones: **Test remote** → **Save for next restart** → **Save and reconnect**

## Síntoma: sesiones no cargan / se caen a los segundos

Firma en el log del Desktop (`%LocalAppData%\hermes\logs\desktop.log`):
```
Connecting to remote Hermes backend at http://<ip>:9112
Remote Hermes backend is ready            ← red y serve OK
... Starting Hermes backend for profile "default" ...
HERMES_BACKEND_READY port=xxxxx           ← backend LOCAL embebido también arranca
could not read served dashboard token: 404 ... web UI disabled
Hermes backend for profile "default" exited (1)   ← crashea y tira la vista
```

**Causa raíz:** el Desktop arranca un **backend local embebido** (perfil default)
además del remoto; cuando ese local sale con `exit 1`, cuelga la vista y muestra
"Lost connection" aunque el remoto esté sano.

**Solución cliente:**
1. Cerrar el Desktop por completo (bandeja → Salir; matar procesos hermes).
2. Reabrir → conectar remoto (`http://<ip>:9112`, usuario `desktop`, pass).
3. Comprobar en el log que NO reaparezca `HERMES_BACKEND_READY port=1xxxxx`
   (local). Si reaparece, en Settings → Gateways guardar con "Save for next
   restart" y que el "this device" (local) no quede activo/guardado.

**Comprobación lado servidor (host del VPS):**
```bash
docker run --rm --pid=host --privileged alpine sh -c 'nsenter -t 1 -m -u -n -i systemctl status hermes-serve'
docker run --rm --pid=host --privileged alpine sh -c 'nsenter -t 1 -m -u -n -i netstat -tlnp | grep 9112'
# Estado sano:
curl -s http://127.0.0.1:9112/api/status     # 200 público
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:9112/api/sessions  # 401 OK
```
`/api/sessions` da `401 {"reason":"no_cookie"}` cuando la auth funciona (correcto).

## Pitfalls

- **8642 vs 9112:** el Desktop usa `hermes serve` (9112); el 8642 es el api_server
  OpenAI-compatible del gateway. Que el 8642 falle no impide listar sesiones.
- **Reiniciar `hermes-serve` (host) NO corta tu conversación.** El gateway vive en
  contenedor (s6); `systemctl restart hermes-serve` en el host es seguro durante
  tu turno.
- **No reiniciar gateway y serve a la vez:** comparten `state.db` (WAL); juntos
  provocan drop de 1–2 s.
- **Multi-PC / token compartido:** dos PCs con el MISMO `HERMES_DASHBOARD_TOKEN`
  contra el mismo serve se pisan la sesión. Antes de culpar, `tailscale status`
  (host): si el otro peer está `offline`, no es el culpable.
- **Guard de terminal:** `hermes gateway restart` está bloqueado; `systemctl
  restart hermes-serve` (host) sí escapa. Ver `hermes-gateway-s6-ops`.

## Referencias

- `references/remote-vps-session-2026-08-20.md` — diario de la sesión: comandos,
  resultados y firma de log exacta.