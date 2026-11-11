---
name: web-portal-deploy
description: Use when publishing a web app behind the agency SSO/vhost.
version: 1.0.0
author: Ragnar
license: internal
metadata:
  hermes:
    tags: [deploy, nginx, sso, systemd, telegram]
    related_skills: [hermes-agent]
---

# Web Portal Deploy (SSO + systemd)

## When to Use

- The boss asks for an internal tool to be "visible" / reachable at a URL (portal, dashboard, task board, ledger view).
- Any task that publishes a new subpath on an existing PROD vhost behind Pocket ID SSO, or runs a small helper app/service on DEV.
- Any task that surfaces a live store (tasks, alerts, KPIs) as a Telegram pinned message.

Do NOT use for client-facing marketing sites (NeuralCrew Web territory) or for ActivePieces flows.

## Architecture (use this shape)

```
navegador ──HTTPS──> nginx-proxy-manager (PROD :443, vhost existente)
                     │  auth_request /oauth2/auth  (Pocket ID, grupo admins)
                     │  location ^~ /<subpath>/
                     ▼
          http://<DEV-tailscale-ip>:<puerto>   ← bind solo a la IP de Tailscale
                     │
              app como systemd service (DEV)
```

Rules:
- The app **binds to the DEV Tailscale IP only** (e.g. `PORTAL_BIND=100.86.8.81`), never `0.0.0.0`. The vhost is the only public door.
- **No new vhost, no new domain.** Reuse the existing PROD vhost with a `location ^~ /<subpath>/` block — one subpath per internal app.
- SSO is inherited from the vhost: `auth_request /oauth2/auth` + oauth2-proxy already in place. The user's identity arrives as `X-Auth-Request-Email`; read it server-side for the actor, fall back to `local` only when the header is absent (localhost testing).

## Steps

1. **Read the vhost config on disk before editing** — `ssh prod` and read the target `proxy_host/N.conf`. Never assume its shape from memory.
2. **Back up the conf with a timestamp suffix** (`N.conf.bak-<feature>-<ts>`) before any edit. Restore path must be documented in the app's README before you go live.
3. Use `location ^~ /<subpath>/` — the plain prefix form loses against the vhost's static-bypass regex rules; `^~` suppresses regex matching and wins. Forgetting this yields mysterious 404/static-served errors only after SSO passes.
4. After editing: `docker exec nginx-proxy-manager nginx -s reload`, then curl the URL expecting **401 without session** — that verifies the SSO wall before declaring the route live. Do not declare the route working from the config alone.
5. Run the app on DEV under a dedicated systemd unit (`Type=simple`, explicit `ExecStart` with the right interpreter). `systemctl enable --now`, then verify with `systemctl is-active` + a real HTTP request to the Tailscale address.
6. If a companion periodic job is needed, use a **systemd timer** (`OnUnitActiveSec`), not a cron line — same D-I-V-E cycle applies: backup, change, verify with `systemctl list-timers`.

## Pitfalls

- **Warn the user that a UI edit in Nginx Proxy Manager can wipe hand-edited conf blocks.** Document the backup path and the restore command in the app README; if the route 404s later, re-check `N.conf` first before debugging the app.
- **Commit the app code in a worktree branch, not on main** — Plon approves pushes explicitly; local merge/deploy of a reviewed branch is fine, `git push` is not.
- **Runtime copies diverge from repo copies.** When the deployed app gets hot-fixed in `/opt/hermes-agent-data/tools/<app>/`, copy the fixed files back into the worktree and commit before closing the turn — otherwise the repo quietly drifts from what runs in production.
- **Use RELATIVE paths for every fetch and asset in a frontend served under a vhost subpath** (`api/tasks`, `./app.js`) — root-absolute `/api/...` resolves against the domain root, escapes the `/<subpath>/` location block and 404s against the vhost's other rules; the page itself loads fine, so the symptom is only "empty page / buttons do nothing".
- **When a proxied route misbehaves, read what the proxy actually received before touching the app** — NPM logs on PROD at `/opt/docker/nginx-proxy-manager/data/logs/*access*.log` (grep the path; the referer field distinguishes which page fired the request). A 404 there with the correct referer pins a frontend path bug in one look; a 401 pins the SSO wall instead.
- **In a kanban/ledger UI, never let a completed action look like data loss** — checking/closing an item must visibly show where it went (reveal the "Cerradas" section + toast with undo). A check that makes the row vanish reads as a bug and destroys trust in the portal; the boss explicitly reported "desapareció no sé a dónde fue" for a correct close.

## Reversal (mandatory section in every app README)

- App: `systemctl disable --now <unit> <timer>` + remove the runtime dir.
- Route: restore the timestamped conf backup + `nginx -s reload`.
- The data store the app writes is NEVER part of the reversal — it predates the app and outlives it.

## References

- `references/telegram-pin.md` — single-pinned-message sync pattern (edit-in-place, digest hash, HTML parse mode) for surfacing a live list in the boss's Telegram chat.
