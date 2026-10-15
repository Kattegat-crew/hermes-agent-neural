# Hermes Project Memory & Session Continuity

> **Session Lifecycle Contract**:
> - **On Session Start**: Read this file and [`ARCHITECTURE.md`](file:///opt/hermes-agent/ARCHITECTURE.md) to recover active context and understand current flows before taking any action.
> - **On Session Close**: Update this file with what was accomplished, verification results, and immediate next steps.

---

## 1. Active Focus & Current Goal
* **Current Initiative**: Closed & Fully Verified — Model Matrix Finalization & Independent Disaster Fallback (Ticket Discord #1555029599203758160: "Modelos auxiliares y fallbacks — DEV/PROD (plan 26-sep)").
* **Scope**: NaN catalog sanitization, multi-tier fallback architecture (NaN primary -> NaN secondary -> OpenCode-Go Mimo disaster recovery), DEV satellite catalog purge, PROD in-memory runtime reload, and vision/API key homologation.
* **Lead Agent**: Antigravity (`agy`) / Ragnar.
* **Target Path**: [`/opt/hermes-agent/`](file:///opt/hermes-agent/).
* **Approval & Test State**: CLOSED & VERIFIED IN RUNTIME. Ragnar independent audit findings fully resolved: PROD gateways reloaded in-memory under s6 (default PID 676278, golden-game PID 676449, lucky-club PID 676467, casino watchdog exit 0), DEV satellite configs 100% purged of B.AI/mimo-v2.5/0731 (running under PID 1044193), PROD fallback keys corrected to `${NAN_BUILDERS_API_KEY}` and vision homologated to `mimo-v2.6-flash`.

---

## 2. Handover from Last Session
* **Current Handover (2026-10-15 — Post-Audit Remediation, Fleet Homologation & In-Memory Gateway Sync)**:
  - **Completed**:
    - **Ragnar Independent Audit Remediation**:
      - **PROD Gateway In-Memory Synchronization (Bloqueador 1)**: Executed safe reload of supervised services via s6 inside `hermes-agent` container (`s6-svc -t /run/service/gateway-*`). Gateways active with new PIDs: `gateway-default` (PID 676278), `gateway-golden-game` (PID 676449), `gateway-lucky-club` (PID 676467). Verified WhatsApp bridges connected on ports 3001 and 3002; `casino_gateways_watchdog.py` returned exit code 0 (`ALL HEALTHY`).
      - **DEV Satellite Catalog Purge (Bloqueador 2 & 3)**: Purgados `B.AI`, `mimo-v2.5`, y `deepseek-v4-flash-0731` en todos los 11 perfiles de `/opt/hermes-agent-data/profiles/*/config.yaml`. Declarado `mimo-v2.6-flash` (1,048,576 context length, `supports_vision: true`). Cero referencias residuales en DEV.
      - **PROD API Keys & Vision Homologation (Menores)**: Corregidos saltos 0 y 1 de `fallback_providers` en los 11 configs de PROD para usar `${NAN_BUILDERS_API_KEY}` hacia el proxy rate-limited. Homologado `auxiliary.vision: mimo-v2.6-flash` con `supports_vision: true` en todos los satélites de PROD.
      - **DEV Multiplex Gateway Reload**: Gateway DEV recargado y operando estable bajo PID 1044193.
  - **Verified by**:
    - PROD s6 service status (`s6-svstat` uptime and fresh PIDs).
    - PROD `casino_gateways_watchdog.py` exit code 0.
    - DEV config audit script (12/12 configs: `bai=False`, `m25=False`, `d731=False`, `m26=True`).
    - DEV process verification (PID 1044193 active, WhatsApp bridge connected).

* **Prior Handover (2026-10-15 — Initial Model Matrix, NaN Catalog Sanitization & Independent Disaster Fallback)**:
  - **Completed**:
    - **NaN-Builders Live Catalog Sanitization**:
      - Verified live `/v1/models` against NaN-Builders API (13 active models).
      - Purged obsolete models `mimo-v2.5` and `deepseek-v4-flash-0731` from `providers.NaN-Builders.models` and `custom_providers`.
      - Declared `mimo-v2.6-flash` (1,048,576 context length, `supports_vision: true`) in both `NaN-Builders` and `OpenCode-Go` catalogs.
      - Removed circular/dead provider `B.AI` from `fallback_providers`.
    - **Multi-Tier Model Routing & Universal Disaster Fallback**:
      - Enforced business hierarchy:
        - Primary: 100% NaN-Builders (`deepseek-v4-flash` in PROD; `glm5.3-flash` in DEV).
        - Secondary (NaN internal fallback): `deepseek-v4-flash` in DEV; `qwen3.8-flash` in PROD.
        - Tertiary External Disaster Fallback: `mimo-v2.6-flash` @ `OpenCode-Go` (triggered only when NaN is completely offline, protecting PROD).
    - **Profile Fleet Drift Elimination**:
      - Propagated `smart_model_routing.cheap_model: glm5.3-flash` across all 9 satellite profiles (`bragi`, `brokkr`, `comms`, `freyja`, `heimdall`, `hermodr`, `sindri`, `ullr`, `vili`), fully eliminating legacy `qwen3.6` cost leaks.
      - Updated `auxiliary.vision` in PROD to `mimo-v2.6-flash` (native omni video/image understanding).
      - Backed up all 12 DEV and 11 PROD configs with `.bak-pre-fallback-final-20261015`.
    - **Safe Gateway Reload**:
      - Safely restarted `hermes-agent.service` under PID 1010599 with zero turn interruptions.
  - **Verified by**:
    - `load_config()` verification in `hermes_cli.config`.
    - `pytest tests/agent/test_model_metadata.py` (117 passed in 33.91s).
    - Live probe against `opencode.ai/zen/go/v1` (`mimo-v2.6-flash` returned `OPERATIVO`).
    - `systemctl status hermes-agent.service` active and operational.

* **Prior Handover (2026-10-15 — Google Multi-Account Support & Strict Tenant Secret Isolation)**:
  - **Completed**:
    - **Google MCP Multi-Account Refactor (`ncl_google_mcp.py`)**:
      - Identified and resolved dictionary key overwrite collision in `load_owner_connections` where multiple active Google accounts for the same profile masked earlier accounts (e.g. Ragnar had 4 Gmails but only saw `digitalexpresiones1`, Helmer had 2 but only saw `helmerparra`).
      - Refactored `load_owner_connections` to index all active connections per service with preferred defaults (`DEFAULT_ACCOUNTS: default -> jonathan-gmail (jonathaun124@gmail.com), helmer -> helmer-gmail (helmerparra@gmail.com)`).
      - Added `account` optional parameter across all Google tools (`gmail_list`, `gmail_digest`, `gmail_read`, `gmail_send`, `drive_search`, `drive_read_text`, `calendar_list_events`).
      - Added read-only inspection tool `google_list_accounts` to surface available accounts and defaults.
      - Added `--secrets-dir` CLI flag to support per-profile physical secret directory isolation.
    - **Roshi Privacy Leak Resolution**:
      - Discovered `/opt/hermes-agent-data/profiles/roshi/config.yaml` was incorrectly passing `--profile default` to `ncl_google` and `ncl_google_write`.
      - Corrected both configurations to `--profile roshi`.
      - Extracted and materialized Chucho's credentials from ActivePieces DB via `verify_connection.py` into `/opt/hermes-agent-data/secrets/chucho-*.json` (Gmail, Drive, Calendar for `Jemadiar1@gmail.com` with `0600` permissions).
      - Verified bidirectional isolation: Roshi only accesses Chucho's data; Ragnar only accesses Jonathan/NeuralCrew data.
    - **Client Agent Onboarding Hardening & SOP**:
      - Updated `/opt/hermes-agent-data/hermes-profiles/templates/config.yaml`: removed `terminal` from client toolsets (leaving only `web`), fixed legacy docker paths to `/opt/hermes-agent-data/`, and bound `ncl_google` to `--secrets-dir /opt/hermes-agent-data/profiles/__PERFIL__/secrets`.
      - Updated `/opt/hermes-agent-data/hermes-profiles/scripts/onboard-agent.sh`: automated creation of client-specific `secrets/` directory with `0700` permissions and updated native paths.
  - **Verified by**:
    - In vivo unit suite testing: default account resolution, dynamic `account` selector, cross-tenant unauthorized account rejection, and `--secrets-dir` isolated sandbox execution.
    - `systemctl status hermes-agent.service` active and operational.
    - `systemctl status hermes-dashboard.service` active on port 9112.

* **Prior Handover (2026-10-14 — Context Compression 300k, Multimodal Standardization & Ticket Closure)**:
  - **Completed**:
    - **Multimodal & Context Window Incompatibility Resolution**:
      - Identified root cause of auto-lowered threshold: `qwen3.8-flash` in `NaN-Builders` has a 262,144 token window, causing Hermes to automatically clamp the 300k threshold to 262,144 on session init.
      - Discovered `auxiliary.vision` was pointing to `deepseek-v4-flash`, which lacks video understanding for `tools/vision_tools.py` (`video_analyze`).
      - Updated `/opt/hermes-agent-data/config.yaml`:
        - Set `auxiliary.compression.model: glm5.3-flash` (1M window, enabling genuine 300k threshold).
        - Set `auxiliary.vision.model: glm5.3-flash` (native omni-modal support: text, image, video).
        - Homologated `providers.NaN-Builders.models.glm5.3-flash.context_length` from `400000` to `1000000` to eliminate divergence with `custom_providers`.
    - **Model Metadata Static Catalog Patch**:
      - Added unhyphenated aliases `"glm5.3-flash": 1_048_576, "glm5.3": 1_048_576` to `_KNOWN_MODEL_CONTEXT_LENGTHS` in `agent/model_metadata.py`. This prevents decoupled lookups from falling back to generic `202752`.
    - **Discord UX & In-Place Progress Streamlining**:
      - Updated `display.platforms.discord` in `config.yaml`: `tool_progress: 'all'`, `tool_progress_grouping: accumulate`, `cleanup_progress: true`, `interim_assistant_messages: false`. Avoids separate chat commentary bubbles, updates status in-place, and cleans up on completion.
    - **Live Audit & Gateway Safe Restart**:
      - Ragnar completed comprehensive live audit in Discord thread `1555436381042516008`, validating image & video live probes against NaN-Builders API and confirming 300k threshold feasibility.
      - Executed `/usr/local/bin/hermes-safe-restart`, cleanly draining and reloading gateway (PID 500433) with commit `c336482e35` in memory.
    - **Ticket & Discord**:
      - Posted final closing resolution in Discord thread `1555436381042516008`, updated tags to "Cerrado" (`1554957746980261945`), and archived thread.
  - **Verified by**:
    - `pytest tests/agent/test_model_metadata.py` (117 passed in 21.35s).
    - `pytest tests/gateway/test_display_config.py` (19 passed).
    - In vivo feasibility check: `check_compression_model_feasibility` maintains `threshold_tokens=300000` with zero auto-lowered warnings.
    - Live probes by Ragnar: Image PNG and MP4 video analysis successful against NaN-Builders.
    - `systemctl status hermes-agent.service` active and operational.

* **Prior Handover (2026-10-14 — Gateway Restart Hardening & Spanish Stall Guard Resolution)**:
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
