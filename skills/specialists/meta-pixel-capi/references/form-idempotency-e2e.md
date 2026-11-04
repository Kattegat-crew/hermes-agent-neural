# Form-Level Idempotency E2E (request_key) — verified recipe, 12/12 UI tests ×2 repos

Companion to `mode-matrix-e2e.md`. Use when lead forms implement client-side identity
(request_key) so timeouts/retries never duplicate a lead, and the identity must be
released on success. Verified end-to-end on React+Vite landing pages (Golden Game ×2
forms, Lucky SlotMachine) with puppeteer-core + node:test.

## Scenario matrix (assert per form)

| Scenario | Assert |
|---|---|
| timeout → user retries | captured request body `request_key` IDENTICAL on both submits |
| user edits a field | request_key is NEW; payload carries the edited value |
| reload after failed submit + identical refill | same request_key restored (exact fingerprint match) |
| success | stored identity (`*_req:*` in localStorage) released; post-reload key is NEW |
| double submit in flight | button disabled; exactly 1 request captured |
| dedup chain | `eventID` passed to mock `fbq('track','Lead',…,{eventID})` == `event_id` in webhook payload |

## Harness isolation pattern (zero external bytes)

1. Build a FRESH dist into scratch (`vite build --outDir <scratch>/dist`) and pass it via
   env (`UI_DIST_DIR`); never point tests at a leftover scratch dist — scratch is pruned
   after 24 h idle and stale dists silently test old code. Rebuild when any `src/` file is
   newer than the dist.
2. Node `http` server on `127.0.0.1:0` (ephemeral port) serving the dist + a FAKE webhook
   with switchable modes: `ok` (202), `error`, `hang` (never responds — forces client
   AbortController timeout + retry).
3. Puppeteer `page.setRequestInterception(true)`: ABORT every request whose origin is not
   the local base URL (fonts, CDNs, `fbevents.js`, benign `data:` URLs). Log aborted URLs
   and assert 0 requests reached Meta.
4. Put the app in its own MOCK tracking mode (`/api/tracking/status` → MOCK/GRANTED):
   the app installs a stub `fbq` (`window.__fbqMock === true`) recording calls in
   `window.__fbqMockCalls` — assert event emission against that array, never against
   network calls to Meta.
5. Capture full webhook request bodies server-side; write evidence JSON (request_key,
   event_id, identity leftovers) to `UI_EVIDENCE_DIR`. Fictitious data only.

## Harness pitfalls (all three bit us)

- **`node --test tests/ui/` finds nothing on Node 22** — it does not scan directories.
  Use a glob: `node --test 'tests/ui/*.test.mjs'`. Note `npm test` (`tests/*.test.mjs`)
  does NOT cross into `tests/ui/` — document the separate command.
- **Clearing React controlled inputs with `el.value=''` desyncs React state** — the next
  onChange re-render restores the old value and typed text concatenates. Edit like a real
  user: `click({clickCount:3})` → Ctrl+A → Backspace → `page.type(..., {delay:15})`, then
  hard-assert the DOM values equal the fixture before submitting.
- **Cross-repo tool deps:** `puppeteer-core` resolved via absolute `createRequire('/opt/<other-repo>/package.json')` works but is NOT portable — it is machine-specific (Chrome path
  candidates too). Declare the dep or copy the harness if the suite must run elsewhere.

## Test hygiene

- Each test navigates fresh and builds its own pre-state (sessionStorage/identity) — no
  cross-scenario contamination.
- Give each repo its own evidence dir in CI runs; a shared dir mixes runs.
- `git status` must show only the new `tests/ui/` files; never stage `backups/` or dist.
