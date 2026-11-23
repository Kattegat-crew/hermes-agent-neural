# Technical Design: Single-Row Save for Session Metadata

* **Status**: Approved
* **Spec**: `01-spec.md`
* **Created**: 2026-11-23

---

## 1. Current flow

```
set_session_metadata(key, k, v)
  └─ _update_entry(key, mutate)              # session_lifecycle.py:152
       ├─ acquire self._lock
       ├─ entry = _entry_locked(key); mutate(entry)
       ├─ self._save()                       # FULL REWRITE (O(n) rows + sessions.json)
       └─ release lock
```

`_save()` → `_snapshot_routing_locked()` → `_persist_routing_data()` →
`replace_gateway_routing_entries()`: `DELETE FROM gateway_routing WHERE scope=?`
followed by `executemany(INSERT ...)` for every entry, then
`_save_sessions_json()` (atomic rewrite + fsync of the multi-MB mirror).

## 2. Target flow

```
set_session_metadata(key, k, v)
  └─ _update_entry(key, mutate, fast=True)   # new keyword, default False
       ├─ acquire self._lock
       ├─ entry = _entry_locked(key); mutate(entry)
       └─ self._save_entry(key, entry_data=entry.to_dict(), lock_held=True)
            ├─ serialise + allocate routing generation   (inside _lock: atomic with the mutation)
            ├─ UPSERT one row under _save_lock
            └─ fallback (no DB / failed UPSERT): _entries_as_dicts() + _persist_routing_data()
       release self._lock
```

Persistence runs **inside** the mutation lock, matching `update_session`. Two invariants depend
on it:

- *No lost update*: `_save_entry` allocates the routing generation when it runs. Releasing the
  lock first lets a concurrent scalar write take a higher generation with a newer snapshot while
  this older one overwrites it in `state.db`.
- *No deadlock*: `_lock` is a plain non-reentrant `Lock`. The fallback must receive `entry_data`,
  because without it `_save_entry` calls `_save_entries()`, which re-acquires `_lock` in the same
  thread and hangs the gateway forever.

The I/O executed under `_lock` is a single-row UPSERT (the same cost `update_session` already
pays on every turn), not the O(n) rewrite this change removes.

`_save_entry` already exists (`session_persistence.py`, used by `update_session`
and the healthy-path bump). Its contract:

- Serializes one entry and UPSERTs it under `_save_lock`.
- Skips when a full snapshot or a newer fast save already covers that key
  (generation guard).
- Falls back to the full rewrite when there is no DB or the upsert fails, so
  AC4 is inherited, not reimplemented.

## 3. Change surface

| File | Change | Lines (approx.) |
|---|---|---|
| `gateway/session.py` | `set_session_metadata` passes `fast=True` | 1 |
| `gateway/session_lifecycle.py` | `_update_entry(session_key, mutate, *, fast: bool = False)`; branch to `_save_entry` | ~8 |

No schema change. No new dependency. No config key.

## 4. Concurrency and lock discipline

- The mutation stays under `_lock` (in-memory consistency, unchanged).
- `entry.to_dict()` is serialised and its routing generation allocated **inside**
  the lock, and the single-row UPSERT runs there too: generation order must match
  mutation order, and `_lock` is a plain non-reentrant `Lock` (see §2).
- `_save_entry` takes `_save_lock` (its own durable-write lock) and uses the
  shared generation counter, so a concurrent full rewrite cannot regress this
  row (existing contract, covered by `test_routing_save_fast_path.py`).

## 5. Why not bound `pre_gateway_dispatch`

`hermes_cli/plugins_dispatch.py` documents the hook as intentionally unbounded:
fail-open would skip policy checks, fail-closed would drop legitimate messages.
The stall was not caused by an inherently slow policy decision but by an O(n)
persistence call inside it. Removing the O(n) cost fixes the cause without
choosing a failure mode for a policy gate.

## 6. Observability

No new logs. Existing warnings cover the fallback path
("single-entry routing save failed ... falling back to full index rewrite").

## 7. Rollback

Single revert of the two edits. No data migration, so reverting restores the
previous full-rewrite behaviour immediately.
