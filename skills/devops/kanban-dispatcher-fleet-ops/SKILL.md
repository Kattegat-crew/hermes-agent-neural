---
name: kanban-dispatcher-fleet-ops
description: Use when kanban shows 'owner silent' crash loops in fleets.
version: 1.0.0
author: ragnar
license: internal
metadata:
  hermes:
    tags: [kanban, dispatcher, gateway, fleet, profiles, systemd]
    related_skills: [kanban-reviewer-fanout, kanban-workstream-cancellation]
---

# Kanban Dispatcher Fleet Ops (multi-profile)

## When to Use

- Kanban tasks go `running` then `crashed` with `owner silent` / `managed_worker_failed`.
- Someone proposes a standalone `hermes kanban daemon` or a systemd --user supervisor for it (it is deprecated — redirect to the gateway dispatcher).
- Deciding which profile owns the dispatcher in a multi-profile fleet, or unblocking a stalled board.

## Rules of the dispatcher (hermes >= 0.23)

1. **The standalone daemon is deprecated.** `hermes kanban daemon` without `--force` exits code 2 (`kanban_ops.py:_DAEMON_DEPRECATED`); with `--force` it warns about racing a gateway that has `dispatch_in_gateway: true`. NEVER propose a systemd --user unit for the daemon as a fix.
2. **The dispatcher lives inside the gateway** — the profile whose config has `kanban.dispatch_in_gateway: true` owns it. Exactly ONE profile must own it; do not set `true` at root AND in a profile you don't intend as owner.
3. **The worker admittance is against the gateway, not the dispatcher** (`kanban_worker_client.py`: "Kanban requires the assigned local profile owner"). An external supervisor cannot remove this dependency — it only hides it.
4. **Lock lottery:** if no profile declares `dispatch_in_gateway: false` explicitly, whichever gateway boots first grabs the dispatcher lock file — ownership is nondeterministic across restarts. Fix: set `kanban.dispatch_in_gateway: false` explicitly in EVERY profile that is not the owner (owner keeps `true`).

## Recipe: designate owner + unblock a stalled board

```bash
# 1. Backup configs, then append to each non-owner profile:
#    kanban:\n  dispatch_in_gateway: false
#    Also set owner's dispatch_interval_seconds to 60 (default 15 causes hot polling).
hermes -p <profile> config get kanban.dispatch_in_gateway   # verify each (false / owner=true)

# 2. Unblock stalled tasks, then dispatch manually (works without any restart):
hermes kanban unblock <task_id>
hermes kanban dispatch --max 3
```

Config changes apply at the owner gateway's next restart; manual `kanban dispatch` works immediately.

## Diagnosis: 'owner silent' crash loop

Symptom: task goes `running`, worker exits code 1 within ~60s, run outcome `crashed` with `managed_worker_failed`, error contains `owner silent` or `invalid_params`. Two known causes:

- **Worker params malformed** (e.g. bad `stop_phrases` shape sent by the dispatcher) — fix the payload at the source; workers of every assignee start dying the same way.
- **No live gateway for the assigned profile** — the profile owning the board has no gateway running, so the worker's owner check fails silently.

Verify recovery: task rows show `worker_pid` alive, new `task_runs` rows with no `owner silent`, assignees that previously always crashed (e.g. dev-heavy profiles) start running.

## Diagnosis: concurrent-spawn kill loop (`managed worker lost`)

Symptom: two tasks dispatched in the same cycle; one worker runs fine, the other dies ~20 s in with `managed worker lost`, and every retry repeats it. Cause: simultaneous spawns racing on one dispatching gateway.

Fix: set `kanban.max_in_progress_per_profile: 1` (and explicit `max_in_progress: 2`) in the OWNER profile's config. Two gotchas:
- `kanban.*` is resolved per-profile: if the key is absent from the owner's `profiles/<owner>/config.yaml`, the gateway boots with its own default (e.g. 8) and IGNORES the root value you just edited. Set it explicitly in the owner profile.
- Config applies only at the owner gateway's next restart. Until then the live control is `hermes kanban dispatch --max N`.

## Diagnosis: `blocker_auth` / spawn `Permission denied` on `dir` workspaces

Symptom: task auto-blocks with kind `blocker_auth`, `last_failure_error: workspace: [Errno 13] Permission denied: '<path>'`, run outcome `spawn_failed`; `kanban retry` loops forever because the error and path are frozen on the task row — retry does NOT re-read the workspace.

Root cause: the dispatcher spawns workers as the `hermes` user, so a `dir`-workspace card's `workspace_path` must already exist and be writable by it. A typo'd or never-created path (e.g. `/opt/hermes-agent-worktrees/...` when the real tree is `/opt/hermes-agent-data/worktrees/...`) fails at spawn, not at agent time.

Repair recipe (verified):
```bash
cd <repo> && git worktree add /opt/hermes-agent-data/worktrees/<name> <branch>
# backup kanban.db first, then fix the row directly:
#   update tasks set workspace_kind='dir',
#     workspace_path='/opt/hermes-agent-data/worktrees/<name>',
#     last_failure_error=NULL, spawn_failures=0,
#     consecutive_failures=0, status='ready' where id='<task_id>';
hermes kanban unblock <task_id> && hermes kanban dispatch --max 1
```

## Diagnosis: goal-loop `unachievable` = work DONE, not a crash

Symptom: worker exits code 1, run outcome `crashed`, error contains `kanban goal loop: task ... judged unachievable` — but the agent's last output shows the work complete (tests green, worktree clean at the expected commit) and it was asking to move to review.

This is an orchestration gap (agent cannot call request-review), NOT an infra failure. Re-dispatching re-blocks identically. Remedy: orchestrator applies the review handoff itself (request review to the reviewer profile), never a retry.

## Diagnosis: double worker on one profile after a config fix (boot gap)

Symptom: you set `max_in_progress_per_profile: 1`, the CLI `kanban dispatch` even reports `Deferred (<profile> at per-profile cap)`, but minutes later a SECOND worker for the same profile is running anyway. Cause: the gateway tick uses the config snapshot from boot — it does NOT honor the just-edited per-profile cap until the owner gateway restarts. CLI deferral and gateway admission are two different paths.

Live control without a restart (verified):
```bash
hermes kanban reclaim <task_id>   # releases the claim; task -> ready, worker goes defunct
# then immediately re-block it, or the next tick re-spawns it:
hermes kanban block <task_id> "<reason>" --kind transient
hermes kanban unblock <task_id>   # when the profile actually frees up
```
Watch with: `select id,assignee,worker_pid from tasks where status='running'` — more than one row per assignee = the boot gap is live.

CLI syntax gotcha: `kanban block` takes the reason POSITIONALLY (`hermes kanban block <id> "reason" --kind transient`); `--reason` is unrecognized. Typed kinds: `transient` = maybe-flaky/will-retry, `needs_input` = a real human decision owed.

## Recipe: board-hygiene sweep after an infra incident

Infra failures (db lock, spawn Permission denied, `owner silent`) freeze error state on task rows even after the infra is fixed. With kanban.db backed up:
```sql
update tasks set last_failure_error=NULL, spawn_failures=0,
  consecutive_failures=0, block_recurrences=0
where id in (<infra-victim ids>);
```
Then give every blocked card a truthful typed block kind + a dated comment saying WHY it stays blocked (who owns it, what unblocks it) — a blocked column full of stale `needs_input` for infra ghosts hides the cards that genuinely need a human. Never archive blindly.

## Pitfalls

- `max_in_progress` is per-dispatcher; manual `dispatch --max N` respects it. It is also read per-profile at boot: edit the OWNER profile's config, not just root, or the gateway keeps its boot-time value.
- A `dir`-workspace card referencing a non-existent path can never self-heal via retry — the frozen `last_failure_error` must be cleared on the task row (kanban.db, with backup) after the path actually exists.
- Auto-block kinds are diagnostic: `blocker_auth` + `spawn_failed` = environment/permissions at spawn; `crashed` + `unachievable` verdict = orchestration decision owed by the orchestrator. Different remedies; a blind retry fits neither.
- Don't 'fix' dispatch by running daemon + gateway simultaneously — that is the documented race.
- Check `dispatch_interval_seconds` in ALL profiles: a profile-local value overrides root config even for the owner.
- Manual `dispatch --max N` defers by per-profile cap, but the gateway TICK does not until restart — after any concurrency fix, poll `running` rows for double-per-profile spawns instead of trusting one dispatch output.
- `reclaim` is the escape hatch for a wrongly admitted worker; killing the pid leaves a defunct process and a crashed run, reclaim keeps the task clean in `ready`.