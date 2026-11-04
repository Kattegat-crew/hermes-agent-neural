# Feature Specification: WhatsApp Multi-Bubble Coalescing, Typing-Presence Extension & Multimodal Busy Redirect/Steer

* **Status**: Approved
* **Author**: Argon / Senior Architect
* **Target Module**: `scripts/whatsapp-bridge/`, `plugins/platforms/whatsapp/`, `gateway/`, `/opt/hermes-agent-data/`
* **Created**: 2026-11-03
* **Updated**: 2026-11-03

---

## 1. Problem Statement & Motivation
* **What is the problem?**
  1. **Multi-Bubble & Multimodal Fragmentation on WhatsApp**: Users naturally send thoughts across 2–6 consecutive bubbles or send text in one bubble followed by an attachment (`.docx`, `.pdf`, image, voice note) in the next. Currently:
     - `BasePlatformAdapter._TEXT_BATCH_DEFAULT_DELAY_S` (`gateway/platforms/base.py:2526`) is `0.3s` (capped at `2.0s`), while `WhatsAppAdapter._poll_messages` (`plugins/platforms/whatsapp/adapter.py:943`) polls every `1.0s`. Any inter-bubble pause >1s flushes prematurely.
     - Non-text events (`PHOTO`, `DOCUMENT`, `VOICE`, `AUDIO`, `VIDEO`) bypass `_enqueue_text_event` (`plugins/platforms/whatsapp/adapter.py:932-935`) and call `handle_message(event)` immediately, splitting text and attachments into separate turns.
     - `scripts/whatsapp-bridge/bridge.js` does not subscribe to or track inbound `presence.update` (`composing` / `recording`), so the adapter cannot extend the batch window while the user is actively typing or recording audio.
  2. **Mid-Turn Fragmentation (`steer` vs `redirect` & Multimodal Gap)**:
     - When a turn is already in flight and `busy_input_mode: steer` is active (as in `roshi`), `_resolve_busy_steer_or_redirect` (`gateway/run_busy.py:606-635`) only calls `running_agent.steer(...)` and never `running_agent.redirect(...)`. If the model is still in its initial API call (no tools run yet, or a toolless turn), `steer()` cannot inject into the in-flight request; the model finishes answering bubble #1 alone and runs bubble #2 as a separate follow-up turn.
     - Furthermore, `_prepare_busy_steer_text` (`gateway/run_busy.py:427-440`) and `_resolve_busy_steer_or_redirect` (`603-623`) only accept plain text or STT voice notes; any image, document, or video attachment sent mid-turn degrades to `queue` mode (a separate turn) instead of being folded into the active turn via `redirect` or `steer`.
  3. **Shared-Bot Profile Route Resolution for `roshi` (`gateway/run.py:4525-4537`)**:
     - `default` gateway owns the shared WhatsApp bridge (`:3000`) and routes `chucho-wa-*` (`153580212334603@lid` / `573334011599`) to `profile: roshi`. Because `roshi` has `gateway.standalone: true` for its dedicated Discord/Telegram service (`hermes-agent-roshi.service`), `_multiplex_profile_homes` excludes `roshi`, causing `_profile_name_for_source` to reject the explicit WhatsApp route (`ProfileRouteRejected`).
* **Why solve it now?** Eliminates premature, fragmented responses when users send multi-bubble thoughts or text + file bursts on WhatsApp, while preserving 100% of provider KV-cache prefixes and avoiding extra LLM classifier calls.

---

## 2. Goals & Non-Goals
### Goals
- [ ] Track inbound user typing/recording presence (`composing` / `recording`) with a bounded TTL (`12s`) in `bridge.js` and expose it via `GET /presence`.
- [ ] Coalesce N consecutive bubbles (text + media/documents/voice) per session key in `_enqueue_text_event`, with profile-scoped configurable base quiet window (`3.0s` for `roshi`), presence-aware extension while the user is `composing`/`recording`, and a strict hard cap (`10.0s` from batch start) so stuck presence indicators never hang a turn.
- [ ] Upgrade `busy_input_mode: steer` in `gateway/run_busy.py` (and `gateway/run_inbound.py`) to:
  1. Enrich non-voice attachments (documents, images, audio/video files) into context notes in `_prepare_busy_steer_text` so multimodal follow-ups can be redirected or steered in-flight.
  2. Automatically attempt `_redirect_active_turn` first when the agent is in an active model API request (`_model_request_active` set and not `_executing_tools`), and gracefully fall back to `steer()` when tools are executing.
- [ ] Allow explicit `profile_routes` on a shared primary transport (like WhatsApp on `default`) to route turns to a valid existing profile directory (`profile_exists(matched.profile)`) even when that profile opts its own dedicated adapters into `gateway.standalone: true`.
- [ ] Enable and scope the new batching parameters on `roshi` first (`platforms.whatsapp.extra.profile_batch_overrides.roshi` and `roshi/config.yaml`) so it can be validated on Roshi before rolling out fleet-wide.

### Non-Goals (Out of Scope)
- Adding an extra LLM classifier call mid-turn that pauses tool execution or mutates the system prompt / KV-cache prefix.
- Modifying WhatsApp session credentials (`/opt/hermes-agent-data/whatsapp/session/`).

---

## 3. User Stories & Functional Requirements
* **US-1 (Pre-Turn Multi-Bubble & Multimodal Coalescing with Presence Extension)**: As a WhatsApp user messaging Roshi across 2–6 consecutive bubbles or attaching a file in a second bubble, I want the gateway to wait until I finish my burst (including while I am actively typing or recording) and merge all bubbles and attachments into a single turn.
  * **Requirement 1.1**: `bridge.js` must listen to `presence.update`, cache `composing`/`recording` states per chat/sender JID with a `12s` TTL, clear the state upon receiving a message from that chat, best-effort subscribe to presence (`sock.presenceSubscribe(chatId)`), and expose `GET /presence?chatId=<id>`.
  * **Requirement 1.2**: `BasePlatformAdapter._enqueue_text_event` must safely merge N consecutive events (text, images, documents, audio, video, voice), preserving `media_text_inlined` index alignment and keeping `MessageType.VOICE` priority over `DOCUMENT` so mixed voice+document batches transcribe voice via STT and attach document notes.
  * **Requirement 1.3**: `BasePlatformAdapter._flush_text_batch` must support profile-scoped `text_batch_delay_seconds` (up to `10.0s`), `text_batch_presence_extend_seconds`, and `text_batch_hard_cap_seconds` (up to `30.0s`), extending the wait in bounded increments when `_is_sender_composing(event)` is `True` up to `first_ts + hard_cap_seconds`.
* **US-2 (Mid-Turn Multimodal Auto-Redirect & Steer)**: As a WhatsApp user sending additional bubbles or attachments after the turn has already started, I want the agent to absorb them seamlessly into the current turn without emitting duplicate/premature answers or breaking prompt caching.
  * **Requirement 2.1**: `_prepare_busy_steer_text` must enrich non-voice media (documents, images, audio/video files) into context notes (and register native image paths when vision is native) so media-bearing follow-ups are eligible for `redirect` and `steer`.
  * **Requirement 2.2**: When `effective_mode == "steer"` and the agent is in an active model API call (not executing tools), `_resolve_busy_steer_or_redirect` must attempt `_redirect_active_turn` first (cancelling only the in-flight model call and restarting with the merged context), and fall back to `steer()` when tools are executing.
* **US-3 (Shared-Bridge WhatsApp Routing to Standalone Profile `roshi`)**: As the operator messaging Roshi on WhatsApp (`chucho-wa-*`), I want the shared WhatsApp bridge on `default` to route my messages to `profile: roshi` even while `roshi` runs its own standalone Discord/Telegram gateway.
  * **Requirement 3.1**: `_profile_name_for_source` in `gateway/run.py` must allow an explicit `profile_routes` match on the primary transport (`adapter_profile is None`) when `profile_exists(matched.profile)` is `True`.

---

## 4. Acceptance Criteria & Invariants
* **Scenario 1: 5–6 Consecutive Text + Attachment Bubbles on WhatsApp**
  * **Given**: `roshi` has `text_batch_delay_seconds: 3.0`, `text_batch_presence_extend_seconds: 2.5`, `text_batch_hard_cap_seconds: 10.0`, and `multimodal_batching: true`.
  * **When**: The user sends 5 text bubbles and 1 `.docx` document separated by 1.5–4.0s (with active `composing` presence between bubbles).
  * **Then**: All 6 bubbles coalesce into a single `MessageEvent` with combined `text`, aligned `media_urls`/`media_types`/`media_text_inlined`, and anchor on the 6th bubble's `message_id`, triggering exactly 1 agent turn.
* **Scenario 2: Stuck `composing` Presence Hard Cap**
  * **Given**: The user sends 1 bubble, starts typing a second bubble (`composing`), and stops without sending.
  * **When**: `text_batch_hard_cap_seconds` (`10.0s`) elapses from the first bubble.
  * **Then**: `_flush_text_batch` stops extending and dispatches the turn immediately at the hard cap.
* **Scenario 3: Mid-Turn Follow-Up Bubble / Attachment**
  * **Given**: A turn for `roshi` is already running (`busy_input_mode: steer`).
  * **When**: A new bubble or document arrives while `_model_request_active` is set (before tool execution), OR while `_executing_tools` is `True`.
  * **Then**: If `_model_request_active` is set, `_redirect_active_turn` aborts the in-flight LLM call and retries with the merged text/attachment in the same turn; if `_executing_tools` is `True`, `steer()` appends the enriched text/attachment to `_pending_steer` and injects it right after the current tool batch finishes.

---

## 5. Security, VPS & Operational Considerations
* Preserves 100% of provider KV-cache prefixes (`AGENTS.md` core invariant).
* No new environment variables required; configured in `/opt/hermes-agent-data/config.yaml` and `/opt/hermes-agent-data/profiles/roshi/config.yaml` with `hermes:hermes` ownership preserved.

---

## 6. Applicable Project Skills
- [x] `.skills/codebase-inspection/SKILL.md` — Subsystem exploration and dependency tracing
- [x] `.skills/api-and-interface-design/SKILL.md` — Tool schemas, gateway contracts, and plugin interfaces
- [x] `.skills/systematic-debugging/SKILL.md` — Root-cause analysis and edge-case verification
- [x] `.skills/code-review-and-quality/SKILL.md` — Clean architecture, prompt-cache preservation, and test coverage
