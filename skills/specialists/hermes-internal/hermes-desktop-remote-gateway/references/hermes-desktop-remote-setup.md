<!-- Caso absorbido por F6 lote 4 el 2026-09-23 desde `specialists/hermes-internal/hermes-desktop-remote-setup`.
     Contenido íntegro; original en
     `data/archive/F6_lote4_20260923-161107/absorbidas/`. -->

---
name: hermes-desktop-remote-setup
description: Use when setting up Hermes Desktop remote on a new PC.
version: 1.0.0
author: Ragnar
tags: [hermes, desktop, remote-gateway, tailscale, vps, new-pc]
---

# Hermes Desktop → Remote Gateway: connecting a NEW PC (validated setup)

Flujo validado 26/08/2026: PC nuevo (Windows) conectado por primera vez a un
Hermes `hermes serve` que corre en el VPS, vía Tailscale. Sirve para la primera
conexión en cualquier equipo nuevo.

## Modelo (la clave de todo)

- El Desktop en modo **Remote gateway** NO usa el API del gateway (8642) ni SSH.
  Se conecta a **`hermes serve`** (backend headless) que escucha en el puerto
  **9112** del HOST del VPS (`hermes-serve.service`, systemd).
- La auth es **HTTP basic**: usuario `desktop` + password de
  `/root/.hermes-serve.env` en el host. **Las llaves SSH no intervienen.**
  Un usuario que crea que "falta la clave SSH del equipo" está confundiendo
  terminal con Desktop — aclararlo de entrada.
- La URL del gateway remoto SIEMPRE es la IP Tailscale **del servidor**
  (`http://<ip-vps>:9112`), NUNCA la IP local del PC cliente.

## Prerrequisitos en el PC nuevo

1. Tailscale instalado y logueado con **la MISMA cuenta** que el VPS (mismo
   `@`, ej. `digitalexpresions1@`). Si está en otra cuenta/tailnet, la URL no
   resuelve y el Desktop se queda "pensando" sin pedir login.
2. Hermes Desktop instalado.

## Pasos

1. Verificar que el PC ya está en el tailnet del VPS (lado host):
   ```bash
   docker run --rm --pid=host --privileged alpine sh -c 'nsenter -t 1 -m -u -n -i tailscale status'
   ```
   El nombre/IP del PC nuevo DEBE aparecer bajo la misma cuenta.
2. Leer credenciales del serve (host):
   ```bash
   docker run --rm --pid=host --privileged alpine sh -c 'nsenter -t 1 -m -u -n -i cat /root/.hermes-serve.env'
   ```
3. En el Desktop: Settings → Gateways (globo) → tarjeta **Remote gateway**:
   - URL: `http://<ip-tailscale-del-vps>:9112`
   - Usuario: `desktop` · Password: la del paso 2
   - **Test remote** → **Save for next restart** → **Save and reconnect**.

## Verificación desde el host (serve sano)

```bash
nsenter -t 1 -m -u -n -i curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:9112/health       # 302 = OK
nsenter -t 1 -m -u -n -i curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:9112/api/sessions  # 401 = auth OK
```
- El 401 de `/api/sessions` es CORRECTO (no_cookie = la auth funciona).
- Si `curl` desde dentro del contenedor a la IP Tailscale da timeout (HTTP 000),
  NO significa que el serve esté caído — probar desde el namespace del host.

## Pitfalls

- **URL con la IP local del PC** → el Desktop nunca llega al servidor. La URL es
  la IP del VPS.
- **PC en otra cuenta Tailscale** → mismo síntoma: se queda "pensando", no pide
  credenciales. Fix: loguear el PC con la cuenta del VPS.
- **Dos PCs conectados a la vez** con la misma credencial → se pisan la sesión
  (token compartido). Un solo PC activo a la vez.
- Tras reiniciar `hermes-serve`, el Desktop pide re-login ("Lost connection /
  Remote gateway sign-in required") — es normal, sign out → sign in.

## Skills relacionadas (user-owned, profundización)

- `hermes-desktop-remote-backend` — backend serve, perfiles bots desde Desktop.
- `hermes-desktop-remote-connection` — diagnóstico de caídas de conexión.
- `hermes-desktop-remote-gateway` — guía ES con firma de logs del fallo típico.

## Referencias

- `references/nuevo-pc-2026-08-26.md` — caso real: checklist ejecutada con
  valores exactos del tailnet y credenciales.