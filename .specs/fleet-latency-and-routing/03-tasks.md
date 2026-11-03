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

### Phase 3: KV-Cache Preservation & Preliminary Turn Triage (`agent/tool_guardrails.py`)
- [x] **Task 3.1**: Update `should_decouple_tools_for_turn` in `agent/tool_guardrails.py` so `tools_for_api = []` only fires on Turn 1 of a fresh session (`len(messages) <= 2`) for short unambiguous greetings/acks (<60 chars, no question marks or capability verbs), preserving `tools_for_api = agent.tools` on all active multi-turn sessions.
  - *Target Files*: `agent/tool_guardrails.py`, `tests/agent/test_tool_guardrails.py`
  - *Skill*: `.skills/code-review-and-quality/SKILL.md`
  - *Verification*: `/usr/local/bin/pytest tests/agent/test_tool_guardrails.py -v`

### Phase 4: Per-Agent Model Specialization, `OpenCode-Go` Failover Normalization, Dynamic Tiering & Config Shield
- [x] **Task 4.1**: Implement `apply_dynamic_turn_tiering` (`TaskComplexityRouter`) in `agent/turn_request_assembly.py` for `default` and `roshi` (L1 `glm5.3-flash` low / L2 `deepseek-v4-flash` medium / L3 `gpt-6.1-sol` or `deepseek-v4-flash` high), strictly respecting active failover (`agent._fallback_activated` or `agent.provider == "OpenCode-Go"`).
  - *Target Files*: `agent/turn_request_assembly.py`, `agent/tool_guardrails.py`
- [x] **Task 4.2**: Configure specialist primary models and normalize `fallback_providers` + `fallback_model` (Step 1: alternate `NaN-Builders` model; Step 2: `OpenCode-Go` / `mimo-v2.6-flash`) across all 12 profiles, fixing `vigia` `custom_providers`.
  - *Target Files*: `/opt/hermes-agent-data/config.yaml`, `/opt/hermes-agent-data/profiles/*/config.yaml`, `/opt/hermes-agent-data/config/fleet_model_policy.json`
- [x] **Task 4.3**: Implement `Config Shield` (`scripts/hooks/guard_config_model_mutation.py` + `model.lock_default_in_config` guard in `hermes_cli/web_server_config.py`).
  - *Target Files*: `scripts/hooks/guard_config_model_mutation.py`, `hermes_cli/web_server_config.py`

### Phase 5: Final Verification & Live Service Check
- [x] **Task 5.1**: Run unit test suites for memory, tool guardrails, fallback config, and Jev router, verify service health, and mark `.specs/README.md` status as `Completed`.
  - *Verification*: `/usr/local/bin/pytest tests/tools/test_memory_tool.py /opt/hermes-agent-data/plugins/typesafe-skill-router/tests/ -v`
