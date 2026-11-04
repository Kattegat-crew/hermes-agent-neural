---
name: hermes-gateway-http-api
description: "Use when exposing the Hermes gateway HTTP API for login."
tags: [hermes, gateway, api-server, remote-login, sessions]
category: devops
---

# Hermes Gateway HTTP API (api_server)

Enable and diagnose the gateway's HTTP API adapter — the service the Hermes
Desktop (and any OpenAI-compatible frontend) uses for **remote-login** and
session listing. Without it, a remote desktop can show `Gateway ready` but
still get zero sessions.

## When to use

- "Hermes Desktop se conecta pero no carga sesiones / SESSIONS vacío".
- Necesitas exponer el gateway de Hermes a una UI externa (Desktop web,
  Open WebUI, LobeChat, ChatBox, etc.).
- Necesitas listar sesiones del gateway vía HTTP (`/api/sessions`).

## How it works

The `api_server` platform adapter (source: `gateway/platforms/api_server.py`)
serves:
- `GET /api/sessions` — list client-visible Hermes sessions
- `GET/PATCH/DELETE /api/sessions/{id}` and `/api/sessions/{id}/messages`
- `POST /api/sessions/{id}/chat[/stream]` — chat with a persisted session
- `POST /v1/runs...`, `/v1/chat/completions`, `/health`, etc.
- Canonical pointer is `http://<host>:8642/v1` + `API_SERVER_KEY`.

**CRITICAL guard:** the listener is ONLY enrolled if `API_SERVER_KEY` exists in
`/opt/data/.env` (or the process env) with **≥16 characters**. `API_SERVER_ENABLED=true`
alone is NOT enough — without a usable key the adapter never binds, via
`_has_usable_api_server_key()` in `gateway/config.py`. This is the #1 cause of
"connected, but SESSIONS empty" in the Hermes Desktop.

## Enabling (server-side fix)

Configure in `/opt/data/.env`:
```env
API_SERVER_ENABLED=true
API_SERVER_KEY=sk-<secrets.token_urlsafe(32)>   # REQUIRED, min 16 chars
API_SERVER_HOST=0.0.0.0                          # default is 127.0.0.1 (unreachable remotely) — must be 0.0.0.0 for Desktop
API_SERVER_PORT=8642
```

Then **restart the gateway** to apply `.env` changes (there is no hot-reload).
See `hermes-gateway-s6-ops` for the safe restart pattern on this VPS (cron
one-shot via s6 targeting `main-hermes`; NEVER `hermes gateway restart` inside
the live turn — it blocks and kills the session).

## Diagnostics

**What the gateway actually listens on** (no `ss`/`netstat` needed inside the
container): read `/proc/<gateway-pid>/net/tcp`, filter state `0A` (LISTEN):
```python
raw = open(f'/proc/{pid}/net/tcp').read().splitlines()[1:]
for l in raw:
    m = re.match(r'\s*\d+:\s*([0-9A-F]{8}):([0-9A-F]{4})\s+\S+\s+([0-9A-F]{2})', l.strip())
    if m and m.group(3) == '0A':
        print(int(m.group(2), 16))
```
The gateway PID comes from `ps -eo pid,cmd | grep "gateway run"`.

If port 8642 does NOT appear in the LISTEN set despite everything else
listening (9900 A2A, 8644 webhook, 3000 WhatsApp): the `api_server` was never
enrolled → API_SERVER_KEY missing. `Gateway ready` in the Desktop can still
come from those other listeners, so the surface looks "connected".

## Two non-gateway prerequisites (don't burn time on config alone)

1. **Host must publish port 8642 outward** (Docker port mapping / firewall).
   This is NOT the gateway's job. Verify from the host:
   `docker run --rm --pid=host --privileged alpine sh -c 'nsenter -t 1 -m -u -n -i netstat -tlnp | grep 8642'`
   If the host only publishes e.g. 3000, no config change will make remote
   Desktop reach 8642 — the container→host port must exist first.
2. **The Desktop must point at the reachable address**: `http://<public-IP-or-Tailscale>:8642`, and send the SAME `API_SERVER_KEY` as the token.

## Typical root-cause flow for "Gateway ready, no sessions"

1. Confirm 8642 is in the gateway's LISTEN set (`/proc/<pid>/net/tcp`). If absent → key missing → enable per above.
2. If listening but unreachable → check host port publishing (nsenter netstat) and firewall.
3. If reachable but the Desktop token mismatch → align `API_SERVER_KEY`.

## Related skills

- `hermes-gateway-s6-ops` — safe s6 restart pattern (referenced, do not own).
- `hermes-workspace-setup` — the Workspace web UI targets the same api_server contract (HERMES_API_URL + HERMES_API_TOKEN).

## Reference

- `references/desktop-remote-login-2026-08-20.md` — transcript real del
  diagnóstico en este VPS: estado del gateway, `/proc/<pid>/net/tcp` output,
  red del host (IPs, puertos publicados), y lo que quedó pendiente en red.