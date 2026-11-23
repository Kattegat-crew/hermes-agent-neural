# Feature Specification: Single-Row Save for Session Metadata

* **Status**: Approved (Admin authorization 2026-11-23, Telegram)
* **Author**: Ragnar
* **Target Module**: `gateway/session.py`, `gateway/session_lifecycle.py`
* **Created**: 2026-11-23
* **Related incident**: Discord + Telegram outages 2026-11-23 08:07 / 11:21 / 11:49 / 12:00 (America/Bogota)

---

## 1. Problem Statement & Motivation

Every inbound gateway message passes through `pre_gateway_dispatch`. The
`hermes-session-reset-policy` plugin stamps its own clock into the session
metadata on **every** message (the "not past the boundary" branch), which calls
`SessionStore.set_session_metadata`.

`set_session_metadata` delegates to `_update_entry`, whose docstring states it
always performs a **full save**: `_save()` → `_snapshot_routing_locked()` →
`replace_gateway_routing_entries()`, i.e. `DELETE` + `INSERT` of every routing
row in `state.db` **plus** a rewrite of the multi-MB `sessions.json` mirror.

Measured on 2026-11-23 11:59 (live traceback, `Loop thread traceback`):

```
plugins_dispatch.ainvoke_hook (pre_gateway_dispatch, unbounded)
  -> hermes-session-reset-policy/__init__.py:398 _maybe_reset
  -> session_store.set_session_metadata
  -> session_lifecycle._update_entry
  -> session_persistence._save
  -> _snapshot_routing_locked / _entries_as_dicts
```

At that moment the index held **28,823 rows** (scope `/opt/hermes-agent-data/sessions`).
The resulting event-loop stall was 10-40 s per message. Discord's gateway
heartbeat expects a tick every 41 s; Telegram's long-poll adapter stopped
consuming updates (`1 update(s) queued but not consumed`). Both platforms went
dark simultaneously and `systemd` restarted the unit (NRestarts=4).

The store already implements the correct path: `_save_entry()` performs a
single-row UPSERT (used by `update_session` and the healthy-path `updated_at`
bump). `set_session_metadata` simply does not use it.

Growth made this get worse every day: ~755 routing entries/day, no pruning of
retired rows.

## 2. Goals

- **G1**: `set_session_metadata` persists through the single-row UPSERT path and
  never triggers a full routing-index rewrite.
- **G2**: the persisted value remains durable across a store reload (restart).
- **G3**: no change to `updated_at` semantics (metadata writes must not make an
  idle session look fresh).
- **G4**: behaviour is unchanged when no DB is available (JSON-only store): the
  existing full-save fallback still applies.

## 3. Non-Goals

- Do **not** add `pre_gateway_dispatch` to `_HOOK_TIMEOUT_BOUNDED_HOOKS`. The
  core documents this as an intentional decision ("policy gate — neither fail
  mode is acceptable"); abandoning the hook would skip auth-like checks or drop
  legitimate messages. Making the callback cheap removes the need.
- Do not change the reset policy, its boundaries, or its clock semantics.
- Do not touch `sessions.json` format or the routing schema.
- Do not modify the plugin, profiles, or cron jobs.
- Out of scope (separate hygiene, already executed with backup):
  pruning ended sessions and orphaned routing rows.

## 4. Acceptance Criteria

**AC1 — fast path taken**
Given a store backed by `state.db` and an existing session entry,
When `set_session_metadata(key, "k", "v")` is called,
Then `_save_entry` is invoked at least once and `_save` (full rewrite) is never invoked.

**AC2 — durability**
Given the same call,
When a new `SessionStore` is loaded from the same directory,
Then `get_session_metadata(key, "k") == "v"`.

**AC3 — clock untouched**
Given an entry whose `updated_at` is 21 days old,
When `set_session_metadata` is called,
Then `updated_at` is unchanged.

**AC4 — JSON-only fallback**
Given a store with `_db = None`,
When `set_session_metadata` is called,
Then the value survives a reload (existing mirror path), with no exception.

**AC5 — no regression on other `_update_entry` callers**
`update_session`, `suspend_session` and model-override writes keep their current
persistence behaviour (default `fast=False`).

## 5. Edge Cases

- Entry missing → returns `False`, no write (unchanged).
- Mutator returns `False` → no write (unchanged).
- DB present but single-entry save raises → `_save_entry` already falls back to
  the full rewrite; must not raise to the caller.
- Concurrent full rewrite in flight → generation guard in `_save_entry` decides;
  no lost update (existing contract).

## 6. Failure Modes

- If the fast path silently drops the write, the plugin's clock stamp regresses
  and a session may reset earlier than policy allows. Covered by AC2.
- If the lock is held during I/O, a slow disk reintroduces the stall. Holding
  `_lock` here is intentional and bounded: generation allocation must be atomic
  with the mutation, `_lock` is non-reentrant (so the fallback must carry
  `entry_data`), and the write under the lock is a single-row UPSERT — not the
  O(n) rewrite. Declared residual: a pathological stall on that one row holds
  `_lock`, the same exposure `update_session` already has on every turn.
