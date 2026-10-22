# Feature Specification: Ephemeral Progress Heartbeat & Display Cleanup

* **Status**: Approved; implementation and authorized local activation verified; delivery closure pending
* **Author**: Antigravity (Senior Architect)
* **Target Module**: `gateway/`, `plugins/platforms/discord/`, `plugins/platforms/whatsapp/`, `scripts/whatsapp-bridge/`, `hermes-agent-data/`
* **Created**: 2026-10-21
* **Updated**: 2026-10-22

---

## 1. Problem Statement & Motivation
1. In Discord and WhatsApp, Hermes agents (Ragnar, Roshi, Vigía, etc.) output running tool execution progress by appending lines to a growing message (Discord) or posting individual progress messages (WhatsApp) rather than updating in-place.
2. WhatsApp messages accumulated in chat history, bloating SQLite `state.db` and context token limits (requiring expensive compression) because WhatsApp lacked a message deletion endpoint.
3. The temporary progress message was not deleted before delivering the final answer, leaving stale intermediate text cluttering user chats.
4. Intermediate messages displayed unlocalized keys or technical jargon (`iteration X/90`, raw tool commands) instead of clean, contextual Spanish activity descriptions.
5. In multi-agent chats or shared channels where 2 or more bots co-exist (e.g. collaborative threads like `#digital-vikings`), intermediate progress edits and heartbeat messages triggered message-create/message-update events in peer bots, causing infinite response loops.
6. Heartbeat notifications were hardcoded to 180s rather than dynamic 20-25s.

---

## 2. Architectural Decision: Per-Channel Standards (Not Per-Agent)
Rather than configuring heterogeneous behaviors per agent, the system defines **standard platform behaviors per channel**:
* **Telegram**: In-place single-bubble editing (`tool_progress_grouping: replace`) + ephemeral cleanup on delivery (`cleanup_progress: true`).
* **Discord**: Thread-aware in-place editing + ephemeral cleanup (`delete_message` resolving thread channels).
* **WhatsApp**: Baileys bridge in-place editing (`POST /edit` within 15-minute window) + ephemeral cleanup (`POST /delete` revoke) + `cleanup_progress: true`.
* **Hermes Desktop**: Native desktop streaming transcript.
* **Multi-Agent Channels**: Suppress configured intermediate progress and heartbeats in shared channels (`multi_agent_channels`) to mitigate progress-triggered ping-pong; this is not a guarantee against every possible loop class.

Channel behavior is a shared policy, not automatic configuration inheritance. Effective profile settings resolve through the active home file, environment expansion, managed overlay, and normalization; the root and 11 profile display blocks are replicated deliberately. A display setting in one profile does not establish another profile's adapter enablement.

WhatsApp uses the root/default gateway's connected receiving adapter and bridge for both default/Ragnar and the hosted Roshi runtime. Six enabled route rules select the logical runtime by contact: `chucho-wa` routes Jesús/Chucho to Roshi, and `jonathan-wa` routes Jonathan to default/Ragnar; each family accepts LID, JID, and phone-number forms. Delivery uses the receiving adapter. The existing paired number and bridge are shared; no standalone Roshi WhatsApp adapter, new number, re-pairing, QR, or QR delivery is required. Configuration and matcher validation do not substitute for a fresh end-to-end inbound contact canary.

---

## 3. Goals & Acceptance Criteria
- [x] **In-place progress updates**: When `tool_progress_grouping: replace`, `_progress_absorb` maintains a single active line buffer.
- [x] **Ephemeral deletion**: Ephemeral progress bubbles are revoked upon turn completion on Discord, Telegram, and WhatsApp.
- [x] **WhatsApp Deletion Endpoint**: Baileys bridge exposes `POST /delete` with `{ delete: key }`; `WhatsAppAdapter.delete_message` integrated.
- [x] **Discord Thread-Aware Deletion**: `delete_message` in Discord adapter targets thread channels without 404 Unknown Message.
- [x] **Conversational Spanish Activity**: Actions display contextual natural Spanish (e.g. *⏳ Revisando archivos `run_turn.py` (22s)*) with no raw code fences or loop iteration counters.
- [x] **Cadence (20-25s)**: Heartbeat reads `agent.gateway_notify_interval` (configured to 20s in `config.yaml`).
- [x] **Multi-Agent Loop Prevention**: `is_multi_agent_chat` mutes progress and heartbeats in configured multi-agent channels/threads.
- [x] **Shared Channel Policy**: Root and profile `display.platforms` settings are deliberately replicated; profile-specific effective configuration is not inferred from root-file inheritance.

---

## 4. Operational Invariants
* **Safe Restart**: Service recycling must run through `/usr/local/bin/hermes-safe-restart` to preserve active sessions.
* **Clean Code**: Obsolete / dead progress code paths removed to prevent diagnostic confusion.
