# Consent-Gated Hybrid Pixel — Pattern & Live Verification Recipe

Proven on Golden Game / Lucky Brothers casino landings (Vite + React + Express webhook server). Git is the source of truth: full spec lives in each repo under `.specs/meta-capi-hybrid/`.

## Server pieces (Express)

- `server/tracking/consentStore.js` — in-memory + PostgreSQL stores; token stored only as SHA-256 hash; expiry + version checked on every read.
- `server/tracking/router.js` — mounted at `/api/tracking`:
  - `POST /consent` → sets `__Host-<brand>_consent` cookie, returns mode/status/expires_at.
  - `GET /status` → `{ mode, consent, version, expires_at, tracking_eligible, schema_ready }`.
- Fail-closed matrix: `mode=OFF` → nothing loads; consent UNKNOWN/expired → nothing loads; store down → HTTP 500 `consent_unavailable` (never fake 200).
- Env: `META_TRACKING_MODE` (default OFF), `TRACKING_ALLOWED_ORIGINS` (strict allowlist, reject 403 otherwise), `META_TRACKING_STORE=memory` (dev only), `META_TRACKING_SCHEMA_READY=true` after the migration is actually run.

## Client pieces (Vite/React)

- `src/utils/trackingRuntime.js` — fetches `/api/tracking/status`, only injects `connect.facebook.net` `fbevents.js` when eligible; removes the banner once decided.
- `src/components/TrackingConsent.jsx` — two-button notice ("Aceptar publicidad" / "Solo esenciales"); both call `/api/tracking/consent` with `credentials: 'same-origin'`.
- Dev proxy: add `/api` → backend port in `vite.config.js`.
- index.html: delete the original fbevents snippet, `_fbp` cookie seed and `<noscript>` pixel image entirely.

## Live verification recipe (headless Chrome via raw CDP websocket)

1. Start backend with explicit env, e.g. `PORT=<port> META_TRACKING_MODE=LIVE META_TRACKING_STORE=memory META_TRACKING_SCHEMA_READY=true TRACKING_ALLOWED_ORIGINS='http://127.0.0.1:<viteport>,https://<proddomain>' node server/webhook-server.js`.
2. Launch a second headless Chrome instance with `--headless=new --remote-debugging-port=<port> --remote-allow-origins=*` — **without the flag the CDP WebSocket handshake returns 403** (origin-check added in Chrome 111+). Kill any stale Chrome on that debug port before relaunching, or the new flag silently doesn't apply.
3. From CDP: capture desktop (1440x900) and mobile (390x844) — assert banner rect on screen, no horizontal overflow, buttons >=40px tall, `typeof fbq === 'undefined'` BEFORE consent, no fbevents.js network fetch.
4. Click "Aceptar publicidad" via `Input.dispatchMouseEvent` on the element rect, then re-check: cookie present, `/status` shows `consent: GRANTED`, fbevents.js now fetched, banner gone.
5. Negative tests via curl: wrong Origin → 403; invalid status → 400; DB down + POST consent → 500 `consent_unavailable`.

### Diagnostic heuristic (allowlist bugs)

If a localhost Origin gets 403 but the production origin gets 200, the process is running with the *default* allowlist fallback — the env var never reached the server. Check which process actually owns the port (`ss -lntp | grep :<port>`) before debugging the matching logic; a systemd service on the same port is a classic false lead.

## Repo hygiene pitfall

Client repos on DEV may contain `tests/` or `dist/` dirs owned by `root:root` (created by an earlier root process). The agent user can't write them: don't fight it — verify code against a mirror copy in the scratch dir, run the build with an alternate `--outDir`, and report the needed `sudo chown -R` to the Admin instead of escalating permissions.
