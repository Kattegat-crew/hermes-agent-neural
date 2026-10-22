# Hermes Agent Architecture & Systems Map

> **Operational Source of Truth**: This document maps active daemons, network services, system invariants, and the reusable code catalog for [`/opt/hermes-agent`](file:///opt/hermes-agent). Every agent (`agy`, `codex`, `opencode2`, `hermes`) must consult this before modifying code.

---

## 1. System Topology & Active Services

Hermes operates as a multi-profile, distributed agent runtime on Ubuntu 24.04 (DEV Host: `147.93.3.250`).

### Active Daemons & Ports
| Service / Process | Command / Entrypoint | Port / Socket | Responsibility |
|---|---|---|---|
| **Main Gateway (default/Ragnar + hosted profiles)** | `hermes gateway run --replace` | Internal bus | Default profile orchestrator; serves logical profiles such as Roshi through configured profile routes |
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
2. **Roshi Hosted Runtime**:
   - Roshi is served as a logical profile by the main/default gateway through configured profile routes; it is not a separate WhatsApp gateway process.
   - Preserve the shared WhatsApp bridge and the configured per-contact routing. Do not enable a second Roshi WhatsApp adapter or pair another number as part of routine routing.
3. **Prompt Caching Sanctity**:
   - Never inject dynamic timestamps or mutate system prompt prefixes mid-conversation.
   - Preserves upstream cache hits and eliminates unnecessary token latency.
4. **Narrow Waist Core**:
   - New capabilities belong in plugins (`plugins/`), skills (`skills/`), or tools (`tools/`), NOT inside core conversation loops (`agent/conversation_loop.py`).

---

## WhatsApp Shared Transport & Per-Contact Routing

The root/default gateway owns the connected WhatsApp receiving adapter and bridge. Its configured `gateway.profile_routes` select the logical runtime for inbound contacts; outbound delivery continues through the receiving adapter that accepted each message. Roshi and default/Ragnar therefore share the same paired number and bridge without requiring Roshi's own WhatsApp adapter to be enabled.

| Configured route family | Logical runtime | Match variants |
|---|---|---|
| `chucho-wa` | Roshi | LID, JID, and phone-number forms |
| `jonathan-wa` | default/Ragnar | LID, JID, and phone-number forms |

The six enabled rules (three match variants per route family) were validated against the current root configuration and route matcher. This is configuration/matcher evidence, not a fresh end-to-end inbound contact canary. The existing pairing is connected; no separate Roshi adapter, new number, re-pairing, QR, or QR delivery is needed for these routes.

Profile display settings are not inherited automatically from the root config. Effective settings are resolved from the active home file, environment expansion, managed overlay, and normalization; root and profile display blocks are replicated deliberately. Shared channel policy does not imply that every profile's platform adapter is enabled.

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

### Gateway Progress & Heartbeat Status
* `gateway/run_turn.py::_run_agent_notify_long_running` formats periodic status and enqueues typed updates on the existing per-turn progress queue; it is a producer, not an independent adapter writer.
* `gateway/run_turn_runner.py::TurnRunner.send_progress_messages` is the serialized owner of the progress bubble and its message ID, so heartbeat and tool status share one editable message and the existing post-delivery cleanup.
* Heartbeat-enabled turns create this queue even when tool progress is off. In `replace` mode, unsupported or permanently failing edits degrade to one heartbeat send followed by suppression, avoiding one permanent bubble per tick.
* Native Slack task-card turns absorb typed heartbeat updates into the existing card projection (and its existing text fallback), so liveness does not bypass the serialized progress lane. `gateway/display_config.py::is_multi_agent_chat` matches configured IDs against `chat_id`, `thread_id`, and `parent_chat_id`; the parent match is required when a native Discord thread's source channel ID is its child thread.

### Prompts & Skills
* [`agent/prompt_builder.py`](file:///opt/hermes-agent/agent/prompt_builder.py): Dynamic context assembler (loads `SOUL.md`, `AGENTS.md`, and skills).
* [`agent/skills_registry.py`](file:///opt/hermes-agent/agent/skills_registry.py): On-demand skill lookup and execution.
