# Hermes Project Memory & Session Continuity

## Initiative Record — Ephemeral Progress Heartbeat & Uniform Channel Architecture (2026-10-22)
- **Post-audit saneo (2026-10-22, ordered by Chucho)**:
  - **Flood brake restored**: the 30-sep edit-flood livelock brakes (`_FLOOD_ABANDON_WAIT_SECS`/`_FLOOD_EDIT_COOLDOWN_SECS`/`_FLOOD_EDIT_FAILURE_LIMIT` + helpers and cooldown gate in `edit_message`) had been silently lost from `plugins/platforms/telegram/adapter.py` (same working-tree-switch loss class as `fca052407a`). Re-applied via `git cherry-pick 0595377f43` (conflicts hand-merged onto the current `_edit_text` helper and the #116312 chat-outbound-budget gate; cooldown skip placed BEFORE the budget gate so `skipped_reason: edit_flood_cooldown` wins). Commit `1a8d3391ba` preserves original authorship; `test_telegram_edit_flood_storm.py` 5/5.
  - **Test-collection root cause**: the execution environment exports `PYTHONPATH=<3.14 venv site-packages>`, so bare `pytest` (system 3.12) imported binary-incompatible wheels (pydantic_core/PIL._imaging/_cffi_backend/python-multipart failures) and file-order sys.path pollution broke 6+ modules in single-process runs. Fix: run the suite as `env -u PYTHONPATH HERMES_PYTHON=/usr/bin/python3.12 scripts/run_tests.sh` (canonical per-file isolation). The «138/138» in the deploy report was an 8-FILE subset, never the whole `tests/gateway/` dir.
  - **Bridge de-sync closed**: deployed `/opt/hermes-agent-data/scripts/whatsapp-bridge/` was an older bridge.js variant (no mentions/group-policy). Backed up to `.backup-pre-saneo-20261022/`, synced repo files over, SIGTERM'd the node process; the gateway watcher respawned it with the repo script — `/health` reports the new `scriptHash`, status connected, `/edit` + `/delete` probed 400, session untouched.
  - **Root-owned artifacts** (from earlier root-run operations): `.pytest-cache` locks (cleaned), `.git` refs/logs for this branch (rebuilt by hand), `installs/ffad2f5543956651/inputs/` (STILL root-owned, 0500-root — blocks `pm.testenv` sync in `scripts/run_tests.sh`; needs root chown to restore the canonical testenv lane).
- **Status**: Authorized corrections are functionally verified and activated on the local DEV main and Vigia gateways (2026-10-22). The root/default gateway serves Roshi through six enabled per-contact WhatsApp route rules over the same connected bridge used by default/Ragnar. No additional Roshi adapter, pairing, or QR is required. No fresh end-to-end inbound-contact canary was run; commit, native review, publication target, and a live progress-message canary remain pending. SDD: `.specs/ephemeral-progress-heartbeat-cleanup/{01-spec,02-design,03-tasks}.md`.
- **Authorized activation and routing (2026-10-22)**: the main safe-restart and Vigia systemd restart exited 0; their new processes stayed active/running with automatic restart count 0. The existing root WhatsApp bridge health check returned HTTP 200 and connected after restart. The root config and runtime matcher validate six enabled contact routes: Jesús/Chucho to Roshi and Jonathan to default/Ragnar, each accepting LID/JID/number forms. Roshi is a hosted logical runtime; its own WhatsApp adapter remains intentionally disabled while routed turns use the shared receiving adapter and paired bridge. No pairing credentials were deleted/reset, no QR was needed/generated/sent, and no Discord message was sent. No fresh end-to-end inbound contact canary was performed.
- **Superseded pre-activation check (2026-10-22 16:00 UTC)**: At that time, main and Vigia processes predated the source and no restart had yet been authorized. The later authorized activation above supersedes that process-readiness conclusion. The earlier note remains as historical evidence, not current status.
- **Architectural Shift: Standard Per-Channel Behavior**:
  - Rather than fragmenting configurations per agent, behaviors are standardized per platform:
    - **Telegram**: Single-bubble replacement (`tool_progress_grouping: replace`) + post-delivery ephemeral cleanup (`cleanup_progress: true`).
    - **Discord**: Thread-aware in-place replacement + post-delivery ephemeral cleanup (`delete_message` thread resolution prevents 404 Unknown Message).
    - **WhatsApp**: Baileys bridge in-place editing (`POST /edit` within 15-minute window) + ephemeral cleanup via `POST /delete` revoke endpoint (`{ delete: key }`), integrated cleanly into `WhatsAppAdapter.delete_message`. Prevents history pollution, SQLite `state.db` inflation, and token blowups.
    - **Hermes Desktop**: Native streaming transcript.
  - Channel policy is shared, but profile configuration does not automatically inherit the root file. Effective settings resolve through the active home file, environment expansion, managed overlay, and normalization; root plus 11 profile display blocks are replicated deliberately. A shared display policy does not prove that every profile adapter is enabled.
- **Multi-Agent Safeguard (Anti-Loop)**:
  - In shared channels/threads where 2+ agents interact (e.g. `#digital-vikings` thread `1562442815676616704`), live progress edits and heartbeats are completely muted via `is_multi_agent_chat` in `gateway/display_config.py` and `gateway/run_turn.py`. This suppresses configured progress-triggered events; it does not prove that every possible bot loop is impossible.
- **Conversational Spanish & Dynamic Heartbeat**:
  - Restored missing `long_running.*` i18n keys in `locales/es.yaml` and `locales/en.yaml`.
  - Progress shows natural Spanish actions with resource context (e.g. *⏳ Revisando archivos `run_turn.py` (22s)*) with no raw code fences or loop iteration counters (`busy_ack_detail: false`).
  - Dynamic heartbeat timing configured to 20s via `agent.gateway_notify_interval: 20` in `config.yaml`.
  - **Desactivación de `interim_assistant_messages: false`**: Se identificó que las frases intermedias ("¡Buena pregunta, mi chavo!...", "Ya tengo la mayoría verificadas...") correspondían a narración intermedia de LLM enviada como mensajes permanentes (`role=assistant`), acumulándose en el chat y rompiendo el ciclo efímero. Al apagarse (`false`), el chat solo recibe la burbuja de progreso efímero y un único mensaje final.
- **Auditoría de Codex & Remediación Integral (2026-10-22)**:
  - *Re-auditoría Codex (#2201/#2202) y Remediación Final*:
    1. **Telegram Supergroup/Topic Cleanup**: En `_run_agent_schedule_bubble_cleanup` (`gateway/run_turn.py`), se fijó `_chat_id_snapshot = turn_ctx.source.chat_id`. Anteriormente se priorizaba `thread_id`, lo que causaba error `Chat not found` en supergrupos con tópicos de Telegram y `channel_not_found` en Slack.
    2. **Discord Heartbeat Edit Metadata**: En `_run_agent_notify_long_running`, `edit_message` ahora pasa `metadata=_interim_metadata(_non_conversational_metadata(_status_thread_metadata, platform=source.platform))` cuando el método lo acepta (`_accepts_keyword`), garantizando edición correcta en hilos y foros de Discord.
    3. **Formato de Duración Exclusivamente en Español**: Se implementó `format_duration_es(elapsed_seconds)` en `gateway/run.py` formateando duraciones limpias en español (`20 s`, `1 min`, `2 min`, `1 h 15 min`). Se unificaron los templates de `working_heartbeat` en `locales/de.yaml` y `locales/fr.yaml` con `{duration}`.
    4. **Resolución de Intervalo de Notificación (Env Var <= 0)**: Se implementó `resolve_gateway_notify_interval` en `gateway/run.py`, soportando explícitamente desactivación cuando `HERMES_AGENT_NOTIFY_INTERVAL <= 0` o `user_config.agent.gateway_notify_interval <= 0`, con fallback a 20.0s.
    5. **Deduplicación de Tests Unitarios**: `tests/gateway/test_ephemeral_progress.py` fue actualizado para invocar directamente `resolve_gateway_notify_interval` y `format_duration_es`, e incluye verificación de enrutamiento a `source.chat_id` en supergrupos con tópicos de Telegram. (32/32 tests pasando).
  - *Punto 1 (Propagación Flota)*: Replicado el bloque estándar de canales (`display.platforms`), `multi_agent_channels` y `gateway_notify_interval: 20` en los 11 perfiles de `/opt/hermes-agent-data/profiles/*/config.yaml`, dado que `config_effective.py` no hereda del root.
  - *Punto 2 (Formato Duración)*: Corregido `{duration}` en `locales/*.yaml` y `run_turn.py` eliminando el sufijo duplicado `20s min`.
  - *Punto 3 (Desactivación Intervalo 0)*: Corregido `_NOTIFY_INTERVAL` en `run_turn.py` para respetar explícitamente `0` (desactivación) sin forzar `20.0` mediante `or`.
  - *Punto 4 (Contrato Booleano WhatsApp)*: Eliminado `@_needs_bridge` en `WhatsAppAdapter.delete_message`, retornando un booleano estricto `False` ante puente desconectado (evitando instancias `SendResult` truthy).
  - *Punto 5 (Hilos Discord en Edición)*: Añadido soporte de `metadata.get('thread_id')` y fallback en `DiscordAdapter.edit_message()` ante error `10008` (Unknown Message).
- **Verification**:
  - Earlier handover reported unit tests in `tests/gateway/test_ephemeral_progress.py` (11/11), `tests/gateway/test_display_config.py` (19/19), and `tests/gateway/test_activity_labels.py` (11/11). These historical results do not verify the current correction candidate.
- **Authorized Audit Corrections (2026-10-22)**:
  - Heartbeat text and status metadata now enter the existing per-turn progress queue and are serialized by `TurnRunner.send_progress_messages`; queue setup includes heartbeat-only turns with tool progress off. Replace-mode adapters without edits, or with permanent edit failures, suppress repeated heartbeat sends after one message.
  - Configured multi-agent IDs now match `source.parent_chat_id` in addition to chat/thread IDs; the legacy `multi_agent_chats` alias and unrelated-parent negative case are covered.
  - Initial correction candidate passed the exact 8-file regression suite at 133/133; independent actual-method verification exposed three edges, then follow-up tests and the exact 8-file suite passed 138/138. An independent verifier repeated the latest suite with 138 passed and exit 0. The authorized runtime activation is recorded above; no profile configuration was changed and no fresh inbound-contact or live progress-message canary was performed.
- **Pending Follow-up**:
  - Standalone general audit for unused/dead code and documentation cleanup across `/opt/hermes-agent`.

## Current Initiative — Gateway Shutdown/Restart Discord Reporting via Vigía & Non-Blocking Auto-Resume (2026-10-17)
- **Vigía Discord Gateway Monitoring**: Configured Vigía to report gateway restarts, shutdowns, and crashes for `hermes-agent.service` (Ragnar / Roshi multiplex) to Discord via Vigía's Discord webhook (`/opt/hermes-agent-data/profiles/vigia/scripts/vigia_post_discord.py`).
- **Systemd Drop-in & Notifier**: Installed `/opt/hermes-agent-data/scripts/hermes-service-notify.sh` (symlinked to `/usr/local/bin/hermes-service-notify.sh`) and systemd drop-in `/etc/systemd/system/hermes-agent.service.d/40-vigia-notify.conf` using `ExecStopPost=` to capture all service stop results (`$SERVICE_RESULT`, `$EXIT_CODE`, `$EXIT_STATUS`), cleanly distinguishing planned restarts (code 75), normal shutdowns (code 0), and crashes/failures.
- **Watchdog Integration**: Updated `/usr/local/bin/hermes-watchdog.sh` to dispatch Vigía Discord alerts when `hermes-agent.service` is detected down, successfully recovered, or persistently down after restart.
- **Dead Script Cleanup**: Removed obsolete legacy container s6-era scripts in `/opt/hermes-agent-data/scripts/` (`cron_gateway_restart.sh`, `gateway_restart_once.sh`, `gateway_restart_glm53.sh`, `restart_gateway_contexto_400k.sh`, `phase_d_restart_cleanup.sh`, `phase_f2_restart_suppress.sh`, `rename_roshi_restart.sh`).
- **Notice Suppression Status**: Configured `gateway_restart_notification: false` in `/opt/hermes-agent-data/config.yaml` and Roshi's config; in-chat/home-channel restart notices are cleanly suppressed for Discord and Telegram while keeping cron/restart acks intact.
- **Legacy Cron Cleanup (2026-10-20)**: Removed legacy weekly heartbeat cron `latido-semanal-gateways` (`6a4ac3ee5077`) from Ragnar's scheduler (`jobs.json`) to prevent duplicate Monday gateway status postings on Discord, consolidating gateway monitoring exclusively in Vigía.
- **Roshi WhatsApp Context Recovery & Full Purge (2026-10-20)**: Fixed per-turn context amnesia for Roshi on WhatsApp (`chat_id: 153580212334603@lid`). Root cause was legacy zombie keys `agent:rochi:whatsapp:dm:153580212334603` (and `ragnarcho`) in `sessions.json` and `gateway_routing` referencing the same active `session_id` (`20260828_151313_d014449e`). Following resolution, performed a complete system purge requested by user: confirmed 0 tables named `rochi`/`ragnarcho`; purged all zombie routing keys in `bragi` and `sindri`; updated 15 session `profile_name` entries to `roshi`; sanitized `system_prompts` text across 11 profiles; fixed `vigia-fallback-watchdog.py`; and deleted all `.bak` files from today's operation along with all legacy backup artifacts and scripts in `backups/` and `archive/`. All 95 conversation turns now load properly into active context.
- **Engineering Skills Evolution (2026-10-20)**: Audited `mattpocock/skills` repository. Preserved strict SDD governance and Engram memory protocols while successfully incorporating key engineering disciplines: added `codebase-design` (Ousterhout deep modules and Feathers seams) and `wizard` (interactive bash HITL scripts with `template.sh`) to local engineering skills in `hermes-agent` and `ai-platform`; added `improve-codebase-architecture` with HTML visual reports to the central catalog; upgraded `code-review-and-quality` with isolated Two-Axis parallel sub-agent review (Standards / Fowler 12 code smells vs Spec / SDD requirement fidelity); and enriched `test-driven-development` with anti-patterns against change-detector tests and test source-code reading.
- **Controlled Pause & Auto-Resume (`hermes-safe-restart`)**: Replaced the previous hard block (`exit 3`) with a non-blocking graceful pause and resume mechanism. When active agents are detected during an intentional restart, the script marks them as `resume_pending=True` (`resume_reason='restart_timeout'`) in `sessions.json` and `state.db` (table `gateway_routing`), removes `.clean_shutdown`, and restarts the service. Upon boot, `_schedule_resume_pending_sessions()` in `gateway/run_startup.py` immediately synthesizes continuation events to resume the interrupted tasks without human intervention.


## Current Initiative — Lightweight Hermes Observability on Existing Langfuse (2026-10-17)
- SDD: `.specs/langfuse-fleet-observability/{01-spec,02-design,03-tasks}.md`; `.specs/langfuse-fleet-observability/04-migration.md` is historical/declined evidence only. User rejected the heavy v3/v4 migration and approved assessing the minimum compatibility fix for Hermes against existing Langfuse `2.95.11`.
- Selected catalog plugin is version `2.0.0` / source SHA `c2a95963c442f3f23e4bc6fe0da898e1dd1fb63d`, pinned to SDK `4.15.2`. DEV PM Python `3.14.7` import passed independent review; PROD import is diagnostic-worker evidence only. Server `2.95.11` is below the SDK v3/v4 floor `3.63.0`. The legacy SDK2 CPython 3.13 overlay failure is separate and not the selected runtime's root cause; do not globally downgrade SDK4.
- Short `langfuse` alias: 8 enabled in DEV/PROD; legacy `observability/langfuse`: 10 DEV / 11 PROD. Root profiles disabled; two PROD test profiles unconfigured. Alias coexistence does not prove duplicate traces.
- The public official plugin source chain is rooted at tracker revision `c2a95963c442f3f23e4bc6fe0da898e1dd1fb63d`. Unit 1 `fix/langfuse-v2-rest-01-transport` is commit `e52545c16942f33398c371a75a0cea5ffdacec4f`; unit 2 `fix/langfuse-v2-rest-02-hermes-hooks` is commit `de4c12af69e119e2fdde6d744fc8f19bb9e66cef`, parented exactly to unit 1. Both are local child branches; no push, PR, or main merge. User selected `feature-branch-chain`.
- Unit 1 native RDD review (lineage `review-7160735dc2c73400`, frozen candidate digest `4e090ccd7b1e8d0dd0eab2e8f7e6fabe2f7c9f2719103e76aa29d0b89e900457`) ended approved with two nonblocking advisories; exact acknowledgement burned authority. Do not rerun unchanged unit 1. Unit 2 assessment against unit 1 returned `review_due=false`, `under_budget`, not approval of the entire feature. Full source suite 155 passed, 2 skipped; SDK standalone contract exit 0; repo diff checks passed. Native review advisories are follow-up notes, not auto-corrected blockers.
- One blocked HTTP call cannot be cancelled while the worker is busy; saturation/process exit can drop telemetry; arbitrary response buffering is unbounded; 50 ms is a per-flush wait, not shutdown bound. No live ingestion or DEV validation is proven.
- L1 discovery, L2 adapter/tests, and L3 independent review are complete. A DEV canary still needs the named authorized profile/environment, credential injection scope, privacy/capture audit, and explicit activation authorization; PROD remains unchanged and separately gated. Codex/OpenCode/AGY remain deferred without parity promise.
- Project credential references and effective `HERMES_LANGFUSE_CAPTURE` remain unknown; `sanitized` is not content-free. No secrets or values may be copied. No runtime/dependency/service/production changes or traces have been made; local source code/test changes are in the two commits above.
- No new services, collectors, cloud resources, server migration, or Codex/OpenCode/AGY parity promise. Other client integrations are deferred. DEV canary requires named-environment, credential, privacy, and activation authorization; PROD requires explicit destination/operation/credential scope.
- Prior migration sizing/backup evidence remains in the declined historical proposal; it is not a current blocker for the lightweight route. The approved local strategy is `feature-branch-chain`; publication remains unauthorized.

> **Session Lifecycle Contract**:
> - **On Session Start**: Read this file and [`ARCHITECTURE.md`](file:///opt/hermes-agent/ARCHITECTURE.md) to recover active context and understand current flows before taking any action.
> - **On Session Close**: Update this file with what was accomplished, verification results, and immediate next steps.

---

## 1. Active Focus & Current Goal
* **Current Initiative**: Completed & Verified — Tiered Cascading Skill Selection (Tier 1 Predetermined -> Tier 2 Global Fallback) via TypeSafe Jev Router (`typesafe-skill-router` v1.1.0).
* **Scope**: Per-agent specialist skill routing based on Roshi & Yisus fleet architecture (2026-09-25 consensus & R2-bis), sub-second single-chunk routing for in-domain queries (<$0.0004 USD), seamless fallback to 708-skill global catalog for cross-domain requests, full catalog access preserved (`skills.on_demand: true`), plugin activation across all 11 profiles.
* **Lead Agent**: Antigravity (`agy`) / Senior Architect.
* **Target Path**: [`/opt/hermes-agent-data/plugins/typesafe-skill-router/`](file:///opt/hermes-agent-data/plugins/typesafe-skill-router/), [`/opt/hermes-agent-data/config/agent_tier1_skills.json`](file:///opt/hermes-agent-data/config/agent_tier1_skills.json).
* **Approval & Test State**: CLOSED & VERIFIED IN RUNTIME. In vivo live routing verified on DEV host with TypeSafe System One (`jev-latest`): in-domain Nginx query routed in 1 chunk to `nginx-certbot-reverse-proxy` (fits 0.90, $0.0002 USD); out-of-domain video query seamlessly cascaded to Tier 2 and routed to `akari-video-editing` / `video-reel-pipeline` (fits 0.85); all 70 unit tests passed; `hermes-agent.service` active under PID 2004458.

---

## 2. Handover from Last Session
* **Current Handover (2026-10-17 — Skills Catalog Audit & Consolidation, Router Option A, and Fleet Reflex Matrix)**:
  - **Completed**:
    - **Global Skills Catalog Hygiene & Purge**:
      - Purged graveyard `skills/_retirados` and all 79 `*.pre-rename-20260929` junk residue files permanently.
      - Resolved collisions (`vault-access` promoted to `core/vault-access/SKILL.md`).
      - Fixed all 36 broken YAML frontmatters using block scalars `>-` (0 broken YAMLs across tree).
      - Purged noise: Wall Street financial models, macOS desktop utilities, Amazon e-commerce, and 27 `specialists/ai-ml/` frontier training recipes.
      - Fused 7 scattered clusters into canonical Spanish core skills: `copy-quality-es`, `hermes-cron-ops`, `meta-ads-ops`, `vps-deployment-ops`, `hermes-provider-ops`, `multi-agent-collaboration`, `google-workspace-ops`, and `brain-knowledge-ops`.
      - Purged framework-specific and generic code stubs migrating to repo-level SDD (`autoskills`), leaving Hermes central skills dedicated strictly to fleet & system operations, business, campaigns, multimedia, and multi-agent coordination.
      - Reduced catalog from 708 to 560 verified skills across 8 clean top categories. 0 stubs (<100 words), 0 broken YAMLs.
    - **TypeSafe (Jev) Skill Router — Option A (On-Demand Tool Routing)**:
      - Expanded `INDEX_WIDTH` from 60 to 180 characters in `typesafe_router/roster.py` to preserve rich context and triggers.
      - Registered `skill_route` as an on-demand tool (`toolset="skills"`) with schema and handler in `typesafe-skill-router` v1.1.0.
      - Exposed `pre_hook_enabled` toggle and configured `pre_hook_enabled: false` across `/opt/hermes-agent-data/config.yaml` and all 11 profiles (`profiles/*/config.yaml`), guaranteeing 0 accidental Jev fires on chitchat/conversation and zero wasted tokens.
      - Unit test suite: 75 passed in 1.61s (including new `tests/test_skill_route_tool.py`).
    - **Operational Reflex Matrix in `AGENTS.md`**:
      - Installed the concise 14-line **Mapa Canónico de Recursos e Infraestructura** across all 11 profiles and root default `ragnar`.
      - Canonical channels established: Vaultwarden (`/usr/local/bin/vw`), Google Workspace MCP (`ncl_google`), Google Drive & Sheets API (`google-workspace-ops`), ActivePieces (`http://localhost:3000`), Twenty CRM, Composio Meta Ads, and VPS Host execution (`ssh -o BatchMode=yes root@10.0.2.1`).
      - Zero plaintext secrets exposed; all `AGENTS.md` maintained under 70 lines (far below the 300-line ceiling).
  - **Verified by**:
    - Comprehensive python audit (`Total skills: 560, Categories: 8, Broken YAML: 0, Stubs: 0`).
    - `pytest` in `typesafe-skill-router` (75 passed in 1.61s).
    - `git status` clean in both repositories.

  - **Completed**:
    - **Fleet-Wide Predetermined Skill Manifest**:
      - Compiled [`/opt/hermes-agent-data/config/agent_tier1_skills.json`](file:///opt/hermes-agent-data/config/agent_tier1_skills.json) based on Roshi's authoritative report (`diseno-catalogos-por-agente-20260925.md`) and `gen_agentes_skills.py`.
      - Mapped 11 profiles: `brokkr` (58), `sindri` (54), `hermodr` (46), `roshi` (39), `bragi` (39), `freyja` (34), `ullr` (34), `vili` (33), `heimdall` (33), `vigia` (31), `comms` (24), all including the 13 shared fleet hygiene skills.
      - 100% of skills in manifest verified to exist in live canonical tree (`/opt/hermes-agent/skills/`).
    - **TypeSafe Skill Router (`typesafe-skill-router` v1.1.0)**:
      - Extended `__init__.py` with tiered cascading: evaluates Tier 1 first (fast single-chunk, <1s, ~$0.0002–$0.0004 USD).
      - If Tier 1 produces a winner with `gate >= 0.30` and `fits >= 0.40`, returns immediately.
      - If Gate < 0.30 (conversational chit-chat/prose), skips Tier 2 and stays silent.
      - If Gate >= 0.30 but Tier 1 has no fit (out-of-domain task), cascades automatically to Tier 2 (the rest of the 707 canonical skills).
      - Resolved profile session context via `gateway.session_context.get_session_env("HERMES_SESSION_PROFILE")`, `ctx.profile_name`, and environment fallback.
      - Added fallback in `typesafe_router/client.py` to root `/opt/hermes-agent-data/.env`.
      - Added comprehensive test suite (`tests/test_tier1_cascading.py`); 70/70 tests passing.
    - **Profile Fleet Configuration & Gateway Activation**:
      - Symlinked `typesafe-skill-router` into all 11 profiles (`/opt/hermes-agent-data/profiles/*/plugins/`).
      - Updated `config.yaml` across all 11 profiles and root to enable `typesafe-skill-router` with `tier1_enabled: true` and `fallback_to_global: true`.
      - Fixed permissions (`hermes:hermes`) and safely restarted `hermes-agent.service` (PID 2004458).
  - **Verified by**:
    - `pytest` in `typesafe-skill-router` (70 passed in 1.50s).
    - CLI status checks across profiles (`hermes typesafe-skill-router status`).
    - Live in vivo routing probes against TypeSafe System One (`jev-latest`):
      - In-domain Brokkr Nginx query -> Tier 1 hit (`nginx-certbot-reverse-proxy`, 1 chunk, $0.000234 USD).
      - Out-of-domain Brokkr Reel query -> Tier 1 miss -> Tier 2 cascade hit (`akari-video-editing` / `video-reel-pipeline`, fits 0.85).
    - Runtime service status (`systemctl status hermes-agent.service`, PID 2004458 active).

* **Prior Handover (2026-10-15 — Post-Audit Remediation, Fleet Homologation & In-Memory Gateway Sync)**:
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

* **Current Handover (2026-10-16 — Skills SSOT, Fleet Catalog Resolution & Jev Router Reconnection)**:
  - **Completed**:
    - **Skills Canonical Path (SSOT)**: Replaced dead path `/opt/hermes/skills/` with native `/opt/hermes-agent/skills/` in `/opt/hermes-agent-data/AGENTS.md` and `/opt/hermes-agent-data/profiles/roshi/AGENTS.md`.
    - **Fleet-wide Native Catalog Binding**: Configured `skills.external_dirs: ["/opt/hermes-agent/skills"]` with `on_demand: true` across all profiles in `/opt/hermes-agent-data/profiles/` (`roshi`, `bragi`, `brokkr`, `comms`, `freyja`, `heimdall`, `hermodr`, `sindri`, `ullr`, `vigia`, `vili`) and `default`.
    - **Catalog Resolution Verified**: Default profile restored from 74 to 782 skills; Roshi profile restored from 1 to 709 skills, with 0 token bloat in system prompt via progressive disclosure (`skills.on_demand: true`).
    - **TypeSafe (Jev) Skill Router Reconnection**: Injected `TYPESAFE_API_KEY` into `/opt/hermes-agent-data/.env` from `/opt/hermes-agent-data/secrets/typesafe.json`. Configured `roster_dir: /opt/hermes-agent/skills` and enabled state under `plugins.entries.typesafe-skill-router.settings` in `/opt/hermes-agent-data/config.yaml`.
    - **Live Jev Verification**: Verified two-stage typed routing in vivo across 707 skills (Nginx query routed to `nginx-certbot-reverse-proxy` with fits 0.85; Reel query routed to `akari-video-editing` with fits 0.74, cost ~$0.0018 USD).
    - **Service Restart**: Cycled `hermes-agent.service` (PID 1964959) cleanly.
  - **Verified by**:
    - Python runtime `_skill_catalog`: Default profile = 782 skills, Roshi = 709 skills.
    - Python `suggest(client, ...)` test: live HTTP 200 to TypeSafe System One (`jev-latest`), sub-3s response.
    - `systemctl status hermes-agent.service` active and healthy.

* **Prior Handover (2026-10-14 — Semantic Project Grouping & Engram Alignment)**:
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
* **Skills Architecture & Hardening (2026-10-20)**:
  - Formally specified under `.specs/canonical-skills-rollout/` (Approved).
  - 15 stack engineering skills in `.agents/skills/` (aliased via `.skills/`), mirrored to `.claude/skills/` with zero broken symlinks, indexed in `.atl/skill-registry.md`.
  - Hardened `template.sh` in `wizard`: `write_env` strictly rejects symlinks, validates POSIX variable identifiers (`^[A-Za-z_][A-Za-z0-9_]*$`), creates `0600` temp files, and replaces atomically (`mv -f`). Verified with `tests/test_template_hardening.sh`.
  - Fleet catalog integrity: 100% of the 574 `SKILL.md` files pass native `_validate_frontmatter` with 0 syntax or delimiter errors.
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
