# Implementation Tasks: Lightweight Hermes Observability

* **Associated Spec**: [01-spec.md](./01-spec.md)
* **Associated Design**: [02-design.md](./02-design.md)
* **Historical migration evidence**: [04-migration.md](./04-migration.md)
* **Status**: Local source work units committed and tested; first native review approved/acknowledged; DEV canary and production remain pending
* **Delivery strategy**: User chose `feature-branch-chain`. Hermes tracking branch is `feat/langfuse-fleet-observability`; source branches are local children of the public source tracker. No push, PR, or merge to main is authorized. Before any future PR, review the 717-line first slice against applicable PR-size policy and recommend a suitable PR boundary; this does not block or authorize any PR now.

## Working rules

1. Keep scope to existing Hermes DEV/PROD and current Langfuse `2.95.11`; do not add infrastructure, a server upgrade, new dependencies, or other client parity.
2. Preserve selected SDK `4.15.2`; no global SDK downgrade. Do not read or disclose secret values; unknown credentials are not absent credentials.
3. Keep read-only mapping trace-free. Any activation requires a named, authorized environment and a no-sensitive-content canary.
4. Use test-first for deterministic code changes; passive documentation is verified structurally. Obtain an independent reviewer at each implementation/activation phase boundary.
5. No production operation without explicit destination, operation, and credential/session authorization. Commit chain is authorized locally only; publication and deployment remain unauthorized.

## F1 — Inventory and scope review (complete)

- [x] **F1.1** Record runtime, SDK/server, alias, and evidence boundaries.
  - *Evidence*: Selected catalog plugin `2.0.0`, source SHA `c2a95963c442f3f23e4bc6fe0da898e1dd1fb63d`, SDK `4.15.2`. DEV PM generation `2852166f2cb3454db180810e2f3d29ef` uses Python `3.14.7` / pydantic-core `2.46.4`; import passed independent review. PROD generation `36f4b27c…` import is diagnostic-worker evidence only. Server is `2.95.11`, below the documented SDK v3/v4 floor `3.63.0`. Legacy bundled SDK `2.60.10` CPython 3.13 extension failure is separate, not the selected runtime's global root cause. Short `langfuse` alias: 8 enabled in DEV/PROD; legacy `observability/langfuse`: 10 DEV / 11 PROD. Root profiles disabled; two PROD test profiles unconfigured. Alias coexistence does not prove duplicate traces. Effective capture config and credential references remain unknown.
- [x] **F1.2** Independent inventory review.
  - *Outcome*: Corrected inventory accepted by `/root/phase1_review`; native RDD was unavailable, so this is not native RDD approval.

## Historical disposition — heavy server migration

- [x] A v3/v4 server-migration proposal was prepared and structurally reviewed during the earlier scope. The user subsequently rejected that heavy route and confirmed the existing Hermes + existing Langfuse approach. [04-migration.md](./04-migration.md) is retained as historical evidence only; its route, capacity analysis, and deployment gates are not current implementation tasks.
- No migration, install, image pull, database query, backup/restore, service operation, production trace, or server change was performed. The user approved local feature-branch chaining only; no publication or deployment.

## F2 — Minimum compatible Hermes path

- [x] **L1 — Read-only transport mapping**: Completed.
  - *Evidence*: Existing SDK `4.15.2` exposes low-level REST `LangfuseAPI` (`langfuse.api.client`) and `ingestion.batch` targeting `/api/public/ingestion`; avoid high-level `Langfuse(...).api`, which initializes its resource manager even when tracing is disabled. The authorized public checkout is `/opt/hermes-official-plugins`, branch `fix/langfuse-v2-rest`, based on `c2a95963c442f3f23e4bc6fe0da898e1dd1fb63d`.
- [x] **L2 — Bounded local adapter and tests**: Implemented in the authorized checkout as an explicit `HERMES_LANGFUSE_TRANSPORT=legacy` opt-in; existing default OTLP behavior is unchanged. It uses SDK4 REST only and metadata-only allowlisting before queueing. No new dependency, service, real credential, or live ingestion.
  - *Source chain*: Tracker base `c2a95963c442f3f23e4bc6fe0da898e1dd1fb63d`; unit 1 `fix/langfuse-v2-rest-01-transport` commit `e52545c16942f33398c371a75a0cea5ffdacec4f` (717 additions across 3 files); unit 2 `fix/langfuse-v2-rest-02-hermes-hooks` commit `de4c12af69e119e2fdde6d744fc8f19bb9e66cef` (309 additions, 6 deletions across 4 files), parent exactly unit 1. The Hermes feature tracker remains on its parent branch. No merge, push, or PR.
  - *Verification*: Initial test-first run: 6 failures. SDK4/server contract caught a `createdAt` timestamp-schema mismatch and it was corrected. Unit 1 clean worktree: 147 passed, 1 skipped; actual SDK wire/retry/split contract 5/5. Unit 2 clean worktree: 155 passed, 2 skipped; SDK standalone contract 3/3. Exact aggregate suite: `env -i PATH=/usr/bin:/bin HERMES_AGENT_REPO=/opt/hermes-agent PYTHONPATH=/opt/hermes-agent /usr/bin/python3 -m pytest -q /opt/hermes-official-plugins/langfuse/tests` — 155 passed, 2 skipped. Exact SDK standalone rerun: `env -i PATH=/usr/bin:/bin /opt/hermes-agent-data/installs/ffad2f5543956651/environments/2852166f2cb3454db180810e2f3d29ef/venv/bin/python -B /opt/hermes-official-plugins/langfuse/tests/test_legacy_sdk_contract.py` — exit 0 (serializer, retry-budget, and blocked-transport contracts passed; expected mocked-503 warning only). Both repo `git diff --check` commands passed. No live endpoint or ingestion is claimed.
  - *Limitations*: SDK retries are disabled to prevent compounded retry sleeps; one module-level daemon worker performs HTTP outside the producer lock with a bounded 128-event/512-KiB queue and one in-flight batch. A blocked request cannot be cancelled while the sole worker is occupied; queue saturation/process exit may drop events; response buffering is not bounded. The 50-ms wait applies per flush, not process shutdown.
- [x] **L3 — Independent implementation review**: independent reviewer accepted the final local correction with limitations. Native review of unit 1, lineage `review-7160735dc2c73400`, approved the clean candidate digest `4e090ccd7b1e8d0dd0eab2e8f7e6fabe2f7c9f2719103e76aa29d0b89e900457` with two nonblocking advisories; exact acknowledgement succeeded and burned that authority. Do not rerun/reopen unchanged unit 1. Unit 2 was assessed against unit 1 and returned `review_due=false`, reason `under_budget`; this is not approval of the complete feature. Native review findings remain follow-ups: `R3-001` concerns manual `run_sdk4` not being pytest-collected (manual execution proof exists); `R3-002` notes batch-wait assertion can depend on scheduling. They were nonblocking and were not auto-corrected.
  - *Gate before activation*: Runtime behavior and effective aliases/configuration remain unverified; verify no duplicate transport and audit privacy/capture mode before a canary.

## F3 — Authorized DEV validation

- [ ] **F3.1** Confirm the exact DEV profile/environment, credential reference and injection mechanism, effective capture/privacy settings, and rollback boundary. Credentials remain unknown, not absent.
- [ ] **F3.2** Only after explicit DEV activation authorization, send a no-sensitive-content canary and verify it becomes queryable in the intended Langfuse project. HTTP acceptance alone is insufficient. Record redacted evidence.
- [ ] **F3.3** Independent reviewer confirms evidence, privacy boundary, and bounded rollback before any next phase.

## F4 — Production, separately authorized

- [ ] **F4.1** Obtain explicit authorization naming PROD destination, operation, and credential/session; confirm rollback/maintenance boundary.
- [ ] **F4.2** Stage only the approved Hermes profile(s), verify health and a no-sensitive-content canary in the named authorized PROD environment, and roll back on the agreed trigger.
- [ ] **F4.3** Independent review and closeout; report every failed, skipped, unavailable, and pending check.

## Deferred scope

Codex, OpenCode, and AGY integrations are deferred. This plan does not promise parity. Codex's plugin requires a newer server than `2.95.11`; OpenCode captures prompt/tool payloads without a proven metadata-only control; AGY metadata-hook feasibility does not prove OTLP ingestion. Revisit only through a separate scoped decision after the Hermes path is understood.

## Current blockers and next step

- The local adapter is committed in two local child-branch source work units; user-selected `feature-branch-chain` resolved the prior delivery question. Neither push, PR, nor merge to main is authorized.
- A DEV canary still needs the exact named profile/environment, credential reference/injection scope, privacy/capture audit, and explicit activation authorization. No live ingestion has been proven.
- Native review approved and acknowledged unit 1 only; unit 2 remains under the native review slice budget. Do not imply approval of the full feature or any delivery authority.
- Project API-key references and injection boundary are unknown; no claim is made that keys are absent.
- Effective `HERMES_LANGFUSE_CAPTURE` is unknown; `sanitized` default is not content-free.
- PROD is unchanged and requires separately authorized destination, operation, and credential/session scope.
- The heavy migration route is declined, not a primary blocker for the lightweight path. Its prior capacity/backup evidence remains archived in `04-migration.md`.
- No runtime activation, live canary, or PROD change is complete. Codex/OpenCode/AGY remain deferred without a parity promise. Keep existing SDK pins and default OTLP behavior unchanged. The current native review boundary is unit 1; assess from that boundary after each later source work-unit commit.
