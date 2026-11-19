# Feature Specification: Unified SDD Governance Across `/opt/hermes-agent` and `/opt/hermes-agent-data`

* **Status**: Completed
* **Author**: Antigravity Architect
* **Target Scope**: `/opt/hermes-agent` (`AGENTS.md`, `ARCHITECTURE.md`, `.agents/rules/`, `.specs/`), `/opt/hermes-agent-data` (`AGENTS.md`, `ARCHITECTURE.md`, `PROJECT_MEMORY.md`, `.agents/rules/`, `.gitignore`, `config.yaml`, `profiles/*/AGENTS.md`)
* **Created**: 2026-11-17
* **Updated**: 2026-11-17

---

## 1. Problem Statement & Motivation

* **What is the problem?**
  1. **Invisible SDD entry point in `/opt/hermes-agent`**: `/opt/hermes-agent/AGENTS.md` is unmodified upstream Nous Research (`a8e49b25c7`) and never references `.specs/`, `PROJECT_MEMORY.md`, `.agents/rules/01-04`, or `.atl/skill-registry.md`. Meanwhile, `/opt/hermes-agent/ARCHITECTURE.md` does not exist despite being mandated by `.agents/rules/04-memory-and-reuse.md`, and `.agents/rules/03-code-standards.md` (`pytest`) conflicts with `AGENTS.md:138` (`scripts/run_tests.sh`).
  2. **Broken SDD targets in `/opt/hermes-agent-data`**: `/opt/hermes-agent-data/AGENTS.md:79-85` requires reading `PROJECT_MEMORY.md` and `.agents/rules/01-sdd-workflow.md`, neither of which exists at `/opt/hermes-agent-data` (nor does `ARCHITECTURE.md`). Strict whitelist `.gitignore` (`/*`) also omits `.agents/` and `.atl/`.
  3. **Hermes daemon self-editing blind spot**: Both `hermes-agent.service` and `hermes-agent-roshi.service` set `HOME=/opt/hermes-agent-data/home`, `HERMES_HOME=/opt/hermes-agent-data`, and `config.yaml` sets `terminal.cwd: .`. At startup `gateway/run_bootstrap.py:599` resolves `TERMINAL_CWD` to `Path.home()` (`/opt/hermes-agent-data/home`), which causes `SubdirectoryHintTracker._is_home_like_working_dir()` (`agent/subdirectory_hints.py:123-155`) to **disable subdirectory hint discovery completely**. Furthermore, `SubdirectoryHintTracker._within_working_dir()` (`line 249`) blocks hints across `/opt/hermes-agent` when `working_dir` is `/opt/hermes-agent-data`. Consequently, Hermes agents self-editing scripts, profiles, plugins, or core files never receive subdirectory `AGENTS.md` hints and miss SDD rules.

* **Why solve it now?**
  External coding agents (`agy`, `codex`, `opencode`, `claude`) and Hermes fleet daemons (`Ragnar`, `Roshi`, etc.) routinely switch between `/opt/hermes-agent`, `/opt/hermes-agent-data`, and `$HERMES_HOME/plugins/*`. Without a unified, verifiable SDD contract loaded at entry in both trees, agents skip specifications, invent code, or fail to update `PROJECT_MEMORY.md`.

---

## 2. Goals & Non-Goals

### Goals
- [x] **G1 — Option A Header in `/opt/hermes-agent/AGENTS.md`**: Prepend a concise NCL SDD governance header in `/opt/hermes-agent/AGENTS.md` (preserving all upstream Nous rules below intact) so Hermes, Codex, OpenCode, and AGY all load SDD rules automatically at startup.
- [x] **G2 — Complete Missing Governance Files in Both Repos**: Create `/opt/hermes-agent/ARCHITECTURE.md`, and add `PROJECT_MEMORY.md`, `ARCHITECTURE.md`, and `.agents/rules/01..04` to `/opt/hermes-agent-data/` (whitelisted in `/opt/hermes-agent-data/.gitignore`).
- [x] **G3 — Reconcile Contradictions & Stale Pointers**: Align `.agents/rules/03-code-standards.md` with `AGENTS.md:138` (`scripts/run_tests.sh` vs targeted plugin `pytest`), update `/opt/hermes-agent-data/AGENTS.md` skills SSOT pointer (`/opt/hermes-agent-data/skills/`), and remove duplicated SDD boilerplate from `profiles/*/AGENTS.md` in favor of root inheritance.
- [x] **G4 — Hermes Self-Editing SDD Enforcement**: Reactivate `SubdirectoryHintTracker` for Hermes daemons by setting `terminal.cwd: /opt/hermes-agent-data` (instead of `.` -> `Path.home()`), add explicit self-editing SDD rules for Hermes agents, and evaluate a lightweight cross-tree SDD guard for edits touching `/opt/hermes-agent` or `$HERMES_HOME/{plugins,scripts,profiles}`.

### Non-Goals (Out of Scope)
- Modifying core `Pre-Lector Cognitivo` routing logic in `typesafe-skill-router` (tracked separately in `plugins/typesafe-skill-router/.specs/pre-lector-cognitivo-hardening/`).
- Changing Hermes's upstream `prompt_builder.py` / `subdirectory_hints.py` core discovery engine unless strictly needed (prefer configuration + governance + optional hook over core patches).
- Modifying `MEMORY.md` routine operational entries or profile `SOUL.md` personas.
- Committing or pushing changes to GitHub remotes without explicit human approval.

---

## 3. User Stories & Functional Requirements

* **US-1**: As any coding agent (`agy`, `codex`, `opencode`, `claude`, `hermes`) starting in `/opt/hermes-agent`, I want `AGENTS.md` to immediately enforce SDD (`01-spec.md` -> `02-design.md` -> `03-tasks.md` -> Phase 4) and point to `PROJECT_MEMORY.md`, `ARCHITECTURE.md`, `.agents/rules/`, and `.skills/` (excluding `skills/` fleet catalog).
  * **Req 1.1**: `/opt/hermes-agent/AGENTS.md` begins with an NCL SDD header block pointing to all required governance files and clarifying the `/opt/hermes-agent` vs `/opt/hermes-agent-data` boundary.
  * **Req 1.2**: `/opt/hermes-agent/ARCHITECTURE.md` exists and documents core topology, Narrow Waist, plugin runtime, and reusable modules.
  * **Req 1.3**: `.agents/rules/03-code-standards.md` reconciles `scripts/run_tests.sh` (core) vs targeted `pytest` (plugins/isolated units).

* **US-2**: As a Hermes daemon (`Ragnar`, `Roshi`, or another profile) running in `/opt/hermes-agent-data` and self-editing configs, scripts, profiles, skills, or plugins, I want SDD rules to be loaded at startup, refreshed by subdirectory hints, and respected before mutating code.
  * **Req 2.1**: `/opt/hermes-agent-data/` contains real `PROJECT_MEMORY.md`, `ARCHITECTURE.md`, and `.agents/rules/01-sdd-workflow.md`..`04-memory-and-reuse.md` (matching every path referenced in `/opt/hermes-agent-data/AGENTS.md`).
  * **Req 2.2**: `/opt/hermes-agent-data/AGENTS.md` contains explicit **Self-Editing SDD Gate** rules: trivial data/memory updates may proceed directly, while non-trivial edits to `scripts/`, `plugins/`, `profiles/*/AGENTS.md`, `config.yaml`, or `/opt/hermes-agent/*` require an SDD `.specs/` record and human approval when altering architecture/contracts.
  * **Req 2.3**: `config.yaml` (and any profile overriding `terminal.cwd: .`) sets `terminal.cwd: /opt/hermes-agent-data` so `SubdirectoryHintTracker` is NOT disabled by `_is_home_like_working_dir()`.

---

## 4. Acceptance Criteria & Invariants (Given / When / Then)

* **Scenario 1 — Startup Context in `/opt/hermes-agent`**:
  * **Given**: Any agent opens `/opt/hermes-agent` (`cwd=/opt/hermes-agent`).
  * **When**: `build_context_files_prompt` (or Codex/OpenCode/AGY) loads root `AGENTS.md`.
  * **Then**: Both the NCL SDD header and the full Nous contributor rules are present, and every referenced file (`PROJECT_MEMORY.md`, `ARCHITECTURE.md`, `.agents/rules/01..04`, `.atl/skill-registry.md`) exists on disk.

* **Scenario 2 — Startup Context & Self-Edit Hints in `/opt/hermes-agent-data`**:
  * **Given**: `hermes-agent.service` boots with `HOME=/opt/hermes-agent-data/home` and `terminal.cwd: /opt/hermes-agent-data`.
  * **When**: `SubdirectoryHintTracker` initializes and the agent accesses `/opt/hermes-agent-data/plugins/typesafe-skill-router/__init__.py` or `/opt/hermes-agent-data/skills/...`.
  * **Then**: `_home_is_working_dir` is `False`, and `SubdirectoryHintTracker` injects that subdirectory's `AGENTS.md` on first visit; every file referenced in `/opt/hermes-agent-data/AGENTS.md` exists on disk.

* **Scenario 3 — Zero Unintended Prompt-Cache Breakage**:
  * **Given**: Active Hermes sessions after applying the new `AGENTS.md` / `terminal.cwd`.
  * **When**: Turns execute normally without changing directories.
  * **Then**: Static `AGENTS.md` remains deterministic in the `context` tier and preserves KV-cache stability across turns.

---

## 5. Security, VPS & Operational Considerations
* Preserve `hermes:hermes` ownership on all files in `/opt/hermes-agent` and `/opt/hermes-agent-data`.
* Zero secrets in any `AGENTS.md`, `ARCHITECTURE.md`, `PROJECT_MEMORY.md`, or `.specs/` file.
* Gateway restart required **only** if `config.yaml` (`terminal.cwd`) is modified and needs live reload (requires explicit user confirmation before restarting `hermes-agent.service` / `hermes-agent-roshi.service`).

---

## 6. Applicable Project Skills
- [ ] `/opt/hermes-agent/.skills/hermes-agent/SKILL.md`
- [ ] `/opt/hermes-agent/.skills/codebase-inspection/SKILL.md`
- [ ] `/opt/hermes-agent/.skills/code-review-and-quality/SKILL.md`
- [ ] `/opt/hermes-agent/.skills/python-testing-patterns/SKILL.md`
