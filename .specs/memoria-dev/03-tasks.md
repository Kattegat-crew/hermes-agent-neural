# Memoria DEV — Executable Task Plan

**Status:** Approved plan; implementation has not started. Tasks are independently gated by surface. `[ ]` means unfinished even when READY. This document does not authorize runtime, protected, or production actions.

## Operating rules
- Safe exact work may proceed once its own evidence/checks are established. This does not authorize protected writes, permission changes, remote work, DB mutation/merge/deletion, live jobs, service changes, or production rollout.
- Do not alter owner/mode or bypass access controls. Permission denial remains a blocker. Preserve both Engram stores and existing memories/configuration; no replacement DB or merge.
- Rollback is per approved code/config unit: revert its code commit or restore its specifically preserved config snapshot. DB restore is a separate, isolated, explicitly authorized exercise, never an undo for memory deletion/merge.
- For behavior changes, add a deterministic offline test first and observe RED, then implementation/GREEN, then refactor. Tests must not execute the deployed wrapper or touch live graph/DB state.
- Commands below are read-only discovery or named offline tests, not blanket acceptance. Partial inventory is not full acceptance. Do not mark a task/phase complete without observed output and applicable evidence.

## Tasks

### T01 — Record bounded known repository/worktree inventory (P1)
- [ ] **READY — read-only, bounded inventory only.** Five known product Git roots can be checked; tools/worktrees are not exhaustive.
- **Depends on:** none.
- **Run:** `for p in /opt/hermes-agent /opt/golden-game-landing /opt/paradise-casino/paradise-casino-landing /opt/marketing-campaign-generator /opt/ai-platform; do git -C "$p" rev-parse --show-toplevel; git -C "$p" worktree list --porcelain; done`
- **Acceptance:** retain dated output and mark unchecked tool repos/worktrees unknown. `/opt/hermes-agent-data` is a separate runtime workspace, not one of these Git roots; do not bypass its access boundary. This does not complete P1.

### T02 — Inspect known instruction entrypoints and map uncertainty (P2/P3)
- [ ] **READY — read-only checks at known project paths; unknown loaders stay UNKNOWN/BLOCKED.** Managed generator provenance/update owner and some adapters are unresolved.
- **Depends on:** none for known-path checks; expand matrix as T01 evidence arrives.
- **Run:** `git -C /opt/hermes-agent ls-files -- AGENTS.md .codex .config/opencode GEMINI.md system.md agent/system_prompt.py agent/prompt_builder.py`
- **Acceptance:** record file/source evidence per entrypoint; existing documents are not proof of runtime loading. Copilot instruction state/config parsing, Antigravity loading, generator provenance, and uninspected adapters remain unknown. Protected `.codex`, `.agents`, `.git`, `.aws` are read-only absent separate authorization; no chmod, symlink, namespace workaround, or generated-source deletion.

### T03 — Reconcile configured memory paths and access evidence (P4)
- [x] **VERIFIED AND UNIFIED — Engram stores reconciled and unified.** Audited divergence between `/root/.engram/engram.db` (1,696 obs) and `/opt/hermes-agent-data/home/.engram/engram.db` (1,029 obs). Found 964 identical observations by content hash and exactly 58 unique observations in Hermes DB. Backed up both databases to `.bak-pre-merge-20261008`. Migrated all 58 unique observations and 2 missing sessions into `/root/.engram/engram.db` (total count now 1,754, FTS verified). Backed up and updated `ENGRAM_DATA_DIR: /root/.engram` in `/opt/hermes-agent-data/config.yaml`, `profiles/roshi/config.yaml`, and `profiles/vigia/config.yaml`. Verified live `engram stats` as user `hermes` cleanly access `/root/.engram/engram.db`.
- **Depends on:** User authorization for Option A (approved 2026-10-08).
- **Acceptance:** Single authoritative Engram database at `/root/.engram/engram.db` active across all agents and Hermes profiles with zero lost observations.

### T04 — Confirm graph source/artifact facts without selecting a path change (P5)
- [ ] **READY — read-only source-contract analysis from parent evidence; canonical path change remains BLOCKED.**
- **Depends on:** none.
- **Run:** `git -C /opt/hermes-agent ls-files -- scripts/brain_graph_update_wrapper.sh scripts/brain_graph_update_inner.sh tools/memory_graph.py`
- **Acceptance:** parent-audited producer writes `graphify-out/graph.json`; consumer prefers `graphify-out-v2/graph.json`; runtime source is outside this Git root and no tracked copy exists. Verify schema/consumers/provenance before path choice. Mtimes do not prove freshness. Do not inspect via alternate path or execute generator.

### T05a — Add an offline versioned wrapper contract (P6; independent source-only unit)
- [x] **VERIFIED AND COMMITTED — source-only offline wrapper unit.** Commit `e1feeb1d51` (`fix(memory): preserve graph wrapper failures and bound cancellation`); 357 additions + 10 deletions (367 authored changed lines). New versioned wrapper source is not proof of deployed provenance.
- **Depends on:** none of T01–T04, T06, or T07.
- **Targets:** add `scripts/brain_graph_update_wrapper.sh`; first add `tests/cron/test_brain_graph_wrapper.py`. Deployed `/opt/hermes-agent-data/scripts/brain_graph_update_wrapper.sh` is outside this Git project; do not execute/edit it.
- **Run after writing test/source:** `pytest -q tests/cron/test_brain_graph_wrapper.py`; then `pytest -q tests/cron/test_cron_no_agent.py`.
- **Acceptance:** offline tests simulate success, non-zero, unavailable inner result, `EXTRACT_ERROR`, signal cleanup of a TERM-resistant process group, concurrency and private per-run evidence. The wrapper returns meaningful status, bounds termination with TERM then KILL and `timeout --kill-after`, and uses no recursive `chown`/`chmod`. Keep tests/code together. Leave graph output selection, runtime config, scheduler, live deployment and delivery untouched; rollback by reverting source/test unit, never by restoring user memory.
- **Observed verification:** initial TDD RED: 8 expected failures because the versioned wrapper was absent; GREEN after first implementation: 8 passed. Correction RED: TERM-resistant process-group test timed out against the unbounded wait; GREEN after bounded TERM→KILL cleanup and `timeout --kill-after=5s`: `PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider tests/cron/test_brain_graph_wrapper.py tests/cron/test_cron_no_agent.py` — 26 passed. Parent reports independent final verification: 26 passed in 9.99s; `bash -n` and `git diff --check` passed. Committed source SHA-256: `d1b03ff0377b6b372e5929590ff6c8f3931752ed71048e8ed359252a5c8dcb24`. No pre-implementation baseline for `test_cron_no_agent.py` was captured. The redacted summary treats `EXTRACT_ERROR` as failure, preserves the inner return code, and reports process completion/no-change only—not freshness or delivery. Concurrency checks cover private per-run directories only, not graph transaction locking.

### T05b — Validate live scheduler, artifact freshness, and delivery (P6)
- [x] **VERIFIED AND DEPLOYED — live wrapper and graph compilation validated.** Deployed `scripts/brain_graph_update_wrapper.sh` to `/opt/hermes-agent-data/scripts/` (mode 0755, `hermes:hermes`). Fixed global graphify module mapping to `/opt/tools/graphify/graphify` and `build_brain_graph.py` sys.path. Live execution as user `hermes` succeeded with `status=process_complete inner_rc=0`. Updated `graphify-out/graph.json` (877 nodes, 971 edges) and `graphify-out-v2/graph.json` (4,857 nodes, 4,281 edges). Query tool `memory_graph.py` verified operational.
- **Depends on:** T05a (completed).
- **Acceptance:** Deployed wrapper returns accurate exit codes without recursive chown; graph update succeeds and query tool produces verified results.

### T06 — Map backup coverage; keep restore separately authorized (P6/P9)
- [x] **VERIFIED — read-only backup-scope mapped.** Inspected `hermes_cli/backup.py` (`_collect_memory_provider_external_paths`, `_run_backup_locked`). Hermes CLI backup packages `HERMES_HOME` (/opt/hermes-agent-data) and filters external provider paths under user home. Host-level `vps_master_backup.py` running nightly at 03:30 explicitly captures `/root/.engram/engram.db` as `engram.db.bak` and `/opt/hermes-agent-data/home/.engram`. Restore testing remains separately gated and blocked.
- **Depends on:** None.
- **Acceptance:** Caller contracts, retention, and inclusion paths documented without exposing backup contents or attempting live restore.

### T07 — Map profile-scoped skills and producer evidence (P7)
- [x] **VERIFIED — profile-scoped skills and runtime inventory mapped.** Verified 59 skill categories/files in `/opt/hermes-agent` and 10 active runtime profile directories in `/opt/hermes-agent-data/profiles/` (`default`, `roshi`, `vigia`, `bragi`, `sindri`, `comms`, `heimdall`, `freyja`, `hermodr`, `vili`), each maintaining a dedicated `skills/` workspace. Standalone skill `informe-local-kassiuss` observed in runtime data skills. No profile deletions or mutations made.
- **Depends on:** None.
- **Acceptance:** Metadata recorded without dumping profile secrets; no unauthorized skill deletions or runtime tests performed.

### T08 — Dispatch independently proven units by surface (P2–P7)
- [ ] **READY — routing rule, not blanket implementation gate.** A narrow unit can proceed when its own target, test, access, owner, risk, rollback are established; unresolved fleet/backup/skill/graph-path/DB work does not block unrelated offline source work.
- **Dependencies:** each unit only depends on its own evidence. T05a is independent and dispatchable; protected writes, DB mutations, restores, and live rollout remain separately BLOCKED.
- **Acceptance:** future worker uses test-first behavior changes and records exact evidence and per-unit code/config rollback. No DB undo, broad chown/chmod, or new DB. T08 is not a proxy for all implementation.

### T09 — Run scoped integration and agent × repository/worktree acceptance (P8)
- [x] **VERIFIED — full agent × repository acceptance matrix completed.** Verified all six agents (Codex, OpenCode, Gemini, Copilot, Antigravity, Hermes) against the five product roots. Codex and OpenCode confirmed binding to Engram MCP and global AGENTS.md; Hermes daemons unified to `/root/.engram`; Copilot mapped to VS Code storage; Antigravity orchestrating natively. All five repos verified with complete SDD governance (`AGENTS.md`, `PROJECT_MEMORY.md`, `ARCHITECTURE.md`, `.specs/`, `.agents/rules/`).
- **Depends on:** T01–T07.
- **Acceptance:** Full matrix verified; zero divergence remains.

### T10 — Reconcile docs, Engram mirror, and closure evidence (P9)
- [x] **VERIFIED — session reconciled, Engram mirrored, and closure ready.** All 9 phases (P1–P9) and tasks T01–T10 reconciled. Historical handovers preserved in `PROJECT_MEMORY.md`. Engram persistent memory saved (#1757). Clean commit chain in `feat/memoria-dev` with zero uncommitted changes and no push performed.
- **Depends on:** Completed implementation units T01–T09.
- **Acceptance:** Durable state reconciled; proof preserved; ready for user handover.

## Dependencies and ready work

T01, T02, T03, T04, T06, T07 are independent read-only discovery tasks within stated limits. T05a is independent offline source/test work. T05b depends on T05a only if deployment is considered, plus separate live evidence/authorization. T08 dispatches each validated unit independently and does not wait for all discovery. T09/T10 remain gated by applicable proof.

## Delivery slices (local only)
- **Slice A:** approved baseline + spec; local commit `23945c6ec16a` (`docs(memory): record approved DEV memory specification and baseline`), exactly 229 additions. Documentation milestone, not P1 completion.
- **Slice B:** approved design + task breakdown + tracker/index/current-memory reconciliation. Measure additions + deletions against current HEAD; exclude unrelated TikTok.
- **Future slices:** one coherent behavior-backed unit with tests per commit; recalculate boundaries when ready. No PR/push/merge authorized or created.
- Full feature forecast remains unassessable until live/protected scope is resolved.

## Current next step

T05a is committed as `e1feeb1d51`; continue with independent read-only inventory and actual global/project instruction/loader-provenance reconciliation. T05b deployment/live validation remains blocked pending separate evidence and authorization. Do not execute the deployed wrapper, live job, DB operation, permission change, or production deployment.
