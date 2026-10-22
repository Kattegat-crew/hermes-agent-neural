# Implementation Tasks: Ephemeral Contextual Progress & Multi-Channel Cleanup

* **Associated Spec**: [01-spec.md](./01-spec.md)
* **Associated Design**: [02-design.md](./02-design.md)
* **Status**: Corrective implementation activated on local DEV gateways; shared WhatsApp routing verified; delivery closure pending

## Authorized Delivery Closure (2026-10-22)

- [x] **Task 9.1**: Correct the documentation to describe the existing shared WhatsApp transport and per-contact routing (Jesús/Chucho -> Roshi; Jonathan -> default/Ragnar), without enabling a separate Roshi adapter or changing runtime configuration. Reconcile current status, obsolete standalone claims, profile configuration inheritance claims, and the now-unnecessary additional QR task.
  - *Route*: delegated direct; multi-file documentation correction after verified routing evidence.
  - *Skill*: `.skills/hermes-agent/SKILL.md`; `/root/.agents/skills/cognitive-doc-design/SKILL.md`.
  - *Target Files*: `ARCHITECTURE.md`, `PROJECT_MEMORY.md`, and this feature's `01-spec.md`, `02-design.md`, `03-tasks.md`.
  - *Verification*: scoped `git diff --check` passed; structural readback matches six enabled routes and shared receiving-adapter delivery. The current docs now distinguish hosted Roshi routing from its intentionally disabled direct adapter, and profile config replication from automatic inheritance.
- [x] **Task 9.2**: Derive a coherent commit/review/publication boundary that excludes unrelated bundled-skill changes, then complete only the delivery steps whose target and authority are established.
  - *Route*: bounded read-only delivery explorer, then parent-owned Git operations after resolving mandatory choices.
  - *Skill*: `/root/.agents/skills/work-unit-commits/SKILL.md`, `/root/.agents/skills/chained-pr/SKILL.md`, `/root/.agents/skills/branch-pr/SKILL.md`.
  - *Verification*: Authorized atomic feature commit executed on `feat/ephemeral-progress-heartbeat-cleanup`, excluding unrelated skill edits; pushed to local origin and GitHub `git@github.com:Kattegat-crew/hermes-agent.git`.

---

## Task Checklist

### Phase 1: Test Scaffolding & TDD Unit Tests
- [x] **Task 1.1**: Create unit tests for `_progress_absorb` in `replace` mode, contextual formatting (no raw code blocks, human-friendly Spanish with target resources), and thread-safe Discord message deletion.
  - *Target Files*: `tests/gateway/test_ephemeral_progress.py`
  - *Verification*: `pytest tests/gateway/test_ephemeral_progress.py -v` (Passed 7/7).

### Phase 2: In-Place Replacement & Contextual Label Implementation
- [x] **Task 2.1**: Update `_progress_absorb` in `gateway/run_turn_runner.py` to support `tool_progress_grouping: replace` (single active line buffer).
  - *Target Files*: `gateway/run_turn_runner.py`
  - *Verification*: `pytest tests/gateway/test_ephemeral_progress.py -k "test_progress_absorb_replace" -v`
- [x] **Task 2.2**: Enhance contextual action formatting in `agent/display.py`, `gateway/run_turn_runner.py`, and restore `locales/*.yaml` keys for Spanish actions.
  - *Target Files*: `locales/en.yaml`, `locales/es.yaml`, `gateway/run_turn_runner.py`
  - *Verification*: `pytest tests/gateway/test_activity_labels.py -v` (Passed 11/11).

### Phase 3: WhatsApp & Discord Ephemeral Lifecycle
- [x] **Task 3.1**: Update Discord adapter `delete_message` to resolve thread channels when given either thread_id or parent channel with thread metadata.
  - *Target Files*: `plugins/platforms/discord/adapter.py`
  - *Verification*: `pytest tests/gateway/test_ephemeral_progress.py -k "test_discord_delete_thread" -v`
- [x] **Task 3.2**: Add `POST /delete` to WhatsApp Baileys bridge and implement `delete_message` in `WhatsAppAdapter`.
  - *Target Files*: `scripts/whatsapp-bridge/bridge.js`, `plugins/platforms/whatsapp/adapter.py`
  - *Verification*: `pytest tests/gateway/test_ephemeral_progress.py -k "test_whatsapp_delete_message" -v`

### Phase 4: Multi-Agent Safeguard & Standard Fleet Configuration
- [x] **Task 4.1**: Implement `is_multi_agent_chat` in `gateway/display_config.py` and enforce suppression of progress & heartbeats in `gateway/run_turn.py`.
  - *Target Files*: `gateway/display_config.py`, `gateway/run_turn.py`
  - *Verification*: `pytest tests/gateway/test_ephemeral_progress.py -k "test_multi_agent_chat_suppression" -v`
- [x] **Task 4.2**: Configure standardized channel defaults in `/opt/hermes-agent-data/config.yaml` (`telegram`, `discord`, `whatsapp`) and clean stale per-profile overrides in `roshi/config.yaml`.
  - *Target Files*: `/opt/hermes-agent-data/config.yaml`, `/opt/hermes-agent-data/profiles/roshi/config.yaml`
  - *Verification*: `pytest tests/gateway/test_display_config.py -v` (Passed 26/26).

### Phase 5: Safe Restart & Memory Update
- [x] **Task 5.1**: Restart service cleanly via `/usr/local/bin/hermes-safe-restart` and verify systemd status.
  - *Verification*: `systemctl is-active hermes-agent` -> active.
- [x] **Task 5.2**: Update `PROJECT_MEMORY.md` with final architecture.
- [ ] **Task 5.3 (Pending Audit)**: Standalone audit for unused/dead code and documentation cleanup across `/opt/hermes-agent`.

### Phase 6: Authorized Audit Corrections (2026-10-22)

Scope: the user's instruction to fix the two remaining audited failures. Reuse the approved single-bubble and multi-agent suppression requirements; do not change dependencies, profile configuration, adapters, services, or WhatsApp sessions. Preserve all pre-existing worktree changes.

- [x] **Task 6.1**: Route heartbeat updates through the turn-local progress queue and its existing serialized message writer. Cover tool-first, heartbeat-first, heartbeat-only, concurrent publication, failed edits, interruption/generation ownership, thread metadata, and one-ID cleanup. Do not create a second heartbeat bubble.
  - *Route*: delegated direct; multiple non-trivial files and preparation-for-write trigger.
  - *Skill*: `.skills/python-patterns/SKILL.md`, `.skills/python-testing-patterns/SKILL.md`, `.skills/codebase-design/SKILL.md`.
  - *Target Files*: `gateway/run_turn.py`, `gateway/run_turn_runner.py`, `tests/gateway/test_ephemeral_progress.py`.
  - *Verification*: RED observed before implementation (2 behavioral assertions failed as expected); focused `-k 'heartbeat or shared_status or multi_agent' -v` passed 11/11 after implementation. Exact 8-file regression command passed 133/133, exit 0 (2026-10-22). Heartbeat stale-generation/cancel ownership is guarded by the existing run-current predicate; sender cancellation drain and generation-invalidation regressions are covered in `test_run_progress_topics.py`; cleanup ID tracking and post-delivery deletion are covered in `test_ephemeral_progress.py` and `test_run_cleanup_progress.py`.
- [x] **Task 6.2**: Match configured multi-agent container IDs against `parent_chat_id` as well as chat/thread IDs. Preserve unrelated-chat behavior and the existing mention-policy fallback.
  - *Route*: delegated direct with Task 6.1; one writer preserves the shared dirty baseline.
  - *Skill*: `.skills/python-patterns/SKILL.md`, `.skills/python-testing-patterns/SKILL.md`.
  - *Target Files*: `gateway/display_config.py`, `tests/gateway/test_ephemeral_progress.py`.
  - *Verification*: RED observed before implementation (parent-only channel assertion failed as expected); focused `-k 'heartbeat or shared_status or multi_agent' -v` passed 11/11 after implementation. Exact 8-file regression command passed 133/133, exit 0 (2026-10-22), including parent-only match, alias, and unrelated-parent negative coverage.

Execution notes: forecast 250–350 authored changed lines for these corrections, excluding the pre-existing agy baseline; delivery strategy `ask-on-risk`. Keep one coherent correction unit. The existing feature branch is `feat/ephemeral-progress-heartbeat-cleanup`; commit scope must not absorb unrelated or incomplete pre-existing changes. Record any unachievable commit boundary explicitly rather than staging broadly. Native review-mode lookup currently refuses the Git authority ownership (UID mismatch); mode is unknown and verification must use the high/unassessable independent-check path. Do not change ownership or the review switch to bypass the refusal.

### Phase 6 Follow-up: Independent Method-Path Corrections

- Independent verification reproduced three concrete failures after the initial 133-test pass: replace-mode tool events could send a second bubble after permanent heartbeat edit failure; Telegram's real `flood_control:20` `SendResult` could fall through to a replacement send; Slack native task-card state discarded typed heartbeat updates.
- Added regression coverage first and observed RED (5 selected cases failed); after fixes, all 5 new cases passed, and the broader focused heartbeat/shared-status/multi-agent/failure/flood/native-card selection passed 16/16.
- Follow-up implementation keeps all replace-mode status updates suppressed after a permanent edit failure while the original may remain; preserves message identity and defers retry using the bounded adapter `retry_after` on flood caps; and renders heartbeat text as a stable in-progress row in the existing Slack card and its text fallback. Non-replace modes retain their prior behavior.
- **Latest exact 8-file canonical regression**: writer verification 138 passed, 0 failed, exit 0; independent verifier repeated 138 passed, 0 failed, exit 0 in 106.4s (2026-10-22 15:23 UTC). Actual-method replays confirmed permanent-failure suppression across mixed events, Telegram flood backoff with same-ID recovery, and Slack native/fallback status delivery. Parent repeated the multi-agent selection: 2 passed, 0 failed, exit 0.

Functional closure: focused follow-up and original selected tests passed 16/16; the exact named 8-file regression suite passed 138/138 (exit 0) with the fail-closed canonical runner, independently repeated against unchanged source/test hashes. Scoped whitespace validation passed. No staging or commit was performed: the correction depends on pre-existing, uncommitted agy feature changes across additional files, and an independently runnable commit boundary cannot be formed without absorbing that baseline. Preserve the index and request a separately authorized integration/commit boundary rather than committing incomplete or unrelated work. Native review remains unavailable/unassessable; no receipt or approval is claimed. No dependencies were installed. At Phase 6 closure, runtime activation and a live canary remained pending separate authorization; the later authorized activation is recorded in Phase 7. Phase 6 itself changed no services or WhatsApp session state.

### Phase 7: Final Verification and Operational Activation Gate (2026-10-22)

- [x] **Task 7.1**: Repeat final functional verification and inspect local activation readiness without disrupting WhatsApp.
  - *Route*: delegated direct; independent verifier and read-only operational explorer.
  - *Skill*: `.skills/python-testing-patterns/SKILL.md`, `.skills/code-review-and-quality/SKILL.md`, `.skills/hermes-s6-container-supervision/SKILL.md`.
  - *Verification*: exact guarded canonical eight-file runner: 138 passed, 0 failed, exit 0 in 129.4s. Bridge syntax, EN/ES/FR/DE YAML/template checks, and scoped whitespace checks passed. Twelve audited code/test/locale hashes were unchanged (2026-10-22 15:59 UTC).
  - *Observed runtime*: main gateway and Vigia services are active, but both process start times predate the corrected source. Both report `CanReload=no`; no supported source hot-reload was found. Active services are not evidence of new-code activation.
- [x] **Task 7.2**: Activate corrected source after resolving the WhatsApp continuity constraint and verify restarted processes; live contact/message canaries remain separate evidence.
  - *Route*: delegated direct; the user explicitly authorized controlled gateway restarts and WhatsApp reconnection on 2026-10-22. Restart only the existing local DEV main and Vigia gateway services; do not change deployment topology or delete pairing credentials.
  - *Skill*: `.skills/hermes-s6-container-supervision/SKILL.md`, `.skills/hermes-agent/SKILL.md`.
  - *Resolved decision*: the user accepted restarting the gateways and reconnecting WhatsApp. The managed bridge will reconnect as part of the main gateway restart. Use the canonical safe-restart procedure, including its existing active-turn recovery mechanism when needed; no ad-hoc session/routing edits, credential removal, forced logout, ownership changes, or bridge redesign are authorized.
  - *Verification*: authorized main and Vigia restarts exited 0 and the new processes remained active/running with automatic restart count 0. The root bridge health check returned HTTP 200 and connected using the existing pairing. Source hashes were unchanged; no pairing files, profile configuration, code, or deployment topology were altered. This verifies process activation and bridge health, not a new inbound contact or live progress-message canary.

### Phase 8: Authorized WhatsApp Reconnection Assistance

- [x] **Task 8.1**: Inspect WhatsApp readiness after restart and preserve the existing paired number/bridge. The verified shared root route already serves Roshi and default/Ragnar; no additional adapter, pairing, QR, or Discord delivery is needed.
  - *Route*: delegated local readiness inspection and route-configuration validation; no external write was needed.
  - *Verification*: the root bridge reconnected using its existing pairing. Current configuration and matcher validate all six enabled per-contact rules: Jesús/Chucho -> Roshi and Jonathan -> default/Ragnar, with LID/JID/number forms. Roshi is served as a logical profile by the root gateway; its own WhatsApp adapter is intentionally disabled while outbound delivery uses the receiving adapter. No QR was generated or sent, and no Discord message was sent. No fresh end-to-end inbound contact canary was performed; Vigia's separate WhatsApp readiness remains unverified, and no fleet-wide connectivity is asserted.
