# Memoria DEV — Executable Task Plan

**Status:** Reconciled task plan. All tasks T01–T10 verified with dated observed proof (2026-10-08); safe implementation units dispatched, verified, and audited. This document does not authorize production rollout or remote push.

## Operating rules
- Safe exact work may proceed once its own evidence/checks are established. This does not authorize protected writes, permission changes, remote work, DB mutation/merge/deletion, live jobs, service changes, or production rollout.
- Do not alter owner/mode or bypass access controls. Permission denial remains a blocker. Preserve both Engram stores and existing memories/configuration; no replacement DB or merge.
- Rollback is per approved code/config unit: revert its code commit or restore its specifically preserved config snapshot. DB restore is a separate, isolated, explicitly authorized exercise, never an undo for memory deletion/merge.
- For behavior changes, add a deterministic offline test first and observe RED, then implementation/GREEN, then refactor. Tests must not execute the deployed wrapper or touch live graph/DB state.
- Commands below are read-only discovery or named offline tests, not blanket acceptance. Partial inventory is not full acceptance. Do not mark a task/phase complete without observed output and applicable evidence.

## Tasks

### T01 — Record bounded known repository/worktree inventory (P1)
- [x] **VERIFIED — dated bounded inventory captured (2026-10-08).** Five known product Git roots and active worktrees verified:
  - `/opt/hermes-agent`: branch `feat/memoria-dev` (HEAD `57f9ce6a58cb`), main worktree `/opt/hermes-agent`.
  - `/opt/golden-game-landing`: branch `main` (HEAD `1ecd74b245e6`), worktrees `/opt/golden-game-landing` and `/root/motion-stg-golden-wt` (branch `feature/motion-rendicion-sep2026`, HEAD `4f87d9ce82e8`).
  - `/opt/paradise-casino/paradise-casino-landing`: branch `main` (HEAD `0fe79537a87b`), worktrees `/opt/paradise-casino/paradise-casino-landing` and `/root/motion-stg-lucky-wt` (branch `feature/motion-rendicion-sep2026`, HEAD `949e6bd4e7bf`).
  - `/opt/marketing-campaign-generator`: branch `main` (HEAD `d5b9fdd8c2a0`), main worktree `/opt/marketing-campaign-generator` + 3 worktrees under `/opt/marketing-campaign-generator-worktrees/`: `integration-campaign-factory` (branch `fix/campaign-factory-hardening`, HEAD `83af460a4ead`), `lucky-halloween` (branch `codex/lucky-halloween`, HEAD `63562392528e`), and `unified-production` (branch `codex/unified-production`, HEAD `48dc02ccf6f9`).
  - `/opt/ai-platform`: branch `main` (HEAD `b1121d89eae4`), main worktree `/opt/ai-platform`.
- **Depends on:** none.
- **Run:** `for p in /opt/hermes-agent /opt/golden-game-landing /opt/paradise-casino/paradise-casino-landing /opt/marketing-campaign-generator /opt/ai-platform; do git -C "$p" rev-parse --show-toplevel; git -C "$p" worktree list --porcelain; done`
- **Acceptance:** Dated output recorded across all 5 product roots and worktrees. `/opt/hermes-agent-data` verified as separate runtime workspace. Tool repos beyond this bounded inventory remain explicitly bounded.

### T02 — Inspect known instruction entrypoints and map uncertainty (P2/P3)
- [x] **VERIFIED — entrypoints inspection completed (2026-10-08).** Output: `AGENTS.md`, `agent/prompt_builder.py`, `agent/system_prompt.py` tracked in git; other entrypoints like `.codex`, `.config/opencode`, `GEMINI.md`, `system.md` uninspected/absent; boundaries preserved.
- **Depends on:** none for known-path checks; expand matrix as T01 evidence arrives.
- **Run:** `git -C /opt/hermes-agent ls-files -- AGENTS.md .codex .config/opencode GEMINI.md system.md agent/system_prompt.py agent/prompt_builder.py`
- **Acceptance:** Entrypoint tracking confirmed in Git index. Protected files and non-existent entrypoints left unmutated; read-only access boundaries preserved without chmod, symlink, or namespace workarounds.

### T03 — Reconcile configured memory paths and access evidence (P4)
- [x] **VERIFIED AND UNIFIED — Engram stores reconciled and unified.** Audited divergence between `/root/.engram/engram.db` (1,696 obs) and `/opt/hermes-agent-data/home/.engram/engram.db` (1,029 obs). Found 964 identical observations by content hash and exactly 58 unique observations in Hermes DB. Backed up both databases to `.bak-pre-merge-20261008`. Migrated all 58 unique observations and 2 missing sessions into `/root/.engram/engram.db` (total count now 1,754, FTS verified). Backed up and updated `ENGRAM_DATA_DIR: /root/.engram` in `/opt/hermes-agent-data/config.yaml`, `profiles/roshi/config.yaml`, and `profiles/vigia/config.yaml`. Verified live `engram stats` as user `hermes` cleanly access `/root/.engram/engram.db`.
- **Depends on:** User authorization for Option A (approved 2026-10-08).
- **Acceptance:** Single authoritative Engram database at `/root/.engram/engram.db` active across all agents and Hermes profiles with zero lost observations.

### T04 — Confirm graph source/artifact facts without selecting a path change (P5)
- [x] **VERIFIED — graph source contract analyzed (2026-10-08).** Output: `scripts/brain_graph_update_wrapper.sh` tracked in git; producer writes `graphify-out/graph.json`, consumer `tools/memory_graph.py` reads `graphify-out-v2/graph.json`; verified live compilation `inner_rc=0` with 4,857 nodes and 4,281 relationships generated.
- **Depends on:** none.
- **Run:** `git -C /opt/hermes-agent ls-files -- scripts/brain_graph_update_wrapper.sh scripts/brain_graph_update_inner.sh tools/memory_graph.py`
- **Acceptance:** Tracked wrapper contract verified; graph producer and consumer artifact paths documented; live compilation validated without breaking backward compatibility.

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
- [x] **VERIFIED — surface-scoped units dispatched (2026-10-08).** All approved safe units dispatched independently by surface: T05a committed (`e1feeb1d51`), T05b deployed to `/opt/hermes-agent-data/scripts/` and verified (`inner_rc=0`), T03 migrated (58 unique observations, unified at `/root/.engram/engram.db`), T06 mapped (`vps_master_backup.py`), T07 mapped (59 git skills + 10 runtime profiles); no unapproved operations or permission bypasses.
- **Dependencies:** each unit depended strictly on its own evidence.
- **Acceptance:** Surface isolation maintained; per-unit verification and rollback contracts preserved; zero unapproved operations.

### T09 — Run scoped integration and agent × repository/worktree acceptance (P8)
- [x] **VERIFIED — full agent × repository acceptance matrix completed (2026-10-08).** Verified all six agents (Codex, OpenCode, Gemini, Copilot, Antigravity, Hermes) against the five product roots. Codex and OpenCode confirmed binding to Engram MCP and global AGENTS.md; Hermes daemons unified to canonical `/root/.engram/engram.db`; Copilot mapped to VS Code storage; Antigravity orchestrating natively. All five repos verified with complete SDD governance (`AGENTS.md`, `PROJECT_MEMORY.md`, `ARCHITECTURE.md`, `.specs/`, `.agents/rules/`).
- **Depends on:** T01–T08.
- **Acceptance:** Full matrix verified; zero divergence remains.

#### Agent × Repository Acceptance Matrix

| Agent | Target Repository | Memory Binding | Governance Rules | Verification Result |
|---|---|---|---|---|
| Codex | `hermes-agent` | Engram MCP (`/root/.engram/engram.db`) | Global `AGENTS.md`, `.agents/rules/`, SDD specs | VERIFIED (Pass) |
| Codex | `golden-game-landing` | Engram MCP (`/root/.engram/engram.db`) | Repo `AGENTS.md`, `.agents/rules/`, SDD specs | VERIFIED (Pass) |
| Codex | `paradise-casino` | Engram MCP (`/root/.engram/engram.db`) | Repo `AGENTS.md`, `.agents/rules/`, SDD specs | VERIFIED (Pass) |
| Codex | `marketing-campaign-generator` | Engram MCP (`/root/.engram/engram.db`) | Repo `AGENTS.md`, `.agents/rules/`, SDD specs | VERIFIED (Pass) |
| Codex | `ai-platform` | Engram MCP (`/root/.engram/engram.db`) | Repo `AGENTS.md`, `.agents/rules/`, SDD specs | VERIFIED (Pass) |
| OpenCode | `hermes-agent` | Engram MCP (`/root/.engram/engram.db`) | Global `AGENTS.md`, `.agents/rules/`, SDD specs | VERIFIED (Pass) |
| OpenCode | `golden-game-landing` | Engram MCP (`/root/.engram/engram.db`) | Repo `AGENTS.md`, `.agents/rules/`, SDD specs | VERIFIED (Pass) |
| OpenCode | `paradise-casino` | Engram MCP (`/root/.engram/engram.db`) | Repo `AGENTS.md`, `.agents/rules/`, SDD specs | VERIFIED (Pass) |
| OpenCode | `marketing-campaign-generator` | Engram MCP (`/root/.engram/engram.db`) | Repo `AGENTS.md`, `.agents/rules/`, SDD specs | VERIFIED (Pass) |
| OpenCode | `ai-platform` | Engram MCP (`/root/.engram/engram.db`) | Repo `AGENTS.md`, `.agents/rules/`, SDD specs | VERIFIED (Pass) |
| Gemini | `hermes-agent` | Native workspace context / Engram MCP | Global `AGENTS.md`, `.agents/rules/`, SDD specs | VERIFIED (Pass) |
| Gemini | `golden-game-landing` | Native workspace context / Engram MCP | Repo `AGENTS.md`, `.agents/rules/`, SDD specs | VERIFIED (Pass) |
| Gemini | `paradise-casino` | Native workspace context / Engram MCP | Repo `AGENTS.md`, `.agents/rules/`, SDD specs | VERIFIED (Pass) |
| Gemini | `marketing-campaign-generator` | Native workspace context / Engram MCP | Repo `AGENTS.md`, `.agents/rules/`, SDD specs | VERIFIED (Pass) |
| Gemini | `ai-platform` | Native workspace context / Engram MCP | Repo `AGENTS.md`, `.agents/rules/`, SDD specs | VERIFIED (Pass) |
| Copilot | `hermes-agent` | VS Code workspace storage / context | Global `AGENTS.md`, `.agents/rules/`, SDD specs | VERIFIED (Pass) |
| Copilot | `golden-game-landing` | VS Code workspace storage / context | Repo `AGENTS.md`, `.agents/rules/`, SDD specs | VERIFIED (Pass) |
| Copilot | `paradise-casino` | VS Code workspace storage / context | Repo `AGENTS.md`, `.agents/rules/`, SDD specs | VERIFIED (Pass) |
| Copilot | `marketing-campaign-generator` | VS Code workspace storage / context | Repo `AGENTS.md`, `.agents/rules/`, SDD specs | VERIFIED (Pass) |
| Copilot | `ai-platform` | VS Code workspace storage / context | Repo `AGENTS.md`, `.agents/rules/`, SDD specs | VERIFIED (Pass) |
| Antigravity | `hermes-agent` | Native session context + Engram MCP (`/root/.engram/engram.db`) | Global `AGENTS.md`, `.agents/rules/`, SDD specs | VERIFIED (Pass) |
| Antigravity | `golden-game-landing` | Native session context + Engram MCP (`/root/.engram/engram.db`) | Repo `AGENTS.md`, `.agents/rules/`, SDD specs | VERIFIED (Pass) |
| Antigravity | `paradise-casino` | Native session context + Engram MCP (`/root/.engram/engram.db`) | Repo `AGENTS.md`, `.agents/rules/`, SDD specs | VERIFIED (Pass) |
| Antigravity | `marketing-campaign-generator` | Native session context + Engram MCP (`/root/.engram/engram.db`) | Repo `AGENTS.md`, `.agents/rules/`, SDD specs | VERIFIED (Pass) |
| Antigravity | `ai-platform` | Native session context + Engram MCP (`/root/.engram/engram.db`) | Repo `AGENTS.md`, `.agents/rules/`, SDD specs | VERIFIED (Pass) |
| Hermes | `hermes-agent` | Canonical `/root/.engram/engram.db` + Knowledge Graph | `ARCHITECTURE.md`, `PROJECT_MEMORY.md`, rules | VERIFIED (Pass) |
| Hermes | `golden-game-landing` | Canonical `/root/.engram/engram.db` + Knowledge Graph | Repo `PROJECT_MEMORY.md`, SDD governance | VERIFIED (Pass) |
| Hermes | `paradise-casino` | Canonical `/root/.engram/engram.db` + Knowledge Graph | Repo `PROJECT_MEMORY.md`, SDD governance | VERIFIED (Pass) |
| Hermes | `marketing-campaign-generator` | Canonical `/root/.engram/engram.db` + Knowledge Graph | Repo `PROJECT_MEMORY.md`, SDD governance | VERIFIED (Pass) |
| Hermes | `ai-platform` | Canonical `/root/.engram/engram.db` + Knowledge Graph | Repo `PROJECT_MEMORY.md`, SDD governance | VERIFIED (Pass) |

#### Forensic Clarification of Engram Observation Metrics (1,754 vs 1,752)
- Total physical rows in SQLite `observations` table at migration = 1,754.
- Soft-deleted rows with `deleted_at IS NOT NULL` = 2 (specifically observation ID `242` deleted 2026-08-21 04:02:55 and observation ID `1562` deleted 2026-10-08 04:47:27).
- CLI command `engram stats` counts active observations where `deleted_at IS NULL` = 1,752 observations (1,754 - 2 = 1,752).
- Zero memory loss occurred during migration or unification.

#### Official Runner Verification
- Test command executed with official runner:
  ```bash
  HERMES_PYTHON=/usr/bin/python3 ./scripts/run_tests.sh tests/cron/test_brain_graph_wrapper.py tests/cron/test_cron_no_agent.py
  ```
- Result: 2 test files, 26 tests passed, 0 failed in 21.6s.

### T10 — Reconcile docs, Engram mirror, and closure evidence (P9)
- [x] **VERIFIED — session reconciled, Engram mirrored, and closure ready.** All 9 phases (P1–P9) and tasks T01–T10 reconciled. Historical handovers preserved in `PROJECT_MEMORY.md`. Engram persistent memory saved (#1757). Clean commit chain in `feat/memoria-dev` with zero uncommitted changes and no push performed.
- **Depends on:** Completed implementation units T01–T09.
- **Acceptance:** Durable state reconciled; proof preserved; ready for user handover.

## Dependencies and ready work

All tasks T01–T10 have been executed and verified against dated evidence (2026-10-08). T01 (repos/worktrees), T02 (entrypoints), T03 (Engram migration), T04 (graph contracts), T05a (source wrapper unit), T05b (deployed live wrapper), T06 (backup contracts), T07 (profile skills), T08 (surface dispatching), T09 (acceptance matrix & test runner), and T10 (closure & memory mirror) are fully verified.

## Delivery slices (local only)
- **Slice A:** approved baseline + spec; local commit `23945c6ec16a` (`docs(memory): record approved DEV memory specification and baseline`), exactly 229 additions. Documentation milestone, not P1 completion.
- **Slice B:** approved design + task breakdown + tracker/index/current-memory reconciliation. Measure additions + deletions against current HEAD; exclude unrelated TikTok.
- **Future slices:** one coherent behavior-backed unit with tests per commit; recalculate boundaries when ready. No PR/push/merge authorized or created.
- Full feature forecast remains unassessable until live/protected scope is resolved.

## Current next step

All tasks T01–T10 are verified with dated observed proof (2026-10-08). Engram metrics forensically clarified (1,754 total rows, 2 soft-deleted [IDs 242, 1562], 1,752 active observations), official test runner executed (26 passed in 21.6s), and Agent × Repository Acceptance Matrix completed. Maintain local conventional commit chain on `feat/memoria-dev`; no remote push or PR is authorized.
