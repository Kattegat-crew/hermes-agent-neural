# Dual-Ingest Event Contract — deterministic IDs, identity & e2e recipe

Use when implementing or reviewing hybrid browser+CAPI event tracking on consent-gated landing pages: event-ID strategy, fbc/fbp handling, per-event semantics and end-to-end verification.

Proven on Golden Game / Lucky Brothers casino landings (Fase 3-B/3-C, 23-oct-2026). Full per-repo spec lives in each repo under `.specs/meta-capi-hybrid/` (`01-spec.md`, `02-design.md`, `03-tasks.md`).

## 1. Deterministic event IDs (UUIDv5) instead of UUIDv4 round-trips

For non-Lead browser events the client has no clean channel to learn an event_id the server already knows. Use **UUIDv5 over a stable identity tuple** so client and server independently derive the SAME id:

```
event_id = uuidv5(DNS_NAMESPACE, `${brand}|${event_name}|${stable_identity}`)
```

- `stable_identity` per event: PageView/ViewContent → pathname; FindLocation → `hostname|destination`; BonusGameInteraction → session key + locale; Lead → a fresh UUIDv4 `request_key` generated at submit time and passed with the payload (that one can't be derived).
- Same tuple on server ⇒ same event_id ⇒ Meta dedup is guaranteed even if the POST fails and is retried later.
- Doubling as idempotency: the server upserts on `(brand, event_name, event_id)` and rejects duplicates, so retries and double-clicks cannot double-count. Migration `server/migrations/002_tracking_capi_queue.sql` adds `capi_events` with `UNIQUE(brand, event_name, event_id)` + PENDING/PROCESSING/DELIVERED/FAILED/CANCELLED/EXPIRED states, `attempts<=4`, `next_attempt_at`, CAS lock columns (`locked_by`, `lock_generation`, `locked_until`). Additive only; **never executed without human approval**.

## 2. fbc/fbp policy (do not fabricate)

- `fbc`: include ONLY when the click URL actually carried `fbclid` (then `fbc = 'fb.1.' + timestamp + '.' + fbclid`). NEVER derive fbc from `_fbp` — invented fbc poisons attribution.
- `fbp`: include ONLY when a real first-party `_fbp` cookie exists. Read it as `fb.1.<timestamp>.<random>` only if you can't read the cookie — never as a constant.
- If any status/handshake endpoint must expose fbp-like identity data, return `hashed_payload` (SHA-256 hex + short prefix), never the raw cookie value.
- **nginx:** never expose `GET /capi-status` without auth — it leaks campaign/proxy confidence data publicly.

## 3. Per-event semantics for casino landings (Ley 1581 / Coljuegos)

| Event | Rules |
|---|---|
| PageView | Client-only (`fbq('track')`). NEVER POSTed to the server endpoint — it would 400. |
| ViewContent | Restricted to canonical routes (`/`, `/bono`, `/conocenos`, `/eventos`); UUIDv5 id. |
| FindLocation | `custom_data.destination_host` = hostname only. NEVER send the full Google Maps URL (leaks coordinates/params). |
| BonusGameInteraction | Custom event for the free ruleta. NEVER emit fake `InitiateCheckout` for a no-purchase flow. |
| Lead | No `value`/`currency` when the conversion is a free bono — a bono is not revenue. Dual-ingest: browser `fbq('track','Lead',{eventID})` + server CAPI with the same `request_key`-derived id. |

**Browser-only dispatch is rejected:** because the contract is dual-ingest with the server as the guaranteed path, `POST /api/tracking/event` returns **400** for a browser-side `Lead` (client helper refuses to send it too). Status codes: valid event → **202** (queued), invalid/rejected → **400**.

## 4. test_event_code channel: `facebookqg` URL param

In staging/test, pass the Test Events code via the landing URL as `?facebookqg=TEST12345` instead of env/config — no server restart, works per-visitor, and is validated server-side before use. Never commit test codes; production builds must contain **0** references to `connect.facebook.net` in compiled `index.html` (assert with `grep -c` after `vite build`).

## 5. E2E verification recipe (adds to consent-gate.md)

1. `vite build` → `grep -c 'connect.facebook.net' dist/index.html` == 0.
2. Headless Chrome: pre-consent `typeof fbq === 'undefined'`, no fbevents.js fetch; after accept: `GRANTED`, fbevents fetched, `tracking_eligible: true`.
3. Exercise a ViewContent POST → expect **202**; attempt a browser-side Lead POST → expect **400**.
4. UI pitfall: the consent banner (z-index 99999) previously covered the legal +18 bar and its own buttons. Reserve the real measured height of any fixed legal bar, verify `solape == 0` px and both buttons >=40px tall at 1440x900 and 390x844.

## 6. Test-suite hygiene

Lucky is writable (tests there are canonical); Golden's `tests/` is `root:root` — mirror-run (`node --test <scratch-mirror>/*.test.mjs` against repo sources) and keep both suites at parity (54/54 each) until the Admin runs `sudo chown -R hermes:orca /opt/golden-game-landing/tests`.
