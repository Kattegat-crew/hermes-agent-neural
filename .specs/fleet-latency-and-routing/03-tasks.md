# Implementation Tasks: Fleet Latency, Zero-Default-Load Routing & Model Specialization

* **Associated Spec**: [01-spec.md](./01-spec.md)
* **Associated Design**: [02-design.md](./02-design.md)
* **Status**: Completed

---

## Execution Guidelines
1. **TDD First**: Write or update unit tests before or alongside each runtime change.
2. **Atomic Verification**: Run the verification command after each phase.
3. **Zero Regression on Failover**: Verify that `OpenCode-Go` (`mimo-v2.6-flash`) remains configured and reachable as the cross-provider fallback across all 12 profiles.

---

## Task Checklist

### Phase 1: Zero-Default-Load Memory (`index_char_limit: 0`), `USER.md` Dense Rewrite & Session Compaction
- [x] **Task 1.1**: Update `MemoryStore` in `tools/memory_tool_store.py` to support `index_char_limit: 0` when `on_demand: true` (rendering only the 4-line on-demand header with zero preloaded `MEMORY.md` entries) and gate `_memory_turn_start_and_prefetch` in `agent/turn_context.py` on `not is_conversational_turn(_query)`.
  - *Target Files*: `tools/memory_tool_store.py`, `agent/turn_context.py`, `tests/tools/test_memory_tool.py`
  - *Skill*: `.skills/code-review-and-quality/SKILL.md`
  - *Verification*: `/usr/local/bin/pytest tests/tools/test_memory_tool.py -v`
- [x] **Task 1.2**: Add explicit `memory:` config (`user_char_limit: 8000`, `on_demand: true`, `index_char_limit: 0`) to `/opt/hermes-agent-data/config.yaml` and all 12 `/opt/hermes-agent-data/profiles/*/config.yaml`, and rewrite all 13 `USER.md` files into dense, role-scoped operational maps including each profile's active `lazy: true` MCP inventory.
  - *Target Files*: `/opt/hermes-agent-data/config.yaml`, `/opt/hermes-agent-data/profiles/*/config.yaml`, `/opt/hermes-agent-data/memories/USER.md`, `/opt/hermes-agent-data/profiles/*/memories/USER.md`
  - *Skill*: `.skills/api-and-interface-design/SKILL.md`
  - *Verification*: `python3 -c "import glob, pathlib; [print(p, len(pathlib.Path(p).read_text())) for p in sorted(glob.glob('/opt/hermes-agent-data/**/USER.md', recursive=True))]"`
- [x] **Task 1.3**: Rotate/archive bloated active sessions (>80 messages) in `state.db` across `roshi`, `default`, `bragi`, `sindri`, `brokkr`, `heimdall`, and `vigia`.
  - *Target Files*: `/opt/hermes-agent-data/state.db`, `/opt/hermes-agent-data/profiles/*/state.db`
  - *Verification*: Verify 0 active unended sessions with `message_count > 80` across all `state.db` files.

### Phase 2: Jev (`typesafe-skill-router`) Contextual Routing & Cost Optimization
- [x] **Task 2.1**: Add `"default"` profile (~45 core skills) to `/opt/hermes-agent-data/config/agent_tier1_skills.json` and update `hermes_home()` in `/opt/hermes-agent-data/plugins/typesafe-skill-router/__init__.py` to use `hermes_constants.get_hermes_home()`.
  - *Target Files*: `/opt/hermes-agent-data/config/agent_tier1_skills.json`, `/opt/hermes-agent-data/plugins/typesafe-skill-router/__init__.py`
  - *Skill*: `.skills/systematic-debugging/SKILL.md`
- [x] **Task 2.2**: Update `skill_route` schema and `handle_skill_route` in `__init__.py` to accept contextual `query` + optional `context` (`recent_context`), fix Stage-2 `fits_margin` tie silencing in `typesafe_router/router.py:367-404`, and skip `GATE_QUESTIONS` in `rank_wide` when `enforce_gate=False`.
  - *Target Files*: `/opt/hermes-agent-data/plugins/typesafe-skill-router/__init__.py`, `/opt/hermes-agent-data/plugins/typesafe-skill-router/typesafe_router/router.py`, `/opt/hermes-agent-data/plugins/typesafe-skill-router/tests/test_router.py`
  - *Verification*: `/usr/local/bin/pytest /opt/hermes-agent-data/plugins/typesafe-skill-router/tests/ -v`

### Phase 3: 100% Removal of Keyword Classifiers & KV-Cache Preservation (`agent/tool_guardrails.py`)
- [x] **Task 3.1**: Remove all regex/keyword/length classifiers (`classify_turn_intent`, `classify_turn_complexity`, `_L3_COMPLEXITY_PATTERNS`, `is_conversational_turn`, `check_runtime_execution_guardrails`) from `agent/tool_guardrails.py` and keep `tools_for_api = agent.tools` constant across all turns so the provider KV-cache prefix never mutates and tools are never blocked by keyword lists.
  - *Target Files*: `agent/tool_guardrails.py`, `agent/turn_request_assembly.py`, `agent/turn_context.py`, `agent/agent_runtime_helpers.py`, `tests/agent/test_turn_intent_triage.py`
  - *Skill*: `.skills/code-review-and-quality/SKILL.md`
  - *Verification*: `sudo -u hermes scripts/run_tests.sh tests/agent/test_turn_intent_triage.py`

### Phase 4: Per-Agent Model Specialization, `OpenCode-Go` Failover Normalization, Config Shield & Vigía Multiplex Consolidation
- [x] **Task 4.1**: Simplify `apply_dynamic_turn_tiering` in `agent/tool_guardrails.py` to remove per-turn model swapping (keeping `default` and `roshi` consistently on `deepseek-v4-flash` with a hot KV-cache) while preserving the `OpenCode-Go` (`mimo-v2.6-flash`) failover pin.
  - *Target Files*: `agent/tool_guardrails.py`, `/opt/hermes-agent-data/config.yaml`, `/opt/hermes-agent-data/profiles/roshi/config.yaml`
- [x] **Task 4.2**: Configure specialist primary models and normalize `fallback_providers` + `fallback_model` (Step 1: alternate `NaN-Builders` model; Step 2: `OpenCode-Go` / `mimo-v2.6-flash`) across all 12 profiles, fixing `vigia` `custom_providers`.
  - *Target Files*: `/opt/hermes-agent-data/config.yaml`, `/opt/hermes-agent-data/profiles/*/config.yaml`, `/opt/hermes-agent-data/config/fleet_model_policy.json`
- [x] **Task 4.3**: Implement `Config Shield` (`scripts/hooks/guard_config_model_mutation.py` + `model.lock_default_in_config` guard in `hermes_cli/web_server_config.py`).
  - *Target Files*: `scripts/hooks/guard_config_model_mutation.py`, `hermes_cli/web_server_config.py`, `tests/agent/test_guard_config_model_mutation.py`
- [x] **Task 4.4**: Fold `vigia` into the central multiplexer (`hermes-agent.service`), disable `hermes-agent-vigia.service`, and deploy `/usr/local/bin/hermes-post-recovery-audit.py` + systemd hooks to report post-crash/post-restart recovery diagnostics to Discord.
  - *Target Files*: `/opt/hermes-agent-data/profiles/vigia/config.yaml`, `/usr/local/bin/hermes-post-recovery-audit.py`, `/usr/local/bin/hermes-service-notify.sh`, `/usr/local/bin/hermes_fleet_watchdog.sh`

### Phase 5: Final Verification & Live Service Check
- [x] **Task 5.1**: Run unit test suites for memory, tool guardrails, fallback config, and Jev router, verify service health, and mark `.specs/README.md` status as `Completed`.
  - *Verification*: `/usr/local/bin/pytest tests/tools/test_memory_tool.py /opt/hermes-agent-data/plugins/typesafe-skill-router/tests/ -v`
