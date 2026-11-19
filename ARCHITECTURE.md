# ARCHITECTURE.md — Hermes Agent Core (`/opt/hermes-agent`)

## 1. System Topology & Boundaries
`/opt/hermes-agent` is the core engine repository (`prod-stable` branch, downstream of `NousResearch/hermes-agent`). Runtime configuration, profiles, cron jobs, memory stores, and user-installed plugins live separately in `/opt/hermes-agent-data` (`HERMES_HOME`).

| Subsystem | Path | Role |
| :--- | :--- | :--- |
| **Agent Core** | `agent/` (`prompt_builder.py`, `system_prompt.py`, `turn_context.py`, `subdirectory_hints.py`, `plugin_llm.py`) | 3-tier KV-cache prompt assembly (`stable`, `context`, `volatile`), context file discovery, subdirectory hints, and bounded plugin LLM bridge (`PluginLlm`). |
| **Gateway & Runtime** | `gateway/` (`run.py`, `run_bootstrap.py`, `cwd_placeholder.py`), `run_agent.py` | Multi-platform messaging gateway (Telegram, Discord, WhatsApp, CLI/TUI, API) and profile scoping (`multiplex_profiles`). |
| **CLI & Plugin Host** | `hermes_cli/` (`plugins.py`, `plugins_context.py`, `plugins_dispatch.py`, `plugins_state.py`, `plugin_capabilities.py`, `config.py`) | Plugin discovery (`<repo>/plugins/` + `$HERMES_HOME/plugins/`), `PluginContext`, hook worker dispatch, reserved root checks, and config bridging (`terminal.cwd` -> `TERMINAL_CWD`). |
| **Tools & Memory** | `tools/` (`memory_tool_store.py`, `skills_tool.py`, `hook_output_spill.py`) | On-demand memory search (`MemoryStore`), skill loading, and `10,000`-char hook spill protection. |
| **Bundled Fleet Catalog** | `skills/`, `optional-skills/`, `plugins/` | Shipped product skills and bundled plugins (distinct from repo engineering skills in `.skills/` -> `.agents/skills/`). |

---

## 2. Core Invariants
1. **Prompt Caching (KV-Cache)**: System prompt stays byte-stable per conversation; per-turn dynamic context (`pre_llm_call`) injects strictly into the user turn (`agent/turn_context.py`).
2. **Narrow Waist**: Keep `agent/` minimal; extend via `$HERMES_HOME/plugins/`, skills, or service-gated tools.
3. **Context File Precedence**: `.hermes.md` / `HERMES.md` wins when present (nearest match walking up to the git root). Then the AGENTS chain runs git root → cwd, each directory contributing the first **non-empty** of `AGENTS.override.md` → `AGENTS.md` → `agents.md`. `CLAUDE.md` / `claude.md` are cwd-only (first non-empty) and `.cursorrules` plus `.cursor/rules/*.mdc` are cwd-only and concatenated. `SubdirectoryHintTracker` disables itself while the working dir is home-like — `Path.home()`, a container home (`/home`, `/root`, `/workspace`), a child of one, or any path whose parts include `.home` / `host-home` / `host_home` — so a Desktop/container fallback cwd cannot vacuously pull every `AGENTS.md` under the user's home.

---

## 3. Reusable Code Catalog (Check Before Coding)
* `agent/plugin_llm.py`: `PluginLlm.complete(messages, ...)` and `PluginLlm.complete_structured(instructions=..., input=..., system_prompt=..., json_mode=...)` (note `complete()` does NOT accept `system_prompt=`).
* `tools/memory_tool_store.py`: `MemoryStore` section splitting, IDF scoring, and `mode=ro` safety checks.
* `tools/hook_output_spill.py`: `spill_if_oversized()` (`10,000`-char cap).
* `agent/subdirectory_hints.py`: `SubdirectoryHintTracker` (`_MAX_HINT_CHARS = 32_000`).
* `hermes_cli/plugins_state.py`: Reserved plugin config root validation (`_PLUGIN_SETTING_RESERVED_ROOTS`).
