# Memory Continuity & Code Reuse Protocol

## Core Mandate
**Never operate blind. Never reinvent existing code.**
Every agent (`agy`, `codex`, `opencode2`, `hermes`) operating in this repository must maintain continuous context and prioritize code reuse over new scaffolding.

---

## 1. Session Start Protocol (MANDATORY)

Before proposing any code modification or running mutating commands, execute these reads:
1. **Read [`PROJECT_MEMORY.md`](file:///opt/hermes-agent/PROJECT_MEMORY.md)**:
   - Identify the active focus, last session handover, and immediate next actions.
   - Do not ask the user for context already documented in this ledger.
2. **Read [`ARCHITECTURE.md`](file:///opt/hermes-agent/ARCHITECTURE.md)**:
   - Identify active services, daemons, and operational invariants (e.g., WhatsApp sessions, Roshi supervisor).
   - Locate the relevant reusable modules before planning implementation.

---
3. **Scan & Consume Project Skills (`.skills/` / `.agents/skills/`)**:
   - Inspect installed skills to load conventions, patterns, and testing standards before touching code.
   - For fleet or system operations, invoke `skill_route` on Hermes or consult `/opt/hermes-agent/skills/`.

---

## 2. Code Reuse & Anti-Duplication Rule

1. **Check Before You Code**:
   - Inspect [`ARCHITECTURE.md`](file:///opt/hermes-agent/ARCHITECTURE.md) Section 3 (*Reusable Code Catalog*).
   - If a utility, logger, time parser, state manager, or tool schema helper already exists, you MUST import and reuse it.
2. **Prohibited Patterns**:
   - ❌ Creating duplicate helper functions (e.g., custom logging wrappers, redundant datetime formatters, ad-hoc file readers).
   - ❌ Reinventing state persistence when `hermes_state.py` or `hermes_state_search.py` is available.
   - ❌ Hardcoding system paths instead of using standard constants.

---

## 3. Session Close Protocol (MANDATORY)

Before declaring a session or task complete:
1. **Update [`PROJECT_MEMORY.md`](file:///opt/hermes-agent/PROJECT_MEMORY.md)**:
   - **Handover**: Summarize completed work and test verification results.
   - **Decisions & Gotchas**: Document any non-obvious discoveries, API constraints, or architectural edge cases.
   - **Next Actions**: Update the atomic checklist for the next incoming agent or session.
2. **Preserve Architectural Purity**:
   - Never write transient session notes into `ARCHITECTURE.md` or `AGENTS.md`. `ARCHITECTURE.md` only changes when system architecture or the reusable catalog evolves.
