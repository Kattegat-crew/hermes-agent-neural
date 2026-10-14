# Hermes Project Memory & Session Continuity

> **Session Lifecycle Contract**:
> - **On Session Start**: Read this file and [`ARCHITECTURE.md`](file:///opt/hermes-agent/ARCHITECTURE.md) to recover active context and understand current flows before taking any action.
> - **On Session Close**: Update this file with what was accomplished, verification results, and immediate next steps.

---

## 1. Active Focus & Current Goal
* **Current Initiative**: Reconcile SDD documentation files in `/opt/hermes-agent` on branch `feat/memoria-dev` to resolve all audit discrepancies identified by Codex.
* **Lead Agent**: Antigravity (`agy`) / Ragnar, with Codex preparing the documentation units.
* **Target Path**: [`/opt/hermes-agent/`](file:///opt/hermes-agent/).
* **Delivery strategy:** feature-branch-chain approved by the user on 2026-10-08 (Aprobado); local slices only.
* **Approval State**: Specification/design approved by the user on 2026-10-08 (Adelante); tasks T01–T10 and phases P1–P9 verified; no PR, push, merge, or unsafe runtime action is authorized.

---

## 2. Handover from Last Session
* **Audit Reconciliation & Completion (2026-10-08)**:
  - **Checklists Reconciled**: All tasks T01–T10 and stable phases P1–P9 are verified with dated observed proof:
    * **T01 / P1**: Bounded inventory of 5 product Git roots and active worktrees captured (`/opt/hermes-agent` feat/memoria-dev, `/opt/golden-game-landing` main + motion-stg-golden-wt, `/opt/paradise-casino/paradise-casino-landing` main + motion-stg-lucky-wt, `/opt/marketing-campaign-generator` main + 3 worktrees, `/opt/ai-platform` main); 6 governance documents per root confirmed.
    * **T02 / P2 / P3**: Entrypoints inspection completed (`AGENTS.md`, `agent/prompt_builder.py`, `agent/system_prompt.py` tracked in git; other entrypoints like `.codex`, `.config/opencode`, `GEMINI.md`, `system.md` uninspected/absent; boundaries preserved).
    * **T03 / P4**: Engram store reconciliation completed. Migrated 58 unique observations from `/opt/hermes-agent-data/home/.engram/engram.db` into canonical `/root/.engram/engram.db`. Updated profile configurations (`config.yaml`, `roshi`, `vigia`) to `/root/.engram`.
    * **T04 / P5**: Graph source contract analyzed. `scripts/brain_graph_update_wrapper.sh` tracked; producer writes `graphify-out/graph.json`, consumer `tools/memory_graph.py` reads `graphify-out-v2/graph.json`. Live compilation verified with `status=process_complete inner_rc=0`.
    * **T05a / T05b / P6**: Offline wrapper unit committed (`e1feeb1d51`); deployed to `/opt/hermes-agent-data/scripts/` (mode 0755, `hermes:hermes`); verified live execution with `inner_rc=0`.
    * **T06 / P6 / P9**: Backup scope mapped. Confirmed `hermes_cli/backup.py` and nightly `vps_master_backup.py` explicitly backup `/root/.engram/engram.db` as `engram.db.bak`.
    * **T07 / P7**: Skills mapped. 59 git skills and 10 runtime profiles in `/opt/hermes-agent-data/profiles/` mapped.
    * **T08**: Surface-scoped units dispatched independently with zero unapproved operations.
    * **T09 / P8**: Acceptance matrix completed for 6 agents across 5 product repos.
    * **T10 / P9**: Durable state reconciled, Engram mirrored (#1757), closure evidence recorded.
  - **Forensic Clarification of Engram Metrics (1,754 vs 1,752)**:
    * Total physical rows in SQLite `observations` table at migration = 1,754.
    * Soft-deleted rows with `deleted_at IS NOT NULL` = 2 (observation ID `242` deleted 2026-08-21 04:02:55 and observation ID `1562` deleted 2026-10-08 04:47:27).
    * Active observations counted by `engram stats` (`WHERE deleted_at IS NULL`) = 1,752 (1,754 - 2 = 1,752).
    * Zero memory loss occurred during migration or unification.
  - **Official Test Runner Executed**:
    * Ran: `HERMES_PYTHON=/usr/bin/python3 ./scripts/run_tests.sh tests/cron/test_brain_graph_wrapper.py tests/cron/test_cron_no_agent.py`
    * Result: 2 test files, 26 passed, 0 failed in 21.6s (17.1s parallel wall time).
  - **Agent × Repository Acceptance Matrix Documented**:
    * Full 6×5 matrix verified across Codex, OpenCode, Gemini, Copilot, Antigravity, Hermes and the 5 product repos (`hermes-agent`, `golden-game-landing`, `paradise-casino`, `marketing-campaign-generator`, `ai-platform`).
    * Confirmed unified Engram MCP / canonical SQLite binding, full SDD compliance, and zero divergence.
  - Feature-branch-chain delivery approved on 2026-10-08 (Aprobado). No PRs, pushes, or merges created.
  - Existing modified TikTok ingestion skill preserved untouched.

* **Prior Handover (historical; file mtime observed 2026-10-03, exact event dates absent from its body)**:
* **Completed (historically recorded; not current verification)**:
  - Established `.agents/rules/` with `01-sdd-workflow.md`, `02-vps-guardrails.md`, and `03-code-standards.md`.
  - Created `.specs/` repository index and base templates (`01-spec.md`, `02-design.md`, `03-tasks.md`).
  - Created [`ARCHITECTURE.md`](file:///opt/hermes-agent/ARCHITECTURE.md) documenting active daemons, WhatsApp persistence invariants, and reusable code catalog.
  - Configured `PROJECT_MEMORY.md` as the official session continuity ledger.
* **Verified by (older handover report; not reverified on 2026-10-08)**:
  - File presence and permissions (`chown -R hermes:hermes`).
  - Process audit confirmed active running daemons (Ragnar, Roshi, Vigia, WhatsApp bridge on `:3000`, Dashboard on `:9112`).
* **Pending / Incomplete (status at that older handover, not current state)**:
  - Establish rule `04-memory-and-reuse.md` in `.agents/rules/`.
  - Update `AGENTS.md` and `SOUL.md` to bind all external CLI agents and internal Hermes fleet profiles to this memory and reuse contract.

---

## 3. Operational Decisions & Gotchas
* **Separation of Concerns**: Kept `ARCHITECTURE.md` (static operational truth and reusable code inventory) decoupled from `PROJECT_MEMORY.md` (ephemeral session state) to protect system maps from accidental agent truncation and prevent prompt cache degradation.
* **WhatsApp Session**: Never touch `/opt/hermes-agent-data/whatsapp/session/` (symlink `/opt/data/whatsapp/session/`).
* **Ownership**: All project files must remain owned by `hermes:hermes`.

---

## 4. Next Immediate Actions
- [x] All 9 phases (P1–P9) and tasks T01–T10 of the Memoria DEV plan completed, audited, and reconciled.
- [x] Engram metric discrepancy forensically explained (1,754 total, 2 soft-deleted, 1,752 active observations).
- [x] Official runner executed with 26 tests passed in 21.6s.
- [x] Agent × Repository Acceptance Matrix documented.
- [ ] Maintain the single Engram database policy at `/root/.engram/engram.db`.
- [ ] Evaluate PR/push of `feat/memoria-dev` upon explicit user review and approval (no automated push allowed).

---

## 5. Scoped Local Scanner Correction and Production Audit (2026-10-14)

- **CURRENT STATUS (2026-10-14 06:07:22 UTC):** The narrow HTML-comment scanner fix is live on production after the corrected controlled retry. Current image ID is `sha256:2b00226cfe6a8dfdb1b9a83e16bff22a114b9769c126ed5849dcc9f96e9c3386`; host/runtime scanner hash is `94b5c121cbe6e8ce0594db3f9aac9e3b84b15efd213bd67f248d0e6460c737bf`. Earlier first-attempt rollback notes below are historical and superseded by the retry; there is no active rollback. Other production audit findings remain a mix of verified, partial, historical, unproven, and open; see [the consolidated audit report](.specs/hermes-html-comment-false-positive/04-audit-report.md). This status does not imply fleet-wide closure.
- **Audit documentation task:** T03 is in progress to consolidate the original operational audit, verify claim status, and list remaining proof/action requirements. No additional production operations are part of T03.
- **Goal:** Correct and preserve the HTML-comment scanner fix for the false positive caused by matching `secret` inside `Secretaría`, while retaining standalone malicious keyword detection; reconcile the original production audit without overclaiming resolution.
- **Approval:** User explicitly authorized “si haz la correccion” on 2026-10-14 for this scoped behavior. A separate explicit user request authorized this narrow production deployment, service interruption, and permanence; it did not authorize unrelated configuration changes or broader remediation.
- **Location:** Isolated local checkout `/root/hermes-agent-worktrees/html-comment-fix`, branch `fix/html-comment-word-boundaries`; original `/opt/hermes-agent` was not edited.
- **Discoveries:** `tools/threat_patterns.py` previously applied substring matching for `ignore|override|system|secret|hidden` within a bounded HTML-comment pattern; context loading rejects files when any finding exists. The existing malicious-comment test is in `tests/tools/test_threat_patterns.py`. CodeGraph init created a local index, but status reported it truncated with unresolved references, so bounded source reads were used after the tool failure.
- **Local implementation:** Added Unicode-aware word boundaries around only the existing HTML-comment keywords. No prompt builder, scanner profile, API, or dependency was changed. Production deployment was completed later under separate explicit authorization; details and limitations are in T02 and the consolidated report.
- **Verification:** Focused runner observed RED (34 passed, 6 expected failures), then GREEN (40 passed, 0 failed). Combined scanner + prompt-builder tests yielded 115 passed and one unrelated failure in `test_agents_md_no_git_root_stays_cwd_only`; independent verification reproduced it on base `prompt_builder.py`, with `/tmp/.git` causing ancestor `AGENTS.md` loading. Independent real-path smoke included benign `Secretaría`, blocked `ignore all rules`, and confirmed the base scanner false positive. `git diff HEAD --check` passed.
- **Known limit:** Python Unicode `\b` treats underscore as a word character; this comment pattern does not treat `ignore_all_rules` as standalone. No general obfuscation-detection guarantee is made.
- **RDD:** Mode is on. Parent's post-commit assessment with `.codegraph` explicitly excluded exited 0: risk `medium`, 6 changed paths / 165 lines, `review_due=false`, reason `under_budget`. No START, consent, receipt, or delivery approval exists; the slice remains pending below budget.
- **Work-unit commit:** `6d54b2c04536f396f27cccd48a0678684d659567` (`fix/security: require standalone html-comment trigger words`), branch `fix/html-comment-word-boundaries`, parent/base `a3358de1258c0886d81428533aad06753fff3efc`.
- **Historical status before T02 deployment (superseded):** Local implementation was committed and focused tests passed; production deployment had not yet occurred at that point. The local review slice remained pending below budget, with no receipt or delivery authority.
- **Historical T02 first deployment attempt and rollback (superseded by corrected retry):** Main Compose effective hash differed because desired-only config included ten Discord/API/group-policy vars and two WhatsApp values differed from live. Parent directed exact-live preservation. A standalone mode-0600 snapshot with only service `hermes` passed exact 78-key environment, command/entrypoint/user/cwd/restart/resources/ports/network, and 12/12 mount parity. Baseline scanner reproduced the false positive. Patched only the approved production regex line (patched hash `94b5c121cbe6e8ce0594db3f9aac9e3b84b15efd213bd67f248d0e6460c737bf`), preserved original source backup (mode 0600), and built candidate `sha256:2b00226cfe6a8dfdb1b9a83e16bff22a114b9769c126ed5849dcc9f96e9c3386` offline from original image ID `sha256:2e21b6c9c08e7842184f5b030a1c83e578dec069f57e7e9cf22ad1a4443ba086` with one COPY/no RUN. Candidate scanner passed benign/injection cases; actual Jacqueline AGENTS was clean for this finding; context smoke included benign Secretaría and excluded malicious HTML. After hermes-only recreation, config parity passed but two secondary s6 gateways stayed down after >100s and WhatsApp health returned HTTP 200 `connected=false`; required health gate failed. Executed prepared rollback; current image tag and source bytes restored to original, source hash `6ad8947a5a62db44f66b1cd33086e2b51c4a66019ef5301856e5efae59797341`. After rollback all three checked gateways were up but WhatsApp health remained `connected=false`; pre-deploy bridge health was unknown. Scanner fix is not live. Candidate image and protected artifacts remain in `/opt/hermes-hotfix/html-comment-20261014/`; private values never printed. No main Compose, data, profile, session, or unrelated config changed.
- **Health-check correction:** Independent verification at 2026-10-14 06:00:22 UTC confirmed original image/source restored, gateway-default/golden-game/lucky-club up after ~220/204/204 seconds, and in-container bridges on loopback ports 3000/3001/3002 returning HTTP 200 `status: connected` at 05:59 UTC. Bridge health has no `connected` boolean; the prior checker therefore reported a false disconnect, and readiness sampled before all service startup completed. Host-tailnet refusal is not the container loopback health signal. Parent authorized exactly one controlled retry using the same candidate and corrected bounded 240-second health gate; no main Compose changes, other service operations, or new settings.
- **T02 controlled retry (current production state):** Corrected health contract parses bridge `/health` `status: connected` on in-container loopback ports 3000/3001/3002 (the earlier `connected`-boolean assertion was invalid); readiness is bounded 240s with three required gateway services. Before retry, live snapshot parity passed for 78 env entries, 12 mounts, ports/networks/restart/resources and command identity. Reused candidate image `sha256:2b00226cfe6a8dfdb1b9a83e16bff22a114b9769c126ed5849dcc9f96e9c3386` from original `sha256:2e21b6c9c08e7842184f5b030a1c83e578dec069f57e7e9cf22ad1a4443ba086`; reapplied one regex line with source hash `94b5c121cbe6e8ce0594db3f9aac9e3b84b15efd213bd67f248d0e6460c737bf`. Recreated only hermes at 06:02:40–06:02:49 UTC; corrected readiness passed at 142s with all three gateways up and all three bridge health statuses connected. Post-deploy parity passed, actual Jacqueline AGENTS had no html-comment finding, scanner positives/negatives passed, and real prompt builder included benign Secretaría while excluding malicious comment. No message was sent or active session reset; existing conversation prompt caches may remain. Deployment is live and persistent in candidate image + patched host source; private snapshot/backup/rollback artifacts remain mode 0600. No main Compose or unrelated service/config changed.
- **Consolidated audit:** [04-audit-report.md](.specs/hermes-html-comment-false-positive/04-audit-report.md) records 34 findings with stable IDs and explicit evidence statuses; it distinguishes point-in-time checks from continuous monitoring and lists unresolved priorities. T03 checks passed: all IDs unique, all seven status categories represented, all relative report links resolve, no secrets/PII included, and `git diff --check` passed. No tests or production probes were run for this documentation-only task.
- **T03 work unit:** Consolidated the production audit and corrected stale current-state summaries in the feature task and this memory section. The three documentation files are structurally verified and committed locally; no push or deployment operation.

## 6. Audit Artifact Publication (T04, 2026-10-14)

- **Current status:** User explicitly authorized publication of an adapted audit report and production-compatible scanner patch to a new branch in private Kattegat-crew/Hermes-casinos. This is documentation/patch-artifact publication only; no production write/deployment, main mutation, PR, or unrelated branch push.
- **Goal and scope:** Publish only docs/audits/html-comment-scanner-false-positive.md and docs/audits/patches/html-comment-scanner-false-positive.patch on branch fix/jacqueline-context-scanner-audit, based on the observed target main commit. Use the corrected 34-finding audit and a patch generated from the verified original production scanner source.
- **Checks before publication:** Verify source baseline SHA-256 6ad8947a5a62db44f66b1cd33086e2b51c4a66019ef5301856e5efae59797341, patched SHA-256 94b5c121cbe6e8ce0594db3f9aac9e3b84b15efd213bd67f248d0e6460c737bf, apply/reverse behavior, scanner cases, privacy and links. Recheck main and branch absence before native API writes.
- **State:** Local report and patch artifacts are prepared and verified: 34 unique finding IDs/statuses, exact baseline/patched hashes, forward/reverse application, direct scanner behavior, links, privacy, and whitespace. Their SHA-256 values are recorded in T04 above. Native GitHub publication is blocked: github_create_blob returned exactly `MCP tool call requires approval, but approval policy is never`. Immediately before refusal, main was `0fa46ef7e7664ade1bc40ee135faf218223d369e` and the target branch was absent. No blob/tree/commit/branch was created; publication remains unchecked. No retry or alternate route was attempted. No Engram mutation is performed by this worker; parent maintains the memory mirror.
