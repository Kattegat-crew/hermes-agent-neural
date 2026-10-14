# Hermes Project Memory & Session Continuity

> **Session Lifecycle Contract**:
> - **On Session Start**: Read this file and [`ARCHITECTURE.md`](file:///opt/hermes-agent/ARCHITECTURE.md) to recover active context and understand current flows before taking any action.
> - **On Session Close**: Update this file with what was accomplished, verification results, and immediate next steps.

---

## 1. Active Focus & Current Goal
* **Current Initiative**: Gateway Restart Hardening & Spanish Stall Guard Resolution (Ticket Discord #1555307813868408966: "Gateway: reinicios cortan agentes + declara-y-no-ejecuta").
* **Scope**: Gateway shutdown timing forensics (`gateway/shutdown_forensics.py`), host watchdog stability (`/usr/local/bin/hermes-watchdog.sh`), safe restart CLI (`/usr/local/bin/hermes-safe-restart`), and Spanish action tail detection in turn loop (`agent/agent_runtime_helpers.py`).
* **Lead Agent**: Antigravity (`agy`) / Ragnar.
* **Target Path**: [`/opt/hermes-agent/`](file:///opt/hermes-agent/).
* **Approval & Test State**: Phase 1, 2, and 3 Implementation COMPLETE. Verified GREEN (10 passed in `tests/gateway/test_shutdown_forensics.py` and 40 passed in `tests/agent/test_stall_guards.py`).

---

## 2. Handover from Last Session
* **Current Handover (2026-10-14 — Gateway Restart Hardening & Spanish Stall Guard Resolution)**:
  - **Completed**:
    - **Host Stability & Watchdog Hygiene**:
      - Identified and terminated 554-restart crash loop on `hermes-agent-roshi.service` caused by `/usr/local/bin/hermes-watchdog.sh`. Removed `hermes-agent-roshi.service` from `UNITS`; stopped and disabled unit.
      - Discovered and fixed critical `TypeError` bug in `hermes-safe-restart.sh` (coercing `active_agents` int to `len(int)` was throwing exception and defaulting to 0 active agents). Created symlink `/usr/local/bin/hermes-safe-restart`.
      - Updated satellite restart scripts (`restart_gateway_glm53.sh`, `restart_gw_roshi_canal.sh`) to delegate safely to `/usr/local/bin/hermes-safe-restart`.
    - **Gateway Shutdown Timing Forensics**:
      - Fixed `_systemd_timeout_stop_us` in `gateway/shutdown_forensics.py` to check `LoadState=loaded` before accepting `--user` bus results. This eliminates false-positive warnings (`TimeoutStopSec=90s`) when running as a system unit with `TimeoutStopSec=360s`.
      - Added regression tests in `tests/gateway/test_shutdown_forensics.py` (verifying unloaded user unit fallback and loaded user unit).
    - **Spanish Stall Guard Resolution ("Declara y no ejecuta")**:
      - Extended `_TRAILING_CONTINUE_INTENT_RE` and `_PROMOTED_REASONING_PLAN_TAIL_RE` in `agent/agent_runtime_helpers.py` with Spanish action markers (`voy a`, `procedo a`, `ahora voy a`, `a continuación voy a`, `paso a`, `tengo que`, `debo`).
      - Added Spanish intent test cases in `tests/agent/test_stall_guards.py`.
    - **Ticket & Discord**:
      - Updated tag to "En curso" (`1554957746980261943`) and posted technical audit & agreed plan in Discord thread `1555307813868408966`.
  - **Verified by**:
    - `pytest tests/gateway/test_shutdown_forensics.py tests/agent/test_stall_guards.py` (50 collected, 49 passed, 1 skipped).
    - `systemctl status hermes-agent-roshi.service` inactive (dead) and disabled.
    - `/usr/local/bin/hermes-safe-restart` tested against active/idle states with RC=3 on active agents.

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

* **Current Handover (2026-10-14 — Semantic Project Grouping & Engram Alignment)**:
  - **Completed**:
    - Created `session_projects` in `/opt/hermes-agent-data/projects.db` with profile isolation and index.
    - Populated 12 official taxonomy projects in `projects.db`.
    - Deterministically mapped 504 sessions (480 crons + 24 CLI sessions) to their respective projects.
    - Classified remaining gateway sessions via Jev batch + subagent inheritance (841 total mapped, 168 transient in Home).
    - Unified Engram memory taxonomy across 1,776 observations, 166 sessions, and 787 prompts.
    - Extended `hermes_cli/projects_db.py`, `tui_gateway/project_tree.py`, and `tui_gateway/server.py` to natively support `session_projects` and non-cwd `Conversaciones` lanes in Desktop sidebar.
    - Added semantic reassignment API `POST /api/profiles/sessions/{session_id}/project`.
    - Authored `.specs/session-projects-sidebar/` (`01-spec.md`, `02-design.md`, `03-tasks.md`).
  - **Verified by**:
    - `python3 -m pytest tests/tui_gateway/test_project_tree.py tests/hermes_cli/test_projects_db.py` (42 passed).
    - End-to-end `GET /api/profiles/projects/tree` test via FastAPI TestClient (HTTP 200, all projects rendered).
    - End-to-end `POST /api/profiles/sessions/{id}/project` assignment verification.
    - `engram doctor --json` verified.

* **Current Handover (2026-10-14 — MCP Approval Persistence & Ragnar Audit Resolution)**:
  - **Completed**:
    - Implemented decoupled MCP approval persistence in `tools/approval.py` (`_mcp_session_approved`, `_mcp_permanent_approved_by_home`, `is_mcp_approved`, `approve_mcp_session`, `approve_mcp_permanent`, `revoke_mcp_permanent`, `save_permanent_mcp_allowlist`).
    - Added structured consent handler in `tools/approval_prompt.py` (`request_mcp_tool_consent`) preserving duration scopes (`once`, `session`, `always`).
    - Integrated gate check in `tools/mcp_tool_handlers.py` to consult allowlist and record grants.
    - Extended `/approvals` with `/approvals mcp` and `/approvals revoke mcp <server:tool>` in `gateway/slash_commands.py`.
    - Addressed Ragnar adversarial audit findings:
      - Fixed Finding 1: Enforced `policy.is_admin(user_id)` before handling `/approvals` subcommands, closing unauthorized inspection/revocation.
      - Fixed Finding 3: Removed test-only `Mock` shim in production `mcp_tool_handlers.py`; updated tests to mock `request_mcp_tool_consent` directly.
      - Documented Finding 2: Reconciled baseline mechanics in `02-design.md`, noting `/approvals revoke mcp` as the authoritative path.
    - Completed operational closure (Task 7):
      - Pushed branch `feat/upgrade-v0.22.0` to `origin`.
      - Reverted 13 write MCP servers in `/opt/hermes-agent-data/config.yaml` to `trust: untrusted`.
      - Restarted `hermes-agent.service` (teardown took 7.03s; PID 298544 loaded commit `7809f2f6d6`).
  - **Verified by**:
    - `pytest tests/tools/test_mcp_trust_gating.py` (22 passed).
    - `pytest tests/gateway/test_approvals_command.py` (4 passed, including non-admin rejection).
    - `pytest tests/gateway/test_discord_slash_commands.py` (14 passed).
    - `systemctl status hermes-agent.service` active and healthy under PID 298544.
    - Memory recorded in Engram (#1861, #1863, #1865).


* **Prior Handover (2026-10-14 — Post-v0.22.0 Upgrade Incident Resolution)**:
  - **Completed**:
    - **DEV WhatsApp & Python C-ABI Mismatch**:
      - Identified and resolved root cause for dropped WhatsApp messages to Roshi: in v0.22.0, profiles with `gateway.standalone: true` are excluded from multiplexed routes (`profiles_to_serve()`). Removed `gateway.standalone: true` in `/opt/hermes-agent-data/profiles/roshi/config.yaml`.
      - Stopped and disabled redundant standalone unit `hermes-agent-roshi.service`. Roshi is now cleanly multiplexed by the host gateway (serving default, roshi, and secondary profiles).
      - Fixed Python C-ABI mismatch: `hermes-agent.service` was executing Python 3.13 (`.venv`), while PM had provisioned Python 3.14.7 in `/opt/hermes-agent-data/installs/`, causing `ModuleNotFoundError: No module named 'pydantic_core._pydantic_core'` on turn execution. Updated unit to run the managed launcher `/opt/hermes-agent-data/home/.local/bin/hermes`.
    - **PROD Discord Cross-Talk / Agent Contamination**:
      - Identified and resolved root cause for Goldie (`golden-game`) and Lucky (`lucky-club`) replying on Bob's Discord channel (`1555019373385752617`). The Docker container `c52496bbd7e7` exported Bob's `DISCORD_BOT_TOKEN`, which sub-gateways inherited via s6 `with-contenv`.
      - Explicitly configured `platforms.discord.enabled: false` and `platforms.telegram.enabled: false` in `/opt/hermes/data/profiles/golden-game/config.yaml` and `/opt/hermes/data/profiles/lucky-club/config.yaml`.
      - Restarted `gateway-golden-game` and `gateway-lucky-club` via s6. Confirmed both sub-gateways only bind WhatsApp (ports 3001, 3002) and API server, eliminating all cross-talk on Discord.
  - **Verified by**:
    - DEV: `systemctl status hermes-agent.service` running PID 212021; `whatsapp` bridge connected on port 3000; `served_profiles` includes `default` and `roshi`; `roshi:discord` and `roshi:telegram` connected.
    - PROD: `s6-svstat` confirmed sub-gateways up; logs confirmed `Platform 'discord' is explicitly disabled... credentials found in the environment will NOT start its adapter`; Bob (`PID 327`) is the sole Discord bot connected.
    - Memory recorded in Engram (#1862).

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
