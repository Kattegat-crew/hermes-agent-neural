# Implementation Tasks: Langfuse Fleet Observability

* **Associated Spec**: [01-spec.md](./01-spec.md)
* **Associated Design**: [02-design.md](./02-design.md)
* **Status**: In Progress — corrected Phase 1 inventory accepted conditionally; implementation path undecided
* **Delivery strategy**: `ask-on-risk` (forecast is uncertain, approximately 300–600 authored lines across implementation; no PR/chain strategy selected)

---

## Execution Guidelines

1. Change only the exact approved files and systems for the active phase; never infer deployment authorization from this plan.
2. User requires an independent reviewer at each phase boundary. Do not start the next phase until the current phase's review has a terminal result.
3. For code changes, use test-first when a meaningful deterministic test exists; run `scripts/run_tests.sh` with focused selectors as applicable. Passive documentation requires structural readback instead.
4. No secrets in Git or Markdown. No new dependencies/binaries without explicit approval and an exact pinned version. Inventory and documentation work emit no traces.
5. Mutating phases need a scoped rollback boundary. Telemetry-activation phases additionally require a positive canary only in a specifically named, explicitly authorized environment, with no sensitive content. Apply only the checks relevant to the phase; inventory needs neither ingestion evidence nor runtime rollback.

## Phase Checklist

### F1 — Inventory and scope review
- [x] **Task F1.1**: Record DEV/PROD runtime, SDK/server, profile, and developer-tool inventory; distinguish SDK presence from importability and ingestion proof.
  - *Route*: Delegated direct, bounded read-only inventory; no code changes.
  - *Evidence*: The selected official catalog plugin is version `2.0.0`, source SHA `c2a95963c442f3f23e4bc6fe0da898e1dd1fb63d`, with SDK `4.15.2`. DEV PM generation `2852166f2cb3454db180810e2f3d29ef` uses Python `3.14.7` and pydantic-core `2.46.4`; its SDK import passed the independent reviewer (exit 0). PROD generation `36f4b27c…` has the same import result per the diagnostic worker, not an independent reviewer. Server `2.95.11` is below the SDK v3/v4 minimum `3.63.0`. The legacy bundled SDK `2.60.10` CPython 3.13 lazy-package failure is a separate path, not the selected runtime's global root cause. Short `langfuse` alias: 8 enabled in each environment; legacy `observability/langfuse`: 10 DEV, 11 PROD. DEV root is disabled; PROD root is disabled and two test profiles are unconfigured. Alias overlap does not prove duplicate traces. Effective `HERMES_LANGFUSE_CAPTURE` values are unknown; supported `metadata|sanitized|full`, default `sanitized`, is not content-free.
  - *Verification*: Corrected evidence, provenance, and limitations are recorded; no trace or remote mutation occurred. Runtime rollback is **N/A** for this read-only phase; functional tests are **N/A** for passive docs.
- [x] **Task F1.2**: Obtain independent review of this phase and record remaining findings.
  - *Route*: Delegated independent review.
  - *Status*: Corrected inventory accepted conditionally on these documentation corrections by `/root/phase1_review`. The earlier SDK2/CPython ABI global-root-cause conclusion is invalidated. Native RDD was unavailable; this acceptance is not native RDD approval.
  - *Verification*: Corrected inventory and remaining decision gates are documented; no runtime rollback or ingestion canary applies.

### F2 — Integration reconciliation and compatibility decision
- [ ] **Task F2.1**: Map selected/legacy aliases, PM generations, and effective capture settings; document the SDK/server compatibility decision and obtain the user's choice before implementation.
  - *Route*: Delegated read-only discovery and user decision; the selected DEV PM runtime import is verified, while PROD import evidence is attributed to the diagnostic worker. Project credential references remain scoped-unknown; never read or expose key values.
  - *Gate*: Server migration for SDK4/OTLP versus adapting the modern integration to the legacy server route. The latter is not a simple SDK downgrade and does not enable native Codex OTLP on server v2. No installs, server migration, dependency change, or payload capture are authorized by this plan.
- [ ] **Task F2.2**: Implement only the explicitly chosen and separately authorized compatibility path.
  - *Route*: One bounded writer for any multi-file change; use test-first where deterministic behavior tests apply.
  - *Verification*: Compatibility checks and focused tests; audit effective capture configuration before activation. A canary is required only if telemetry activates and only in a named, authorized environment with no sensitive content.
  - *Rollback*: Record exact files/services and rollback boundary before any mutating operation; server migration requires its own approved rollout/rollback plan.
- [ ] **Task F2.3**: Independent review of the chosen implementation; stop before F3 until terminal result.

### F3 — Hermes fleet profile coverage and credential mapping
- [ ] **Task F3.1**: Resolve exact DEV/PROD profile-to-service bindings and identify approved project credential references without exposing values.
  - *Route*: Delegated read-only mapping.
  - *Gate*: Do not infer bindings from service-unit names; unknown Vault state is not proof of missing keys. Do not stage integrations until the F2 compatibility path is chosen and authorized.
- [ ] **Task F3.2**: Stage the approved fleet profile configuration with metadata minimization and applicable activation verification.
  - *Route*: One bounded writer; tests and configuration validation must match the active Hermes contracts. A positive canary applies only if this task activates telemetry, and only in a named, explicitly authorized environment with no sensitive content.
  - *Rollback*: Disable/revert only the staged Langfuse settings for the confirmed profile set; record before rollout.
- [ ] **Task F3.3**: Independent review; stop before F4 until terminal result.

### F4 — Codex, OpenCode, and AGY integration gates
- [ ] **Task F4.1**: Decide whether server migration is approved and define privacy-safe telemetry fields for each client.
  - *Route*: User/owner decision; no server upgrade or payload capture is implied.
  - *Evidence*: Codex Langfuse plugin requires server `>=3.95`, beyond current `2.95.11`; native Codex OTLP is unavailable on this v2 server. OpenCode plugin requires OpenCode `>=1.18.29` and captures prompts/tool payloads without a proven metadata-only switch; AGY metadata hook feasibility does not yet establish OTLP support.
- [ ] **Task F4.2**: Implement only approved compatible integrations, with explicit opt-in, minimized data, and a positive event in the intended project.
  - *Route*: One bounded writer per coherent implementation task; no new dependency or binary without exact-version approval. A positive canary applies only if the integration is activated, in a named, explicitly authorized environment, with no sensitive content.
  - *Rollback*: Disable or revert only the confirmed integration settings/files; record exact boundary before activation.
- [ ] **Task F4.3**: Independent review; stop before F5 until terminal result.

### F5 — Separately authorized PROD rollout and monitoring
- [ ] **Task F5.1**: Obtain explicit authorization naming production destination, operations, and credential/session; confirm approved maintenance/rollback window.
  - *Route*: Operator-controlled rollout only; this plan grants no remote permission.
- [ ] **Task F5.2**: Stage approved production changes, validate health and applicable telemetry activation, monitor, and roll back on the agreed trigger.
  - *Route*: One controlled change at a time; only after explicit PROD authorization, capture redacted evidence. If telemetry is activated, validate a canary in the named PROD environment with no sensitive content.
  - *Rollback*: Restore the pre-phase production settings/runtime for the exact approved profile set; no broad rollback without authorization.
- [ ] **Task F5.3**: Independent review and closeout; report failed, skipped, unavailable, and pending checks.

## Current Blockers / Decisions

- Phase 1 inventory was accepted by `/root/phase1_review` with tracked downstream gaps; this was not native RDD approval.
- DEV staging owner and exact runtime/config change surface are not established.
- Project API-key values are not present in the approved inventory; no absence claim is made. Credential reference and injection boundary must be resolved without disclosing values.
- The selected SDK4 plugin is not server-compatible with v2.95.11; choose between a separately authorized compatible server migration and a validated legacy-server adaptation before functional implementation. SDK downgrade alone is not the adaptation plan.
- Effective `HERMES_LANGFUSE_CAPTURE` configuration is unknown; `sanitized` default is not content-free and must be audited before activation.
- OpenCode's content-capturing behavior needs an explicit privacy decision or a verified metadata-only alternative.
- Production rollout requires explicit destination, operation, and credential/session authorization.

## Applicable Checks & Evidence

- Passive docs: `git diff --check` and full structural readback; no functional test runner applies.
- Hermes behavior changes: relevant test first, then `scripts/run_tests.sh` with focused selectors and real import. Require an approved positive canary only when the change activates telemetry.
- Client integration changes: official version compatibility, config validation, and privacy-field review. Require a positive canary only when the change activates telemetry.
- Record each command's exact observed result in its task before checking the item off. A reviewer gate is separate from functional verification.

## Progress & Next Step

Corrected F1 inventory was accepted conditionally on this documentation correction by `/root/phase1_review`. Initial documentation work-unit: `d1f34cba59`; prior scope corrections: `27b2e43a51` and `427407feb6`; no prior commit is amended. F2.1 is reconciliation and a user decision, not an SDK ABI repair. Do not begin functional implementation until the user chooses a compatibility path and exact operations/credentials are authorized.
