# Mode-Matrix E2E Verification Recipe (OFF / MOCK / LIVE)

Proven workflow (verified with 82/82 tests in two landing repos and three real-browser runs, Chromium 1440x900).

## 1. Local topology

- Static: `npx vite --port 3020` (or serve the `vite build` output).
- API: `PORT=3100 META_TRACKING_STORE=memory META_TRACKING_MODE=<MODE> META_TRACKING_SCHEMA_READY=true CORS_ORIGINS='http://127.0.0.1:3020' TRACKING_ALLOWED_ORIGINS='http://127.0.0.1:3020' TRACKING_CANONICAL_ORIGIN='http://127.0.0.1:3020' node server/webhook-server.js`
- Memory store is dev-only; Postgres path requires a real cluster (SKIP LOCKED / advisory locks are not simulable in memory).

## 2. Network instrumentation (CDP)

```python
# via browser CDP session
cdp('Network.enable')
cdp('Network.responseReceived', ...)  # accumulate params['response']['url'] into a list
fb_hits = [u for u in urls if 'facebook.com' in u or 'facebook.net' in u]
```

Assertions per mode:

| Check | OFF | MOCK | LIVE |
|---|---|---|---|
| banner visible | no (never rendered) | yes | yes |
| `typeof window.fbq` | `undefined` | `function` (stub, `__fbqMock === true`) | `function` only after GRANTED |
| facebook.com/net requests | 0 | 0 (also 0 `<script src=facebook>` elements) | fbevents.js + pixel calls only |
| consent after clicking Accept | UNKNOWN (banner absent → click is a no-op) | GRANTED (POST /api/tracking/consent), `tracking_eligible:false` | GRANTED → status `tracking_eligible:true` |
| `GET /api/tracking/status` | 200, mode OFF | 200, mode MOCK | 200, mode LIVE |

## 3. Unit suite per repo (node --test)

- Same module copied into both client repos; config entirely via env vars.
- Suites: consent endpoint hardening (cookie `__Host-`, origin allowlist, 400 on invalid status, 500 `consent_unavailable` when DB down), dual-ingest id derivation, queue claim/backoff/CAS/revocation (RED tests against the memory store with injected `clock`), and the three-mode gating rules.
- Build gate: `npx vite build` then `grep -c 'connect.facebook.net' index.html` == 0.

## 4. Pitfalls that cost real debugging time

- Gating banner/stub on `tracking_eligible` (LIVE-only flag) silently breaks MOCK.
- Banner z-index must clear the legal +18 bar, but reserve its height dynamically or it covers its own buttons.
- Pixel install must react to a `tracking:consent-changed` custom event, not wait for the 15 s poll tick.
- HTTP 200 with an `error` body (or 2xx without `events_received`) is NOT a delivery.
