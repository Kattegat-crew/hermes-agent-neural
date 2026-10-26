---
name: meta-pixel-capi
description: "Trigger: meta pixel, capi, conversions api, tracking pixel, deduplication, event match quality, emq, facebook pixel, lead tracking, offline conversions. Implement, deduplicate, and diagnose hybrid browser-server Meta tracking with Conversions API and Pixel."
license: Apache-2.0
metadata:
  author: gentleman-programming
  version: "1.0"
---

# Meta Pixel & Conversions API (CAPI)

## Activation Contract

Use when implementing, refactoring, or diagnosing Meta (Facebook) tracking in web apps. Covers browser Pixel (`fbq`), server-side Conversions API (CAPI), event deduplication, advanced matching (EMQ), and Graph API testing.

## Hard Rules

- **Redundancy & Deduplication:** Never run CAPI alone or Pixel alone for primary conversion events (`Lead`, `Purchase`). Always emit from BOTH browser and server with the EXACT SAME `event_id` (UUIDv4) within 48 hours. Meta will deduplicate automatically.
- **Advanced Matching (EMQ) Hashing:** All PII fields (`em`, `ph`, `fn`, `ln`, `external_id`, `ct`, `st`, `zp`, `country`) MUST be trimmed, lowercased, and hashed with SHA-256. Do NOT hash `client_ip_address`, `client_user_agent`, `fbp`, or `fbc`.
- **Phone Normalization:** Phone numbers (`ph`) must follow E.164 (only digits, including country code, e.g. Colombia `573001234567`) BEFORE hashing.
- **Graph API Endpoint:** CAPI events are dispatched to `POST https://graph.facebook.com/v21.0/{PIXEL_ID}/events`. Never POST to `/{PIXEL_ID}` directly (causes Graph API error code 100/33).
- **Non-blocking Dispatch:** Server-side CAPI dispatch MUST be asynchronous / fire-and-forget with a strict timeout (max 8s). Never block user registration, checkout, or form responses waiting for Meta CAPI.
- **Persist Before Dispatch:** Store the lead/order in the primary database BEFORE dispatching to CAPI.
- **Test Event Code:** In development or staging, pass `test_event_code` in the CAPI payload to verify events in Meta Events Manager > Test Events in real time. Never commit hardcoded test codes to production.

## Decision Gates

| Scenario | Architectural Choice |
|---|---|
| Page navigation in SPA (`/`, `/eventos`) | Client-side only: `fbq('track', 'PageView')` and `fbq('track', 'ViewContent', { content_name })` |
| Form submission / Lead / Bonus claim | **Hybrid**: Client-side `fbq('track', 'Lead', ..., { eventID })` + Server-side CAPI `POST .../events` with identical `event_id` |
| Client has AdBlocker / iOS ITP | Frontend `fbq` silently drops or fails; server-side CAPI guarantees 100% conversion delivery |
| Event Setup Tool fails with "No pixel detected" | Expected on SPAs behind Cloudflare/AdBlockers. Verify with Graph API Explorer or direct cURL instead of the GUI tool |

## Implementation Specification

### 1. Browser Client Helper (`metaPixel.js`)
```javascript
export function getMetaCookies() {
  if (typeof document === 'undefined') return { fbp: null, fbc: null };
  const cookies = Object.fromEntries(document.cookie.split('; ').map(c => c.split('=')));
  return { fbp: cookies._fbp || null, fbc: cookies._fbc || null };
}

export function generateEventId() {
  return typeof crypto?.randomUUID === 'function' ? crypto.randomUUID() : `ev-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

export function trackLead({ eventId, value, currency = 'COP', contentName = 'Lead' }) {
  if (typeof window === 'undefined' || !window.fbq) return;
  const customData = { content_name: contentName, value, currency };
  window.fbq('track', 'Lead', customData, eventId ? { eventID: eventId } : undefined);
}
```

### 2. Server CAPI Dispatcher (`capiDispatcher.js`)
```javascript
import crypto from 'crypto';

const sha256 = (s) => s ? crypto.createHash('sha256').update(String(s).trim().toLowerCase()).digest('hex') : undefined;

function normalizePhone(phone, defaultCountryCode = '57') {
  if (!phone) return undefined;
  const digits = String(phone).replace(/\D/g, '');
  if (!digits) return undefined;
  const formatted = digits.length === 10 ? `${defaultCountryCode}${digits}` : digits;
  return sha256(formatted);
}

export async function sendCapiEvent({ pixelId, accessToken, testEventCode, eventName, eventId, lead, clientIp, userAgent, fbp, fbc }) {
  const payload = {
    data: [{
      event_name: eventName,
      event_time: Math.floor(Date.now() / 1000),
      event_id: eventId,
      action_source: 'website',
      user_data: {
        em: sha256(lead.email),
        ph: normalizePhone(lead.phone),
        fn: sha256(lead.name?.split(' ')[0]),
        ...(lead.cedula ? { external_id: sha256(lead.cedula) } : {}),
        client_ip_address: clientIp,
        client_user_agent: userAgent,
        ...(fbp ? { fbp } : {}),
        ...(fbc ? { fbc } : {})
      },
      custom_data: {
        content_name: lead.contentName || 'Bono',
        value: lead.value,
        currency: lead.currency || 'COP'
      }
    }],
    ...(testEventCode ? { test_event_code: testEventCode } : {})
  };

  const res = await fetch(`https://graph.facebook.com/v21.0/${pixelId}/events`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...payload, access_token: accessToken }),
    signal: AbortSignal.timeout(8000)
  });
  return res.json();
}
```

## Verification & Diagnostics

1. **Verify CAPI via cURL:**
   ```bash
   curl -X POST "https://graph.facebook.com/v21.0/<PIXEL_ID>/events" \
     -H "Content-Type: application/json" \
     -d '{
       "data": [{
         "event_name": "Lead",
         "event_time": '$(date +%s)',
         "event_id": "test-'$(date +%s)'",
         "action_source": "website",
         "user_data": { "em": "test@domain.com" }
       }],
       "access_token": "<META_CAPI_ACCESS_TOKEN>"
     }'
   ```
   *Expected response:* `{"events_received": 1, "messages": []}`.

2. **Deduplication Check in Events Manager:**
   * Go to **Events Manager > Pixel > Overview**.
   * Inspect the `Lead` event: connection method should show **"Navegador • Servidor"** and deduplication status **"100% deduplicados"**.

3. **Event Match Quality (EMQ):**
   * Target EMQ score >= 7.0/10. Achieved by sending: email (`em`) + phone (`ph`) + first name (`fn`) + external ID (`external_id`) + IP + User-Agent + `_fbp` cookie.

## Consent Gate (mandatory before any pixel)

Never ship a raw pixel in `index.html` on landing pages with ad tracking: gate ALL Meta loading behind explicit consent, fail-closed.

- **Fail-closed mode flag:** server tracking mode defaults to `OFF` (`META_TRACKING_MODE`); `OFF`/unknown consent = no pixel script, no cookie, no CAPI enqueue. Enable only via explicit config.
- **Client gate:** remove the `connect.facebook.net/fbevents.js` snippet, its cookie pre-seed and the `<noscript>` img from the HTML. Load the pixel conditionally only after `POST /api/tracking/consent` returns GRANTED and `GET /api/tracking/status` reports `tracking_eligible: true`.
- **Consent endpoint hardening:** `__Host-` prefixed cookie (Secure, Path=/, SameSite=Lax — requires HTTPS), store only a SHA-256 hash of the consent token server-side, validate `Content-Type` + `Origin` against a strict allowlist (`TRACKING_ALLOWED_ORIGINS`), reject invalid status with 400, return 500 (`consent_unavailable`) instead of fake success when the DB is down. Persist consent in PostgreSQL (survives restarts); memory store only behind `NODE_ENV !== 'production'`.
- **CSP:** ensure `connect-src` allows `connect.facebook.net`, `graph.facebook.com`, `www.facebook.com` or the pixel will silently fail after consent.
- **Schema migration is additive and NOT auto-executed:** create the consent table in a `server/migrations/*.sql` file; require human approval before running it. Details: `references/consent-gate.md`.

## Dual-Ingest Event Contract (deterministic IDs)

For hybrid events, derive `event_id` as **UUIDv5 over a stable identity tuple** (`brand|event_name|stable_identity`) so client and server compute the same id without a round-trip; the same tuple doubles as the idempotency key on the server (`UNIQUE(brand, event_name, event_id)`, additive queue migration `002_tracking_capi_queue.sql`, never auto-executed). Lead keeps a fresh UUIDv4 `request_key` instead (undeterminable pre-submit).

- **Never fabricate `fbc`** (only from a real `fbclid` click param); `fbp` only from a real first-party `_fbp`. Any handshake/status endpoint returns `hashed_payload` (SHA-256 + prefix), never the raw cookie; `GET /capi-status` must not be publicly exposed on nginx.
- **Casino-landing semantics:** PageView is client-only (server POST → 400); ViewContent restricted to canonical routes; FindLocation sends `destination_host` only (never full Maps URLs); the free ruleta uses custom `BonusGameInteraction`, never a fake `InitiateCheckout`; a free-bono Lead carries no `value`/`currency`. Valid event POST → **202**, browser-only Lead → **400**.
- **Test code channel:** pass Test Events codes via `?facebookqg=<code>` on the staging URL (validated server-side), not env/config; after `vite build`, assert 0 occurrences of `connect.facebook.net` in `index.html`.
- Details & e2e recipe: `references/event-contract.md` (companion to `references/consent-gate.md`).

## Durable CAPI Queue & Worker (verified pattern, 70/70 test suites)

When CAPI dispatch must survive worker crashes, retries and consent revocation, use a Postgres queue with **claim → CAS → revalidate → send**. Never send from the HTTP request path.

- **Atomic claim:** `SELECT ... FOR UPDATE SKIP LOCKED` inside a transaction with `UPDATE ... SET status='PROCESSING', locked_by, locked_at WHERE id=...`; commit immediately. Two concurrent workers never see the same event.
- **Lease with attempt-stable counters:** store `attempts` and `locked_at`; on lease expiry recovery, increment `attempts` once and continue — do NOT reset the backoff counter, or a crashing worker retries forever.
- **Backoff:** 30 s → 120 s → 600 s; max 4 attempts then `FAILED`. Respect Meta `Retry-After` capped at 600 s. HTTP 200 with an `error` body, or 2xx without `events_received`, is NOT delivered: treat as failure (retry if transient, FAILED otherwise).
- **Revocation race (CAS):** add `lock_generation` to the event row. Worker reads `lock_generation` at claim, closes with `UPDATE ... WHERE id=? AND lock_generation=<read> AND locked_by=<me>` (CAS). A consent revoke bumps `lock_generation`, so a stale worker's completion is silently discarded. **Revalidate consent BEFORE touching the network** — a revoked event must move to `CANCELLED` with 0 bytes sent.
- **Retention:** events older than 48 h → `EXPIRED`, never sent (stale user_data degrades EMQ and violates minimization).
- **No invented PII:** the worker sends only what the router captured; never fabricate `user_data` fields at send time. Do not route `value`/`currency` for free-bono leads.
- **Worker opt-in (fail-closed):** start the interval worker only when `META_TRACKING_WORKER === 'on'` AND pixel+token are present; otherwise log `[CAPI-WORKER] Desactivado` and send nothing. Interval loop with a `running` overlap guard and `.unref()` so it never blocks process shutdown.
- **In-memory queue parity:** the memory queue (dev-only) must accept the same injected `clock` + `store` so lease/backoff/revocation logic is testable without Postgres.
- Full schema, SQL and test matrix: `references/capi-queue.md`.

## Three-Mode Tracking Matrix (OFF / MOCK / LIVE) — verified in real browser, 82/82 ×2 repos

Implement the mode flag (`META_TRACKING_MODE`) as a THREE-way matrix, not a boolean on/off. Each mode has distinct UI + pixel + network guarantees:

| Mode | Consent banner | Pixel | Requests to facebook.com | Consent state |
|---|---|---|---|---|
| **OFF** | never rendered | `fbq` undefined | **0** | stays UNKNOWN, never asked |
| **MOCK** | rendered | local `fbq` **stub** (no network) | **0** (0 scripts too) | GRANTED recorded, `tracking_eligible:false` by design |
| **LIVE** | rendered | `fbevents.js` only after GRANTED | pixel's own only | GRANTED → `tracking_eligible:true` |

- **Pitfall (bit us):** gating the banner AND the stub pixel on `tracking_eligible` (a LIVE-derived flag) makes MOCK useless — the banner never appears and the stub never installs. Gate conditions must be per-mode: banner on `mode === 'LIVE' || mode === 'MOCK'`; pixel install on `consent GRANTED` (real pixel in LIVE, stub in MOCK), NOT on the eligibility flag.
- **MOCK mode exists for e2e/QA with zero external traffic:** a stub `fbq` records `track()` calls in memory so browser tests assert event emission without a single byte to Meta. Assert `window.__fbqMock === true`.
- **Banner layering pitfall:** the consent banner must sit ABOVE the legal +18 bar (it uses high z-index, e.g. 99999 vs 2000) but must not cover its own buttons — measure the legal bar's reserved height dynamically instead of hardcoding offsets.

## Consent Handshake Protocol (client)

- **Revalidate before each navigation-tracked event** (PageView, ViewContent) via `GET /api/tracking/status` with a **15 s freshness window**: at most one in-flight request, shared across concurrent triggers; cached result reused within the window. Click events (Lead) reuse the polled state without their own handshake.
- **Poll every 15 s, only while `document.visibilityState === 'visible'`**; stop polling and stop emitting events when the backend is unreachable — no re-emit until reload.
- **Immediate reaction on acceptance:** listen for a custom `tracking:consent-changed` event so the pixel installs the instant the user clicks Accept, without waiting for the next poll tick.
- **Config via env vars on the API** (`META_TRACKING_MODE`, `META_TRACKING_STORE=memory|pg`, `META_TRACKING_SCHEMA_READY`, `TRACKING_ALLOWED_ORIGINS`) — same module, both client repos, 82/82 tests each; assert after `vite build` that `index.html` still contains 0 occurrences of `connect.facebook.net`.

## Browser e2e Verification (zero-network assertions)

Verify all three modes in a real Chromium before declaring done — details in `references/mode-matrix-e2e.md`:
1. Instrument the network via CDP (`Network.enable` + `Network.responseReceived`) and collect every request; assert **0 URLs match `facebook.com`** in OFF and MOCK, and that only `fbevents.js`/pixel calls appear in LIVE after consent.
2. Serve the built landing on a local static port and the API on another port with CORS pointed at it (`CORS_ORIGINS` / `TRACKING_ALLOWED_ORIGINS` = the static origin).
3. Per mode assert the matrix above: banner presence, `typeof fbq`, facebook request count, and that the consent endpoint recorded GRANTED (or stayed UNKNOWN in OFF — clicking is a no-op because the banner never rendered).

## References

- [Meta Conversions API Documentation](https://developers.facebook.com/docs/marketing-api/conversions-api)
- [Meta Standard Events Specification](https://eventsmanager.facebook.com/business/help/402791146561655)
