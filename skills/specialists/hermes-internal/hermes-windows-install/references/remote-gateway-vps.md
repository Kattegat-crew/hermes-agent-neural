# Remote gateway connect — Desktop "Connect to existing Hermes"

When the Desktop shows "Connect to existing Hermes" (Gateway URL + token or browser sign-in), the target is the agent gateway running on the VPS.

## Network topology (verified 2026-08-19)

| What | Value |
|---|---|
| VPS host (Tailscale) | 100.86.8.81 |
| Windows PC (Tailscale, Admin) | 100.102.79.4 (Brave CDP at :9222) |
| Hermes container | `hermes-agent`, command `["gateway","run"]` |
| Container | agent remote endpoint A2A JSON-RPC on **127.0.0.1:9900** — bearer auth, serves 'ragnar-neuralcrew' (`/health` → `{"status":"ok","agent":"ragnar-neuralcrew"}`) |
| Container | webhook platform on **8644** (`platforms.webhook.extra.secret: nc-webhook-2026-hmac`) |
| Container | WhatsApp bridge on **3000** (node bridge.js) |
| Container | dashboard (web_server) on **9119** |
| docker-compose | `/root/hermes-agent-legacy-docker/docker-compose.yml` (container mounts `/root:/root`, `/opt:/opt/host_opt`, docker.sock) — publishes ONLY `3000:3000` and `9119:9119` |

Public DNS: `hermes.neuralcrewlabs.com` is the planned gateway domain but does NOT resolve yet (planned Nginx Proxy Manager/Coolify reverse proxy exists only on paper).

## Why there is no URL yet for the Desktop

1. The agent endpoint (9900) binds `127.0.0.1` inside the container — not reachable from outside even if a port were published.
2. docker-compose does not publish 9900 (or 8644) on the host.
3. So any URL given now → connection refused. Do not hand out `http://100.86.8.81:9900` until the two changes below are done.

## Steps to expose (requires gateway restart — it cuts the live session briefly)

1. Change the A2A/agent adapter bind from `127.0.0.1` to `0.0.0.0` (config `platforms.*` / plugin a2a adapter).
2. Host side: add to `/root/hermes-agent-legacy-docker/docker-compose.yml` (`ports:` at the hermes-agent service) then `docker compose up -d hermes` on the host:
   ```
   - "9900:9900"
   ```
3. Restart the gateway (from host or docker, NOT from inside the gateway process).
4. Resulting URL: `http://100.86.8.81:9900` (Tailscale, so it works only from devices in the tailnet; use `tailscale serve` or the public domain for outside access).
5. The endpoint requires a bearer token (A2A "REMOTE (bearer auth)"): capture the API_SERVER_KEY / A2A bearer value from the container env/token store and give it to the user for the "token" field in the Desktop.

## Desktop connect flow expected

The Desktop's "Connect to existing Hermes" screen: enter base URL → it detects token vs browser sign-in. For a VPS gateway with custom providers (no Nous Portal), it will need the token path, NOT browser sign-in.

## Gotchas observed

- Editing docker-compose from inside the container is possible (mounts rw) but the container was already published; prefer running compose from the HOST.
- `hermes gateway restart` from inside the gateway gets blocked by the sandbox guard ("cannot restart the gateway from inside the gateway process") — always advise the Administrator to restart from the host shell.
- After any gateway restart, WhatsApp bridge takes ~30 s to reattach; Discord/Telegram connect after a few seconds.
- User prompt: give the final URL immediately and only then explain; do not make the Admin run three diagnostics first (see SKILL.md "Communication").