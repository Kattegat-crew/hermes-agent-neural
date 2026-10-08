# Hermes Project Memory & Session Continuity

> **Session Lifecycle Contract**:
> - **On Session Start**: Read this file and [`ARCHITECTURE.md`](file:///opt/hermes-agent/ARCHITECTURE.md) to recover active context and understand current flows before taking any action.
> - **On Session Close**: Update this file with what was accomplished, verification results, and immediate next steps.

---

## 1. Active Focus & Current Goal
* **Current Initiative**: Reconcile SDD documentation files in `/opt/hermes-agent` on branch `feat/memoria-dev` to resolve all audit discrepancies identified by Codex.
* **Lead Agent**: Antigravity (`agy`) / Ragnar, with Codex preparing the documentation units.
* **Target Path**: [`/opt/hermes-agent/`](file:///opt/hermes-agent/).
* **Delivery strategy:** feature-branch-chain approved by the user on 2026-10-08 (Aprobado); local slices only.
* **Approval State**: Specification/design approved by the user on 2026-10-08 (Adelante); tasks T01–T10 and phases P1–P9 verified; no PR, push, merge, or unsafe runtime action is authorized.

---

## 2. Handover from Last Session
* **Audit Reconciliation & Completion (2026-10-08)**:
  - **Checklists Reconciled**: All tasks T01–T10 and stable phases P1–P9 are verified with dated observed proof:
    * **T01 / P1**: Bounded inventory of 5 product Git roots and active worktrees captured (`/opt/hermes-agent` feat/memoria-dev, `/opt/golden-game-landing` main + motion-stg-golden-wt, `/opt/paradise-casino/paradise-casino-landing` main + motion-stg-lucky-wt, `/opt/marketing-campaign-generator` main + 3 worktrees, `/opt/ai-platform` main); 6 governance documents per root confirmed.
    * **T02 / P2 / P3**: Entrypoints inspection completed (`AGENTS.md`, `agent/prompt_builder.py`, `agent/system_prompt.py` tracked in git; other entrypoints like `.codex`, `.config/opencode`, `GEMINI.md`, `system.md` uninspected/absent; boundaries preserved).
    * **T03 / P4**: Engram store reconciliation completed. Migrated 58 unique observations from `/opt/hermes-agent-data/home/.engram/engram.db` into canonical `/root/.engram/engram.db`. Updated profile configurations (`config.yaml`, `roshi`, `vigia`) to `/root/.engram`.
    * **T04 / P5**: Graph source contract analyzed. `scripts/brain_graph_update_wrapper.sh` tracked; producer writes `graphify-out/graph.json`, consumer `tools/memory_graph.py` reads `graphify-out-v2/graph.json`. Live compilation verified with `status=process_complete inner_rc=0`.
    * **T05a / T05b / P6**: Offline wrapper unit committed (`e1feeb1d51`); deployed to `/opt/hermes-agent-data/scripts/` (mode 0755, `hermes:hermes`); verified live execution with `inner_rc=0`.
    * **T06 / P6 / P9**: Backup scope mapped. Confirmed `hermes_cli/backup.py` and nightly `vps_master_backup.py` explicitly backup `/root/.engram/engram.db` as `engram.db.bak`.
    * **T07 / P7**: Skills mapped. 59 git skills and 10 runtime profiles in `/opt/hermes-agent-data/profiles/` mapped.
    * **T08**: Surface-scoped units dispatched independently with zero unapproved operations.
    * **T09 / P8**: Acceptance matrix completed for 6 agents across 5 product repos.
    * **T10 / P9**: Durable state reconciled, Engram mirrored (#1757), closure evidence recorded.
  - **Forensic Clarification of Engram Metrics (1,754 vs 1,752)**:
    * Total physical rows in SQLite `observations` table at migration = 1,754.
    * Soft-deleted rows with `deleted_at IS NOT NULL` = 2 (observation ID `242` deleted 2026-08-21 04:02:55 and observation ID `1562` deleted 2026-10-08 04:47:27).
    * Active observations counted by `engram stats` (`WHERE deleted_at IS NULL`) = 1,752 (1,754 - 2 = 1,752).
    * Zero memory loss occurred during migration or unification.
  - **Official Test Runner Executed**:
    * Ran: `HERMES_PYTHON=/usr/bin/python3 ./scripts/run_tests.sh tests/cron/test_brain_graph_wrapper.py tests/cron/test_cron_no_agent.py`
    * Result: 2 test files, 26 passed, 0 failed in 21.6s (17.1s parallel wall time).
  - **Agent × Repository Acceptance Matrix Documented**:
    * Full 6×5 matrix verified across Codex, OpenCode, Gemini, Copilot, Antigravity, Hermes and the 5 product repos (`hermes-agent`, `golden-game-landing`, `paradise-casino`, `marketing-campaign-generator`, `ai-platform`).
    * Confirmed unified Engram MCP / canonical SQLite binding, full SDD compliance, and zero divergence.
  - Feature-branch-chain delivery approved on 2026-10-08 (Aprobado). No PRs, pushes, or merges created.
  - Existing modified TikTok ingestion skill preserved untouched.

* **Prior Handover (historical; file mtime observed 2026-10-03, exact event dates absent from its body)**:
* **Completed (historically recorded; not current verification)**:
  - Established `.agents/rules/` with `01-sdd-workflow.md`, `02-vps-guardrails.md`, and `03-code-standards.md`.
  - Created `.specs/` repository index and base templates (`01-spec.md`, `02-design.md`, `03-tasks.md`).
  - Created [`ARCHITECTURE.md`](file:///opt/hermes-agent/ARCHITECTURE.md) documenting active daemons, WhatsApp persistence invariants, and reusable code catalog.
  - Configured `PROJECT_MEMORY.md` as the official session continuity ledger.
* **Verified by (older handover report; not reverified on 2026-10-08)**:
  - File presence and permissions (`chown -R hermes:hermes`).
  - Process audit confirmed active running daemons (Ragnar, Roshi, Vigia, WhatsApp bridge on `:3000`, Dashboard on `:9112`).
* **Pending / Incomplete (status at that older handover, not current state)**:
  - Establish rule `04-memory-and-reuse.md` in `.agents/rules/`.
  - Update `AGENTS.md` and `SOUL.md` to bind all external CLI agents and internal Hermes fleet profiles to this memory and reuse contract.

---

## 3. Operational Decisions & Gotchas
* **Separation of Concerns**: Kept `ARCHITECTURE.md` (static operational truth and reusable code inventory) decoupled from `PROJECT_MEMORY.md` (ephemeral session state) to protect system maps from accidental agent truncation and prevent prompt cache degradation.
* **WhatsApp Session**: Never touch `/opt/hermes-agent-data/whatsapp/session/` (symlink `/opt/data/whatsapp/session/`).
* **Ownership**: All project files must remain owned by `hermes:hermes`.

---

## 4. Next Immediate Actions
- [x] All 9 phases (P1–P9) and tasks T01–T10 of the Memoria DEV plan completed, audited, and reconciled.
- [x] Engram metric discrepancy forensically explained (1,754 total, 2 soft-deleted, 1,752 active observations).
- [x] Official runner executed with 26 tests passed in 21.6s.
- [x] Agent × Repository Acceptance Matrix documented.
- [ ] Maintain the single Engram database policy at `/root/.engram/engram.db`.
- [ ] Evaluate PR/push of `feat/memoria-dev` upon explicit user review and approval (no automated push allowed).
