# Durable CAPI Queue & Worker — schema, SQL and test matrix

Verified implementation (Golden Game / Paradise landings, 2026-10): 16 new worker tests on top of 54 suite tests, 70/70 green in both repos.

## Queue table (additive migration, never auto-executed)

`002_tracking_capi_queue.sql` — columns beyond the consent/event rows:

- `status` — `PENDING | PROCESSING | DELIVERED | FAILED | CANCELLED | EXPIRED`
- `attempts INT`, `next_attempt_at TIMESTAMPTZ`, `locked_by TEXT`, `locked_at TIMESTAMPTZ`
- `lock_generation INT` — bumped on consent revoke; CAS token for the worker
- `last_error TEXT`, `response_code TEXT` (counters only, no PII in logs)
- `UNIQUE(brand, event_name, event_id)` — idempotency against double enqueue

## Claim SQL

```sql
BEGIN;
SELECT id, payload, attempts, lock_generation
  FROM tracking_capi_queue
 WHERE status='PENDING' AND next_attempt_at <= now()
 ORDER BY next_attempt_at
 LIMIT 1
 FOR UPDATE SKIP LOCKED;
UPDATE tracking_capi_queue
   SET status='PROCESSING', locked_by=$worker, locked_at=now()
 WHERE id=$id;
COMMIT;
```

## Worker cycle (runOnce)

1. **Claim** (SQL above). No row → return zeroed counters.
2. **Revalidate consent** via store lookup using the event's consent token id. Revoked/unavailable → CAS-close as `CANCELLED`, zero network calls.
3. **Age gate:** `now - created_at > 48h` → CAS-close as `EXPIRED`.
4. **Dispatch** to `POST /v21.0/{pixel}/events` with 8 s timeout.
5. Interpret response:
   - 200 + `events_received: 1` → CAS-close `DELIVERED`.
   - 429 → retry honoring `Retry-After` (cap 600 s).
   - 5xx / network / timeout → transient retry (30 s → 120 s → 600 s; attempts > 4 → `FAILED`).
   - 200 with `error` body, or 2xx without `events_received` → not delivered; retry if plausibly transient, else `FAILED`.
6. **CAS close:** `UPDATE ... SET status=$s WHERE id=$id AND lock_generation=$gen AND locked_by=$worker` — 0 rows updated means a revoke raced us; drop silently.

## Test matrix (what each test protects)

| Test | Failure mode prevented |
|---|---|
| dual-worker claim | duplicate send (SKIP LOCKED) |
| lease expiry recovery | lost event / reset backoff counter |
| CAS on lock_generation | cancelled event closed by stale generation |
| revoke after claim | 1 unintended network send |
| max attempts | infinite retry loop |
| 429 Retry-After | hammering Meta |
| 200+error body | false DELIVERED |
| 2xx missing events_received | false DELIVERED |
| age > 48 h | sending stale user_data |
| no invented user_data | PII fabrication |

## Wiring (webhook-server.js)

- Mount router as before; add `createMemoryQueue({ store, consentVersion })` in dev so the memory queue shares the injected clock and consent store.
- After the router mount, gate the worker:

```js
if (process.env.META_TRACKING_WORKER === 'on') {
  const dispatcher = createDispatcher({ pixelId: META_PIXEL_ID, accessToken: META_CAPI_ACCESS_TOKEN });
  if (!dispatcher.configured) {
    console.warn('[CAPI-WORKER] Desactivado: falta META_PIXEL_ID o META_CAPI_ACCESS_TOKEN.');
  } else {
    const w = createWorker({ queue: TRACKING_QUEUE, store: TRACKING_STORE, dispatcher, brand, consentVersion, workerId: `${brand}-${process.pid}` });
    let running = false;
    const tick = async () => {
      if (running) return;
      running = true;
      try { const r = await w.runOnce(); if (r.delivered || r.retried || r.failed || r.cancelled) console.log('[CAPI-WORKER] ciclo', JSON.stringify(r)); }
      catch (err) { console.error('[CAPI-WORKER] error de ciclo:', err.message); }
      finally { running = false; }
    };
    setInterval(tick, Number(process.env.META_TRACKING_WORKER_INTERVAL_MS || 5000)).unref?.();
  }
}
```

Log counters only — never event payloads or user_data.
