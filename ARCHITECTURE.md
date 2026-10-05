# Hermes Agent Architecture & Systems Map

> **Operational Source of Truth**: This document maps active daemons, network services, system invariants, and the reusable code catalog for [`/opt/hermes-agent`](file:///opt/hermes-agent). Every agent (`agy`, `codex`, `opencode2`, `hermes`) must consult this before modifying code.

---

## 1. System Topology & Active Services

Hermes operates as a multi-profile, distributed agent runtime on Ubuntu 24.04 (DEV Host: `147.93.3.250`).

### Active Daemons & Ports
| Service / Process | Command / Entrypoint | Port / Socket | Responsibility |
|---|---|---|---|
| **Main Gateway (Ragnar)** | `hermes gateway run --replace` | Internal bus | Default profile orchestrator, multi-channel gateway (Telegram, Discord, Slack) |
| **Roshi Gateway** | `hermes -p roshi gateway run --replace` | Internal bus | Specialist finance and administrative bot |
| **Vigia Gateway** | `hermes -p vigia gateway run --replace` | Internal bus | Monitoring, alerting, and system vigilance |
| **Hermes Dashboard** | `hermes dashboard --host 0.0.0.0 --port 9112` | `9112` | Web administration UI and session visualization |
| **WhatsApp Bridge** | `bridge.js --port 3000 --mode bot` | `3000` | Baileys-based WhatsApp connection daemon |
| **IMAP Daemon** | `davibank_imap_daemon.py` | Background | Bank statement and transaction intake listener |
| **Browser Harness** | `python -m browser_harness.daemon` | Background | Headless Playwright / Chrome execution runner |
| **PROD DB Tunnel** | `ssh -L 127.0.0.1:15433:10.0.2.3:5432 prod` | `15433` | Secure forwarder to Production PostgreSQL |

---

## 2. Inviolable Operational Invariants (Blindaje)

1. **WhatsApp Session Persistence**:
   - Directory: `/opt/hermes-agent-data/whatsapp/session/` (symlink `/opt/data/whatsapp/session/`).
   - `creds.json` and session keys MUST NEVER be deleted, recreated, or cleaned up. Backup exists at `creds.json.bak`.
2. **Roshi Standalone State**:
   - Profile state file `/opt/hermes-agent-data/profiles/roshi/gateway_state.json` must preserve `"desired_state": "running"`.
   - Never collapse Roshi into the default multiplexer.
3. **Prompt Caching Sanctity**:
   - Never inject dynamic timestamps or mutate system prompt prefixes mid-conversation.
   - Preserves upstream cache hits and eliminates unnecessary token latency.
4. **Narrow Waist Core**:
   - New capabilities belong in plugins (`plugins/`), skills (`skills/`), or tools (`tools/`), NOT inside core conversation loops (`agent/conversation_loop.py`).

---

## 3. Reusable Code Catalog (DO NOT Reinvent the Wheel)

Before writing any new class, helper, or utility, inspect and reuse these battle-tested modules:

### State, Persistence & Sessions
* [`hermes_state.py`](file:///opt/hermes-agent/hermes_state.py): Unified agent state, session management, and persistence layer.
* [`hermes_state_search.py`](file:///opt/hermes-agent/hermes_state_search.py): Vector & keyword indexing over conversation history and sessions.
* [`hermes_state_schema.py`](file:///opt/hermes-agent/hermes_state_schema.py): Pydantic / dataclass schemas for messages, trajectories, and profiles.

### Utilities, Time & Logging
* [`hermes_logging.py`](file:///opt/hermes-agent/hermes_logging.py): Structured JSON and console logging. Use this instead of vanilla `logging` or `print`.
* [`hermes_time.py`](file:///opt/hermes-agent/hermes_time.py): Timezone-aware date parsing and formatting utilities.
* [`utils.py`](file:///opt/hermes-agent/utils.py): Core file helpers, hashing, text formatting, and environment resolution.

### Model Execution & Tools
* [`model_tools.py`](file:///opt/hermes-agent/model_tools.py): Tool schema formatting, payload validation, and provider-agnostic dispatch.
* [`toolsets.py`](file:///opt/hermes-agent/toolsets.py): Dynamic tool grouping and filtering by profile.
* [`tools/clarify_tool.py`](file:///opt/hermes-agent/tools/clarify_tool.py): User interaction & structured confirmation prompts.
* [`agent/tool_guardrails.py`](file:///opt/hermes-agent/agent/tool_guardrails.py): Runtime intent triage and decoupling for zero-cost conversational turns.

### Prompts & Skills
* [`agent/prompt_builder.py`](file:///opt/hermes-agent/agent/prompt_builder.py): Dynamic context assembler (loads `SOUL.md`, `AGENTS.md`, and skills).
* [`agent/skills_registry.py`](file:///opt/hermes-agent/agent/skills_registry.py): On-demand skill lookup and execution.
