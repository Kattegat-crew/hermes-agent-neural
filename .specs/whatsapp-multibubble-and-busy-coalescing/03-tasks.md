# Implementation Tasks: WhatsApp Multi-Bubble Coalescing, Typing-Presence Extension & Multimodal Busy Redirect/Steer

* **Associated Spec**: [01-spec.md](./01-spec.md)
* **Associated Design**: [02-design.md](./02-design.md)
* **Status**: Completed

---

## Execution Guidelines
1. **TDD First**: Write unit tests covering multi-bubble coalescing, presence extension + hard cap, multimodal busy redirect/steer, and standalone profile routing on shared adapters.
2. **Atomic Verification**: Run `scripts/run_tests.sh` after each phase.
3. **Zero Regression**: Preserve default batching cadence (`0.3s`) for profiles without overrides while activating the enhanced behavior for `roshi`.

---

## Task Checklist

### Phase 1: Baileys Bridge Typing/Recording Presence (`bridge.js`)
- [x] **Task 1.1**: Add `presence.update` listener, `chatPresence` TTL map (`12s`), clear-on-upsert, best-effort `sock.presenceSubscribe(chatId)`, and `GET /presence` endpoint to `scripts/whatsapp-bridge/bridge.js` and sync to `/opt/hermes-agent-data/scripts/whatsapp-bridge/bridge.js`.
  - *Target Files*: `scripts/whatsapp-bridge/bridge.js`, `/opt/hermes-agent-data/scripts/whatsapp-bridge/bridge.js`
  - *Skill*: `.skills/api-and-interface-design/SKILL.md`
  - *Verification*: `node --check /opt/hermes-agent/scripts/whatsapp-bridge/bridge.js && diff -q /opt/hermes-agent/scripts/whatsapp-bridge/bridge.js /opt/hermes-agent-data/scripts/whatsapp-bridge/bridge.js`

### Phase 2: Pre-Turn Multimodal Batching + Presence Extension with Hard Cap (`base.py` & `whatsapp/adapter.py`)
- [x] **Task 2.1**: Upgrade `BasePlatformAdapter` (`gateway/platforms/base.py`) to support profile-scoped batch overrides (`profile_batch_overrides`), safe multimodal merging in `_enqueue_text_event` (`media_text_inlined` alignment, `VOICE` priority over `DOCUMENT`, latest `message_id` anchor, `_batch_first_ts` tracking), and presence-extended `_flush_text_batch` bounded by `text_batch_hard_cap_seconds`.
  - *Target Files*: `gateway/platforms/base.py`, `plugins/platforms/whatsapp/adapter.py`
  - *Skill*: `.skills/code-review-and-quality/SKILL.md`
  - *Verification*: `sudo -u hermes scripts/run_tests.sh tests/gateway/test_whatsapp_multibubble_coalescing.py -v`

### Phase 3: Mid-Turn Multimodal Auto-Redirect & Steer + Shared-Bot Route Resolution (`run_busy.py`, `run_inbound.py`, `run.py`)
- [x] **Task 3.1**: Upgrade `_prepare_busy_steer_text` and `_resolve_busy_steer_or_redirect` in `gateway/run_busy.py` (and `gateway/run_inbound.py`) to enrich multimodal attachments (documents, images, audio/video files, voice) and attempt `_redirect_active_turn` first when the agent is in an in-flight model call, falling back to `steer()` during tool execution.
  - *Target Files*: `gateway/run_busy.py`, `gateway/run_inbound.py`
  - *Skill*: `.skills/code-review-and-quality/SKILL.md`
  - *Verification*: `sudo -u hermes scripts/run_tests.sh tests/gateway/test_whatsapp_multibubble_coalescing.py -v`
- [x] **Task 3.2**: Update `_profile_name_for_source` in `gateway/run.py` so explicit `profile_routes` on a shared primary adapter (`whatsapp`) resolve to a valid profile (`roshi`) even when that profile runs its own standalone gateway for other platforms.
  - *Target Files*: `gateway/run.py`
  - *Verification*: `sudo -u hermes scripts/run_tests.sh tests/gateway/test_whatsapp_multibubble_coalescing.py -v`

### Phase 4: Roshi Configuration, Service Reload & End-to-End Verification
- [x] **Task 4.1**: Configure `profile_batch_overrides.roshi` on `/opt/hermes-agent-data/config.yaml` (`platforms.whatsapp.extra`) and `/opt/hermes-agent-data/profiles/roshi/config.yaml`, restart the gateway/bridge, and verify live `/health` and `/presence` endpoints plus full test suite.
  - *Target Files*: `/opt/hermes-agent-data/config.yaml`, `/opt/hermes-agent-data/profiles/roshi/config.yaml`, `.specs/README.md`
  - *Verification*: `sudo -u hermes scripts/run_tests.sh tests/gateway/test_whatsapp_multibubble_coalescing.py -v && curl -s http://127.0.0.1:3000/health`
