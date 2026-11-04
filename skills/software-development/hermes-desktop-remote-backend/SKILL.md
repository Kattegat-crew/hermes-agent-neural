---
name: hermes-desktop-remote-backend
description: "Use when Hermes Desktop uses a remote hermes serve backend."
version: 1.0.0
author: Ragnar
tags: [desktop, serve, remote-gateway, perfiles, profiles, tailscale, vps]
---

# Hermes Desktop ↔ Remote `hermes serve` Backend

Operations territory: Hermes Desktop (native Electron) connected to a Hermes backend running on a remote VPS, and creating/repairing bot profiles from the Desktop UI. Verified 20/08/2026 on Hermes v0.20.4 Desktop ↔ VPS `hermes serve` v0.20.4, Tailscale link.

## Mental model (this is the key)

- **Hermes Desktop does NOT talk to the gateway's `api_server` (8642) for remote login.** It connects to the `hermes serve` process (headless backend) — in this stack a **host-native systemd service** `hermes-serve.service`, listening on `0.0.0.0:9112`. The gateway's `api_server`/webhook/A2A ports are a separate concern.
- `hermes serve` uses `HERMES_HOME` (host path like `/root/hermes-agent-legacy-docker/data`) as its data root — the SAME data (including `state.db`) as the container gateway, because the bind mount maps there. So the serve shows the same sessions/profiles the gateway creates.
- Remote connection is over this IP:port via Tailscale (`http://100.86.8.81:9112` in this ops). The Desktop shows the gateway sign-in dialog when the serve requires auth (username/password).

## Setup sequence (Desktop → remote serve)

1. Gateway settings → Connection mode = **Remote gateway**.
2. Gateway URL = `http://<serve-ip>:9112`. (The serve binds 0.0.0.0, so any public/Tailscale IP reachable.)
3. Auth: Session token or username/password (serve reads `HERMES_DASHBOARD_BASIC_AUTH_USERNAME`/`PASSWORD` + `HERMES_DASHBOARD_SESSION_TOKEN` from its env).
4. "Signed in" persists the token. Use **Save for next restart** so the remote stays the default and the Desktop stops trying to spin up a LOCAL embedded backend (which causes the "se ve 1s y se cae" loop).

## Failure table

| Symptom | Root cause | Fix |
|---|---|---|
| `unknown method: profiles.create` on Create Agent | Client/backend **version mismatch** — Desktop is newer than the remote serve; serve lacks the RPC. | Update the serve backend to match Desktop version, THEN restart `hermes serve` service (see below). |
| `agent init failed: Unknown provider 'custom:nan-builders'` | New profile references a provider by a name not declared in that profile's config (inherited a stale provider string). | Edit the bot (right-click → Edit profile) → set Provider to the real provider present (e.g. `NaN-Builders`), pick a Model (e.g. `deepseek-v4-flash`). |
| "Gateway ready" but no session list loads | Desktop is using the **local embedded backend** (This device) instead of the remote Primary gateway. | Gateway settings → make the remote gateway **Primary**; set "return to Sessions on last-used gateway" → ON. |
| Desktop flips to a `shared`-style profile after reconnect | After a serve restart the Desktop session is invalid; it re-syncs to whatever profile/gateway is now current. | Re-login to remote gateway (sign out → sign in), confirm you're on the intended profile (per-profile sessions are separate). |

## Restarting the remote serve backend (applies version/RPC changes)

The serve is a **host systemd service** — restarting it is the only way to apply a software update (the python process holds its version in memory):

```text
# from inside the container, to reach host systemd:
docker run --rm --pid=host --privileged alpine sh -c 'nsenter -t 1 -m -u -n -i systemctl restart hermes-serve'
```

Confirm new PID + that port 9112 is listening again; allow ~10-45s for the build to load before probing.

## Creating a new bot (profile) from the Desktop

1. **BOTS** tab → **New Agent** → fill Name/Title/Description.
2. **Clone from profile**: choose **`fresh`** (or "Fresh Profile (bundled skills)") to start clean. DO NOT clone `default` (it copies identity, skills, memory of the main agent). `shared` is a preexisting auxiliary profile, not a template.
3. "Create empty": leave UNCHECKED (want bundled skills). "Share keys & accounts": keep CHECKED so the new bot inherits the credentials.
4. After save, the profile appears under `profiles/<name>/` (config.yaml + profile.yaml + SOUL.md). Verify on the home path the serve uses. Edit a bot by **right-click → Edit profile**.

## Pitfalls

- **After a serve restart, the Desktop's saved gateway session is invalid — you'll see "Lost connection / remote gateway sign-in required".** Tell the user to sign back in; nothing is deleted.
- The `hermes-workspace-setup` skill describes the web workspace / dashboard (port 3000/9119) — NOT comparable to the Desktop↔`serve` link; don't confuse the two stacks.
- A bare RPC probe to `:9112/rpc` without auth returns an empty body — use `GET /api/status` (unauthenticated) to read the server version, not the RPC endpoint.
- **"Estoy en Hermes Desktop" NO significa ejecución local (verificado 28-oct).** Si el Desktop está conectado al gateway remoto, la sesión del agente sigue corriendo en el VPS (`hostname` muestra el host del VPS, ej. `vmi3151337`): `pwd`, `terminal`, filesystem y procesos son del SERVIDOR. Es imposible inspeccionar, diagnosticar o modificar el PC local del Admin desde esa sesión.
  - Patrón correcto cuando la tarea toca su equipo local: escribir un script **read-only** (PowerShell en Windows) que el Admin ejecuta él mismo, generando un reporte `.md` para adjuntar de vuelta al chat. Nunca pedirle que pegue secretos: el script solo emite máscaras (`sk-abc...xyz`) y **huellas SHA256** de las claves, para compararlas después contra las del entorno del servidor sin exponer valores.
  - Decir explícitamente al Admin dónde corre la sesión antes de proponer un plan "para tu equipo" — evita planes basados en una suposición falsa de ejecución local.