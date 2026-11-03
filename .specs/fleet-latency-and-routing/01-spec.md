# Feature Specification: Fleet Latency, Zero-Default-Load Routing & Model Specialization

* **Status**: Approved
* **Author**: Argon / Senior Architect
* **Target Module**: `agent/`, `tools/`, `hermes_cli/`, `/opt/hermes-agent-data/`
* **Created**: 2026-11-03
* **Updated**: 2026-11-03

---

## 1. Problem Statement & Motivation
* **What is the problem?**
  1. **Conversational Latency & Default Memory Load**: Profiles such as `roshi` experience up to 77.7s response times (54.2s LLM prefill) on simple conversational turns due to:
     - Uncompacted historical sessions in `state.db` (`roshi` carrying 64,279 tokens across 163 messages; `default` carrying up to 557 messages).
     - Mid-session tool decoupling (`tools_for_api = []` in `agent/turn_request_assembly.py:205-208` via `should_decouple_tools_for_turn` in `agent/tool_guardrails.py:828`), which mutates the request prefix mid-conversation and invalidates the provider's KV-cache.
     - `MemoryStore._render_compact_index` (`tools/memory_tool_store.py:194, 666-699`) enforcing `index_char_limit >= 500` (default `6000`) and injecting ~60 `MEMORY.md` entries into the Turn-1 System Prompt even when `memory.on_demand: true`, while `profiles/*/config.yaml` omit the `memory:` section entirely (`user_char_limit` falling back to `1375` chars) and `_memory_turn_start_and_prefetch` (`agent/turn_context.py:922`) runs on conversational turns.
  2. **Jev (`typesafe-skill-router`) Cost & Recall Bugs**:
     - `agent_tier1_skills.json` lacks a `"default"` (Ragnar) key and `hermes_home()` in `typesafe-skill-router/__init__.py:82` reads `os.environ.get("HERMES_HOME")` instead of `hermes_constants.get_hermes_home()`, forcing 100% of logged calls into `tier=global` (3 chunks across 560 skills).
     - `typesafe_router/router.py:399-403` discards valid Stage-2 winners (`fits >= 0.40`) whenever `best_fits - winner_fits < fits_margin` (`0.15`), causing a 30% false-negative `tool:no_fit` rate.
     - `handle_skill_route` omits `recent_context` and `rank_wide` sends 3 paid `GATE_QUESTIONS` even when `enforce_gate=False`.
  3. **`USER.md` Bloat & Missing Deferred MCPs**: All 12 profiles share a ~7,260-char `USER.md` that omits most active `lazy: true` MCP servers (31 in Ragnar, 29 in Roshi, 1-7 in specialists), causing capability hallucinations when agents do not know which deferred MCPs exist behind `tool_search`.
  4. **Unshielded Model Configuration & Fallback Alignment**: Switching models in Hermes Desktop (`POST /api/model/set`) or via natural-language chat commands overwrites `model.default` in `config.yaml`, flattening all profiles to `glm5.3-flash`. Additionally, assigning `deepseek-v4-flash` on `NaN-Builders` requires adjusting `fallback_model[0]` so it does not self-loop, while strictly preserving `OpenCode-Go` (`mimo-v2.6-flash`) as the cross-provider outage fallback.

* **Why solve it now?** Enforces true Zero-Default-Load for skills and `MEMORY.md` (eliminating 50s-77s context prefill spikes on conversational turns), cuts Jev routing costs by ~70% while eliminating false `no_fit` misses, prevents capability hallucinations at the input layer, and protects per-agent model specialization and `OpenCode-Go` failover across the 12-agent fleet.

---

## 2. Goals & Non-Goals
### Goals
- [x] Enforce **Zero-Default-Load** on Turn 1 for both Skills (`skills.on_demand: true`) and `MEMORY.md` (`memory.on_demand: true`, `memory.index_char_limit: 0`), letting the primary LLM read, reason over the message, and autonomously invoke `memory(action="search", ...)` or `skill_route(query, context)` without hardcoded keyword/regex classifiers.
- [x] Preserve provider KV-cache prefixes 100% across all turns by keeping `tools_for_api = agent.tools` constant (`should_decouple_tools_for_turn` disabled) and keeping the model constant per session without per-turn L1/L2/L3 model swapping.
- [x] Fix Jev (`typesafe-skill-router`) profile resolution (`get_hermes_home()`), add `"default"` to `agent_tier1_skills.json`, pass contextual `recent_context`, fix the Stage-2 `fits_margin` false-negative bug, and skip `GATE_QUESTIONS` when `enforce_gate=False`.
- [x] Configure domain-optimal primary models per specialist on `NaN-Builders` (`deepseek-v4-flash` with `reasoning_effort: medium` for `default` and `roshi`), while preserving and normalizing the `NaN-Builders` -> `OpenCode-Go` (`mimo-v2.6-flash`) fallback chain.
- [x] Fold `vigia` into the central multiplexer (`hermes-agent.service`) for cron execution while adding an external post-crash/post-restart recovery auditor (`hermes-post-recovery-audit.py`) that reports downtime, root cause, and missed jobs to Discord.
- [x] Prune all 12 `USER.md` files into dense, role-scoped operational maps that retain 100% of execution paths (`vw`, `ssh dev`/`ssh prod`, Google Workspace, ActivePieces, `skill_route`, `tool_search`) and explicitly list each profile's deferred MCP servers.
- [x] Implement `Config Shield` (`fleet_model_policy.json`, session-scoped Desktop model switches unless explicitly unlocked, and `pre_tool_call` guardrail blocking chat-driven mutations of `config.yaml`).

### Non-Goals (Out of Scope)
- Hardcoded keyword/regex/length classifiers (`classify_turn_intent`, `classify_turn_complexity`, `_L3_COMPLEXITY_PATTERNS`, `check_runtime_execution_guardrails`) or output-side runtime regex/retry wrappers (`capability-claim-guard`). All routing and escalation are driven by semantic reasoning of the LLM.
- Modifying WhatsApp session state (`/opt/hermes-agent-data/whatsapp/session/`).

---

## 3. User Stories & Functional Requirements
* **US-1 (Zero-Default-Load & Native Semantic Reasoning without Keyword Classifiers)**: As an operator messaging any agent, I want turns to execute with Zero-Default-Load without loading `MEMORY.md` or skills by default, while keeping the session KV-cache 100% intact and allowing the model to reason over the message without regex word lists blocking tools.
  * **Requirement 1.1**: `MemoryStore` (`tools/memory_tool_store.py`) must allow `index_char_limit: 0` when `on_demand: true`, rendering only a 4-line on-demand pointer in the System Prompt with zero `MEMORY.md` entries preloaded.
  * **Requirement 1.2**: `_memory_turn_start_and_prefetch` (`agent/turn_context.py`) must only skip external memory prefetch when `is_trivial_prompt(query)` is `True` (single-word acks/greetings), without regex intent classifiers.
  * **Requirement 1.3**: `should_decouple_tools_for_turn` (`agent/tool_guardrails.py`) must always return `False`, keeping `tools_for_api = agent.tools` constant on every turn so the provider KV-cache prefix never invalidates and tools are never stripped by keyword heuristics.

* **US-2 (Contextual Skill Routing via Jev)**: As an agent facing a specialized task, I want to query `skill_route(query, context)` by contextual intent so Jev returns and auto-loads the matching `SKILL.md` in one step at minimal cost.
  * **Requirement 2.1**: `typesafe-skill-router` must resolve active profiles via `hermes_constants.get_hermes_home()` and route `"default"` (Ragnar) through Tier 1 (`agent_tier1_skills.json`) before falling back to Tier 2.
  * **Requirement 2.2**: When `winner_fits >= fits_threshold` (0.40) and `best_fits - winner_fits < fits_margin` (0.15), `suggest()` in `typesafe_router/router.py` must return `(winner, best_name)` instead of `()`.
  * **Requirement 2.3**: When `enforce_gate=False` (explicit `skill_route` tool call), `rank_wide()` must omit the 3 `GATE_QUESTIONS` from the TypeSafe payload.

* **US-3 (Per-Agent Model Specialization, KV-Cache Stability & OpenCode-Go Failover)**: As the system architect, I want each agent to run its domain-optimal model (`deepseek-v4-flash` at `medium` effort for `default` and `roshi`) without per-turn model swapping that breaks KV-cache, while preserving the `OpenCode-Go` (`mimo-v2.6-flash`) backup when `NaN-Builders` fails.
  * **Requirement 3.1**: Every profile's `config.yaml` must declare both `fallback_providers` and `fallback_model` with explicit `provider` and `model` keys: Step 1 = secondary model on `NaN-Builders` (distinct from `model.default`), Step 2 = `{"provider": "OpenCode-Go", "model": "mimo-v2.6-flash"}`.
  * **Requirement 3.2**: `apply_dynamic_turn_tiering` in `agent/tool_guardrails.py` must not swap models per turn using regex/length rules; it must only ensure that if active failover (`agent._fallback_activated` or `agent.provider == "OpenCode-Go"`) is engaged, the model stays pinned to `mimo-v2.6-flash` on `OpenCode-Go`.

* **US-4 (`USER.md` Pruning, Config Shield & Vigía Multiplex Consolidation)**: As an operator, I want `USER.md` to contain all canonical paths and deferred MCP servers concisely, `config.yaml` shielded from chat/GUI overwrites, and `vigia` folded into the central multiplexer with external post-restart recovery auditing.
  * **Requirement 4.1**: All 12 `USER.md` files must be rewritten into telegraphic role-scoped documents (<2,200 chars for Ragnar/Roshi, <1,300 chars for specialists) listing all active `lazy: true` MCP servers and canonical execution paths.
  * **Requirement 4.2**: `Config Shield` must block agent-initiated mutations to `config.yaml` model keys via a `pre_tool_call` hook (including Python/Node/Ruby inline interpreters and shell redirections) and scope Desktop UI model switches to the active session when `model.lock_default_in_config: true`.
  * **Requirement 4.3**: `vigia` must run inside the central multiplexer (`hermes-agent.service` ticking `profiles/vigia/cron/jobs.json`), while `/usr/local/bin/hermes-post-recovery-audit.py` hooks into systemd `ExecStopPost`/`ExecStartPost` to audit and report service restarts, crash causes, permission repairs, and missed cron jobs to Discord.

---

## 4. Acceptance Criteria & Invariants
* **Scenario 1: Conversational Turn Latency & KV-Cache Preservation**
  * **Given**: An active multi-turn session in `roshi` or `default`.
  * **When**: The user sends `"Hola Roshi, ¿cómo estás?"` or an implicit request without imperative verbs.
  * **Then**: `tools_for_api` and `agent.model` (`deepseek-v4-flash`) remain 100% identical to the session's cached prefix, no tools are blocked by regex guardrails, and prompt prefill executes with 0 preloaded memory entries (P50 total turn turnaround bounded only by remote provider `NaN-Builders` TTFT ~4-8s).
* **Scenario 2: Close-Margin Stage-2 Skill Routing in Jev**
  * **Given**: Two skills in `typesafe-skill-router` both score `fits >= 0.40` (e.g., `0.82` and `0.78`, margin `0.04 < 0.15`).
  * **When**: The agent invokes `skill_route(query="...", context="...")`.
  * **Then**: `suggest()` returns `(winner, runner_up)` instead of `()`, and `handle_skill_route` auto-loads the winner's `SKILL.md` content in a single turn.
* **Scenario 3: `NaN-Builders` Outage Failover to `OpenCode-Go`**
  * **Given**: `NaN-Builders` returns connection/5xx errors or is unavailable.
  * **When**: Any of the 12 agents (including `default` or `roshi` with dynamic tiering enabled) executes a turn.
  * **Then**: The runtime fails over to `OpenCode-Go` (`mimo-v2.6-flash` at `https://opencode.ai/zen/go/v1`), and `TaskComplexityRouter` preserves the `OpenCode-Go` provider without forcing the request back to `NaN-Builders`.

---

## 5. Security, VPS & Operational Considerations
* No new environment variables required; uses existing `${NAN_BUILDERS_API_KEY}`, `${OPENCODE_GO_API_KEY}`, and `${TYPESAFE_API_KEY}` from `.env` (`0600`).
* Preserves ownership `hermes:hermes` across `/opt/hermes-agent-data/`.
* Strictly honors Hermes's core prompt-caching invariant (`AGENTS.md`): never mutates `system_prompt` or `tools_for_api` mid-session.

---

## 6. Applicable Project Skills
- [x] `.skills/codebase-inspection/SKILL.md` — Subsystem exploration and dependency tracing
- [x] `.skills/api-and-interface-design/SKILL.md` — Tool schemas, gateway contracts, and plugin interfaces
- [x] `.skills/systematic-debugging/SKILL.md` — Root-cause analysis and edge-case verification
- [x] `.skills/code-review-and-quality/SKILL.md` — Clean architecture, prompt-cache preservation, and test coverage
