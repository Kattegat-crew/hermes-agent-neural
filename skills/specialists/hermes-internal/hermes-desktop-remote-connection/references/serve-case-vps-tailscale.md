# Case: Hermes Desktop → VPS serve (Tailscale) — end-to-end diagnosis

Validated 2026-08-20 on the NeuralCrew VPS (`vps-dev-neural`, Linux, Docker container
`hermes-agent` inside, host native services outside). Symptom the user reported:
installed Hermes Desktop, remote-signed-in, but sessions/options did not load.

## Fleet topology (Tailscale, from `tailscale status`)

| Device | IP | State |
|---|---|---|
| vps-dev-neural | 100.86.8.81 | host (the serve backend) |
| jonathanpc | 100.102.79.4 | windows, offline |
| **portatil-chucho** | **100.116.169.91** | windows, **active; direct 186.30.47.250:56840** |
| portatil-joni | 100.112.47.126 | windows, offline |

The user's Desktop connected via `http://100.86.8.81:9112` (Tailscale IP, not the public
IPv4). Their active laptop showed up in `tailscale status` as connected.

## What the three candidate ports were doing (on the HOST, via nsenter)

- `:9900` → A2A (returns `{"status":"ok","agent":"ragnar-neuralcrew"}` at `/`)
- `:8644` → webhook platform (404 at `/`)
- `:3000` → WhatsApp bridge (Express 404 at `/`)
- `:9112` → **`hermes serve`** — the Desktop backend. `0.0.0.0:9112` LISTEN.
- `:9119` → dashboard (docker-proxy)
- gateway API `8642/8645` → NOT listening (api_server requires an `API_SERVER_KEY`; this
  VPS had none, so the gateway HTTP API did not bind). Not required for the Desktop,
  which uses `serve`.

## Important distinction learned

The Desktop does NOT consume the gateway's OpenAI-compatible API server. It connects to
`hermes serve`. Enabling `API_SERVER_KEY` / `API_SERVER_ENABLED` in `.env` only matters
for the Workspace web UI / OpenAI-compatible frontends — it is not the Desktop path.

## The serve service (host native)

```
service: hermes-serve.service  (systemd, enabled)
cmdline: /opt/hermes-venv/bin/python ... hermes serve --host 0.0.0.0 --port 9112 --skip-build
env:     HERMES_HOME=/root/hermes-agent-legacy-docker/data   (SAME home as gateway -> same state.db)
         HERMES_DASHBOARD_BASIC_AUTH_USERNAME=desktop
         HERMES_DASHBOARD_BASIC_AUTH_PASSWORD=<pass>
         HERMES_DASHBOARD_SESSION_TOKEN=<token>
log ok:  HERMES_BACKEND_READY port=9112
```

## Probe sequence that verified a HEALTHY server

Unauthenticated probes (all returned the expected healthy signatures, NOT errors):

```
GET /health        -> 200  (returns the "Sign in" HTML: NOUS/RESEARCH, "Public bind · Auth required")
GET /api/sessions  -> 401  {"error":"unauthenticated","detail":"Unauthorized","reason":"no_cookie","login_url":"/login"}
```
The `state.db` on the shared home held 329 sessions (`sqlite3 ... "select count(*) from sessions;"`)
and was ~156 MB. So the backend was serving correctly the whole time; the client-side
session had simply gone stale after a restart.

## The actual root cause of "Lost connection"

| Time | Action |
|---|---|
| 04:18 | unconditional `s6-svc -r /run/service/main-hermes` gateway restart (cron no_agent) applied API_SERVER config |
| 04:19 | `systemctl restart hermes-serve` (host) — performed only minutes after the gateway bounce |
| → | Both processes briefly bounce on the SAME `state.db` → Desktop shows "Remote gateway sign-in required / Lost connection" |

On retry, the user's Desktop briefly SHOWED the VPS folders/session list (~1 s) then
dropped — consistent with the shared-DB collision window, not a dead server. No error
in `journalctl -u hermes-serve --since <restart>`; `ps` showed a stable new PID.

## Cleared sequence

1. Restarted `hermes-serve` alone (`systemctl restart hermes-serve`); new PID, active,
   `HERMES_HOME=/root/hermes-agent-legacy-docker/data`, listening `0.0.0.0:9112`.
2. Confirmed both probes above returned the healthy signatures.
3. Desktop "Sign out & sign in", re-entered `desktop`/`<pass>` against
   `http://100.86.8.81:9112`, waiting 10–15 s for the ~156 MB session list.

## Lessons worth carrying forward

- Verify the server first with the two unauthenticated probes; a `401 no_cookie` on
  `/api/sessions` is a HEALTHY server, not a fault.
- The Desktop port is 9112 (`hermes serve`), not the gateway API 8641 nor dashboard 9119.
- Avoid restarting the gateway container and the host `hermes serve` back-to-back —
  they share `state.db`. Sequence them.
- The browser "Sign in" page is a fetch probe, not the place to authenticate the Desktop.
- Enabling `API_SERVER_KEY` changes `.env` on the VPS; it does NOT make the Desktop load
  sessions (that's the gateway API server, a different path). The Desktop needs `serve`.