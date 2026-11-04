---
name: hermes-desktop-remote-connection
description: "Use when Hermes Desktop cannot reach the gateway."
tags: [hermes, desktop, gateway, serve, tailscale, troubleshooting]
---

# Hermes Desktop Remote Backend Connection

Use when a Hermes Desktop instance (on the user's device) connects to a backend on a
VPS/host and the connection fails, drops, or shows "Remote gateway sign-in required" /
"Lost connection to the gateway" — even though the base connection ("Gateway ready")
appears to work.

## Background — the three backends (do not confuse)

| Backend | Port | Serves | Where it runs |
|---|---|---|---|
| `hermes serve` | **9112** | Desktop remote sign-in (sessions UI, capabilities, messaging, artifacts, jobs) | host-native, often a systemd `hermes-serve.service` |
| Gateway HTTP API | 8642 | OpenAI-compatible `/api/sessions`, `/v1/...`; used by Workspace web UI | inside Docker gateway process |
| `hermes dashboard` | 9119 | config/API key management | binds 127.0.0.1 |

The **Hermes Desktop app connects to `hermes serve` (9112)**, not the gateway API
server (8641) and not the dashboard (9119). When diagnosing "Desktop can't see
sessions", target 9112 first.

`hermes serve` typical host cmdline:
```bash
/opt/hermes-venv/bin/python /opt/hermes-venv/bin/hermes serve --host 0.0.0.0 --port 9112 --skip-build
```
Auth is env-scoped, readable from `/proc/<pid>/environ` (redact values before sharing):
```
HERMES_HOME=<same-home-as-gateway>            # e.g. /root/hermes-agent-legacy-docker/data
HERMES_DASHBOARD_BASIC_AUTH_USERNAME=desktop
HERMES_DASHBOARD_BASIC_AUTH_PASSWORD=<pass>
HERMES_DASHBOARD_SESSION_TOKEN=<token>
```

## Diagnostic ladder (verify server BEFORE blaming the Desktop)

1. **Is `hermes serve` up & on the right port?** Host side (`nsenter` from container):
   ```
   nsenter -t 1 -m -u -n -i sh -c "systemctl is-active hermes-serve; netstat -tlnp | grep 9112"
   ```
   Healthy log signature after start: `HERMES_BACKEND_READY port=9112`. Check it reads
   the same `HERMES_HOME` (via `/proc/<pid>/environ`) as the gateway, so it shares `state.db`.

2. **Does the client reach it?** Have the user open `http://<host:port>/health` in a
   browser. Seeing the **Sign in page** (NOUS/RESEARCH-branded, "Public bind · Auth
   required") proves the network path works. A Tailscale identity here confirms the
   TLS/route is fine (their active device shows in `tailscale status`).

3. **Healthy-server signature (unauthenticated) — these are NORMAL, not errors:**
   ```
   GET /health        -> 200  (Sign in HTML page)
   GET /api/sessions  -> 401  {"error":"unauthenticated","reason":"no_cookie","login_url":"/login"}
   ```
   That 401 is the server working correctly. It means the backend is up and the only
   remaining issue is client-side auth/session, NOT a dead server.

4. **Is `state.db` actually there + non-empty?** On the shared home:
   ```
   ls -la <HERMES_HOME>/state.db          # size in the hundreds of MB is normal
   sqlite3 <HERMES_HOME>/state.db "select count(*) from sessions;"
   ```
   A populated `state.db` that the serve process points at means the sessions ARE
   served; empty client list = stale client session, not missing data.

## The sign-in flow

- First web hit to `/health` → browser shows dashboard login. That is the serve auth;
  **enter creds in the Hermes Desktop app, not the browser** — the browser tab is only
  a reachability probe.
- Desktop shows "Remote gateway sign-in required / Lost connection to the gateway"
  after a server restart → **"Sign out & sign in"**, re-enter URL + `desktop`/password.
- After re-login, wait 10–15 s for the session list to render if `state.db` is large.

## ⚠️ THE main pitfall — gateway + serve share `state.db`

The Docker gateway and host `hermes serve` are separate processes that BOTH open the
**same SQLite `state.db`** (via shared `HERMES_HOME`). If you restart both within
seconds of each other, the Desktop shows: connects briefly (you SEE the folder/session
list ~1 s) → then "Lost connection". That is the DB collision window, NOT a
network/credential fault.

**Fix / prevention:**
- Restart **sequentially** — finish one, confirm new PID + `HERMES_BACKEND_READY`, then
  restart the other with a gap (minutes).
- Known-good gateway restart targets s6 `main-hermes` (see devops skill
  `hermes-gateway-s6-ops`), not stale service names.
- Confirm both stable, then have the user "Sign out & sign in" and wait for the list.

## Scripts
- `scripts/hermes-serve-probe.sh` — host-side liveness + `state.db` probe for 9112.

## Reference
- `references/serve-case-vps-tailscale.md` — session end-to-end case: VPS + Tailscale
  fleet, which device connects, exact probe sequences and what each result meant.
- See also the protected user-owned `hermes-desktop-windows-troubleshooting` skill for
  Windows *installer* failures — a SEPARATE class from remote connection issues.