---
name: kanban-workstream-cancellation
description: Use when cancelling a kanban workstream with dependents.
tags: [kanban, ops, dispatcher, workers]
metadata:
  hermes:
    tags: [kanban, ops, dispatcher, workers]
    related_skills: [sdlc-review]
version: 1.0.0
author: Ragnar (NeuralCrew Labs)
license: internal
---

# Cancelling a Kanban workstream (parent + hidden dependents + running workers)

## When to Use

- The Admin (or a decision) cancels/retires an entire kanban workstream: a parent task with dependent cards, independent reviews or workers still in execution.
- A task is `running` and must be stopped cleanly WITHOUT restarting services or editing dispatcher/gateway code.
- Cards referencing a workstream by title may be incomplete: dependent cards do NOT always name the workstream.

Verified procedure (hermes-agent, Nov 2026). Goal: retire an entire workstream cleanly without false `done`, without orphan workers, and without restarting services.

## 1. Discover the FULL dependency scope — never trust titles

Dependent cards often do NOT mention the workstream in their title (e.g. "Review B (Heimdall) — verificación forense…" was a Langfuse review with no "Langfuse" in the title). The dispatcher auto-dispatches a dependent as soon as its parent is archived, so hidden dependents become RUNNING workers.

Combine both probes against the kanban DB (read-only):

1. Recursive dependency closure from the parent id:
   ```sql
   WITH RECURSIVE scope(id) AS (
     SELECT '<parent_id>'
     UNION SELECT l.child_id FROM task_links l JOIN scope s ON l.parent_id = s.id
   )
   SELECT t.id, t.title, t.status, t.worker_pid, t.current_run_id
   FROM tasks t JOIN scope s ON t.id = s.id;
   ```
2. Reference sweep on card BODIES (titles miss workstream names):
   ```sql
   SELECT id, title, status, worker_pid, current_run_id FROM tasks
   WHERE body LIKE '%<parent_id>%'
      OR (lower(body) LIKE '%<workstream_keyword>%'
          AND status NOT IN ('done','archived'));
   ```

Union both result sets to get the real cancellation scope. Flag incidental keyword matches (cards that merely mention the term) and exclude them unless they are actually linked.

## 2. Back up the board DB before mutating

```bash
sqlite3 <kanban.db> ".backup <backup_dir>/pre-cancel-<name>-$TIMESTAMP.db"
```
Verify with `PRAGMA integrity_check` on the copy.

## 3. Leave a cancellation comment BEFORE archiving running cards

Record on the task being stopped: who ordered it, why, that the work transfers elsewhere, that archive must NOT be read as PASS/completion, and the exact exclusion scope (which similarly-named cards stay untouched). This is the auditable rationale for the next reader.

## 4. Stop a RUNNING worker canonically: `kanban archive`, never kill by hand

`kanban archive <task_id>` (or the kernel `archive_task`) is the only correct stop for a running worker:
- It snapshots `worker_pid` + `claim_lock` inside the archive txn and terminates the host-local worker AFTER commit (SIGTERM first, SIGKILL only if needed) — event `archive_worker_termination` records `terminated: true/false`.
- It closes the open run as `reclaimed`, clears the claim, and runs `recompute_ready` so no orphan child respawns.
- Never SIGKILL the pid directly and never just NULL the pid in the DB: the submitter watch thread detects its dispatcher's death and the dead-worker sweep would book a crash, polluting run history.

Do NOT use `block`: `block_task` refuses a task with a live run when an `expected_run_id` is asserted, and blocking keeps the card resurraceable (unblock-loop counting, dispatcher semantics).

## 5. Verify the cancel (read-back, not tool success)

1. Re-run the scope queries: every in-scope card must be `archived` with `worker_pid IS NULL`.
2. Confirm the `archive_worker_termination` event shows `"terminated": true` (and `sigkill: false` if a clean stop was expected).
3. Check process state: `<pid>` under `/proc` should be gone; `Z (zombie)` is acceptable (reaped by its parent); `S`/`R` means it survived — escalate, do not claim success.
4. A canonical `kanban` CLI command prints e.g. `Archived t_xxxx`; the CLI path validates transitions the raw SQL path would silently corrupt.

## Anti-patterns

- Cancelling only the parent by title keyword and leaving a dependent review running — the dependency graph, not the keyword search, defines the scope.
- Marking cancelled work `done` to "clean the board" — archive is the honest terminal state; `done` falsifies handoff history.
- Editing dispatcher/gateway code to stop one worker — archive already does it transactionally.