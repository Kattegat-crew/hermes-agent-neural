# Server-Side Lead Idempotency (verified pattern, TDD RED→GREEN, ephemeral PG 16)

Verified 2026-10-27 on Golden Game + Paradise/Lucky landings (`server/tracking/leadRegistration.js`, byte-identical shared file, `META_LEAD_CAPI_MODE=pg_transaccional` opt-in). Reviewers reproduced 181/182 pass with 0 skips over real ephemeral Postgres.

## Transactional registration pattern (one dedicated PG client)

Order matters, every step tested:
1. **Schema check fail-closed:** verify migrations 001–003 present; missing ⇒ **503 without inserting** (never degrade to legacy silently). Cache the check per-process, but know: if schema changes later, requests 500 instead of 503.
2. **`pg_advisory_xact_lock(hash(brand|request_key))`** — scoped by brand so sister brands sharing a DB never cross-block.
3. **Dedup:** same `request_key` + same server-computed `service_hash` (SHA-256 of payload) ⇒ **200 deduped, zero side-effects** (no second CRM notification, no re-enqueue). Different hash ⇒ **409**.
4. **INSERT lead** (opaque `external_id`, never raw PII into CAPI payload fields).
5. **Consent revalidated with `SELECT ... FOR UPDATE`** inside the same tx — serializes against concurrent consent revocation; revoked/expired/other-brand cookie ⇒ no enqueue. Never confuse the form's legal `consent_marketing` checkbox with the Meta ad-consent cookie `__Host-<brand>_consent`.
6. **`SAVEPOINT sp_capi`** → INSERT `capi_events`; outbox failure ⇒ `needs_reconcile=true` + minimal `reconcile_payload` (no PII) with 48 h expiry. **ROLLBACK TO SAVEPOINT only survives statement-level errors** — a connection-level failure aborts the tx and the subsequent UPDATE throws ⇒ 500 and the lead is lost (retry recreates cleanly; idempotency not corrupted).
7. **COMMIT before any notification**; CRM/webhook side-effects only post-commit and only if `created`.

## event_id authority: server mints, browser must mirror

For Lead, the server **mints its own `event_id`** (UUIDv4, can't be derived pre-submit) and returns it in the response even when the outbox fails. Meta dedups on `event_name + event_id` being IDENTICAL — so:

- **Pitfall (confirmed by independent review):** if the browser still emits its own `fbq('track','Lead',{eventID: generateEventId()})` while the server mints a different one, activation of LIVE+worker = **two Lead events with distinct IDs = double counting**. There is no runtime error; Meta just counts twice.
- **Hard rule for activation:** the frontend must mirror the server-returned `event_id` (call `fbq` only after the webhook response, with the server's ID) in the **SAME deploy** as enabling LIVE, or a code-level interlock must make LIVE+worker impossible while the mismatch exists. Procedural checklists are not a barrier.

## Pitfalls found in review (fix before any LIVE cut)

- **`request_key` NULL bypass:** a partial `UNIQUE(request_key) WHERE request_key IS NOT NULL` + degrading invalid UUIDs to `null` ⇒ unlimited un-deduped inserts from hostile/broken clients even with the flag on. Distinguish explicitly-invalid (400) from absent (legacy compat), or rate-limit.
- **`needs_reconcile` without a consumer loses events forever** (48 h expiry). Don't claim delivery guarantees and don't go LIVE until a reconciler exists.
- **fbc without consent:** deriving `fbc = fb.1.<ts>.<fbclid>` and persisting it into `leads` unconditionally retains an ad identifier for users who denied marketing consent. Null it out without GRANTED, or move to `reconcile_payload` with expiry.
- **Legacy sender bypasses the whole consent gate:** the old inline `sendCapiEvent` path in the webhook sends IP + `value`/`currency` with no consent check and regardless of `META_TRACKING_MODE`. An opt-in new path doesn't fix this — the default path must also be gated (task 3C.5 same cut as LIVE).
- **Shared spec files across sister repos get contaminated:** copying `03-tasks.md` between Golden and Lucky overwrote brand tokens (`pp_consent` vs `gg_consent`) making the checklist wrong (a phase marked `[x]` that the legacy sender never satisfied). When two repos share one spec, diff brand tokens (`__Host-*_consent`, `*_pending_leads`, `*_req:`) before trusting checkboxes.
- **Advisory locks without `lock_timeout`/`statement_timeout`:** one hung tx blocks retries indefinitely and can exhaust the pool.

## Ephemeral PG test harness (no Docker, no secrets)

- Zonky PostgreSQL 16 binaries, **Unix socket only** in scratch; suite env convention: `PG_TEST_URL="postgresql://tester@/db?host=$SOCKDIR&port=N"`. Apply migrations twice with `ON_ERROR_STOP=1` to prove idempotent DDL. This converts previously-skipped 'requires PG' tests into green runs and lets reviewers reproduce independently.
- Negative matrix that caught real bugs: 8 concurrent same-key submits ⇒ 1 row; concurrent different payload ⇒ 1 create + 409s; outbox fault + retry; tx rollback on DB error; schema-not-installed; revocation **in race** (not just pre-revoked); expired/wrong-version/wrong-brand cookie; OFF/MOCK with `fetch` faked to count calls (must be 0); event_id stable across retries; zero PII in payload and reconcile blob.
