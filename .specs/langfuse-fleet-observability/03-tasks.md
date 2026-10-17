# Implementation Tasks: Langfuse Fleet Observability

* **Associated Spec**: [01-spec.md](./01-spec.md)
* **Associated Design**: [02-design.md](./02-design.md)
* **Status**: In Progress — Phase 1 inventory accepted; downstream gaps tracked
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
  - *Evidence*: Explorer inventory handoff reports Python `3.14.7` on both hosts; SDK `2.60.10`; Langfuse server `2.95.11`; CPython 3.13 extensions in the lazy-package tree fail to import under active Python 3.14. DEV Codex `0.163.0`, OpenCode `1.18.35`, AGY `1.4.0`; PROD Codex absent, OpenCode `1.18.18`, AGY `1.1.14`. Explorer reports 10 enabled named DEV profiles (root and vigia off) and 11 enabled named PROD profiles (root and two test profiles off/unconfigured). Reviewer accepted the inventory scope but did not independently enumerate profile names; the explorer handoff is the source for these counts.
  - *Verification*: Inventory evidence, limitations, and review are recorded; no trace was emitted and no remote mutation occurred. Runtime rollback is **N/A** for this read-only phase; functional tests are **N/A** for passive docs.
- [x] **Task F1.2**: Obtain independent review of this phase and record remaining findings.
  - *Route*: Delegated independent review.
  - *Status*: Accepted by `/root/phase1_review`; no technical contradictions. Downstream staging/credential/compatibility gaps remain tracked below. Reviewer did not independently enumerate profile names. Native RDD was unavailable; this acceptance is not native RDD approval.
  - *Verification*: Reviewer accepted the inventory phase with tracked downstream gaps; no runtime rollback or ingestion canary applies.

### F2 — Hermes DEV ABI repair and proof
- [ ] **Task F2.1**: Identify the staging owner, runtime boundary, project credential source, and exact allowed DEV change surface.
  - *Route*: Delegated exploration before implementation; do not assume a staging owner or read/print secret values.
  - *Gate*: No repair until boundaries, credential injection, existing pins, rollback, and user authorization are explicit.
- [ ] **Task F2.2**: Repair the DEV Hermes import/runtime ABI using existing pins; add or update behavior tests only if the current test contract is applicable.
  - *Route*: One delegated writer for multi-file changes; preserve test-first red/green evidence.
  - *Verification*: Focused tests via `scripts/run_tests.sh`; real runtime import; if telemetry is activated, a positive canary only in a named, explicitly authorized environment and with no sensitive content.
  - *Rollback*: Revert only the phase's environment/config changes and restore the prior known runtime; exact commands/boundary must be recorded before execution.
- [ ] **Task F2.3**: Independent review; stop before F3 until terminal result.

### F3 — Hermes fleet profile coverage and credential mapping
- [ ] **Task F3.1**: Resolve exact DEV/PROD profile-to-service bindings and identify approved project credential references without exposing values.
  - *Route*: Delegated read-only mapping.
  - *Gate*: Do not infer bindings from service-unit names; unknown Vault state is not proof of missing keys.
- [ ] **Task F3.2**: Stage the approved fleet profile configuration with metadata minimization and applicable activation verification.
  - *Route*: One bounded writer; tests and configuration validation must match the active Hermes contracts. A positive canary applies only if this task activates telemetry, and only in a named, explicitly authorized environment with no sensitive content.
  - *Rollback*: Disable/revert only the staged Langfuse settings for the confirmed profile set; record before rollout.
- [ ] **Task F3.3**: Independent review; stop before F4 until terminal result.

### F4 — Codex, OpenCode, and AGY integration gates
- [ ] **Task F4.1**: Decide whether server migration is approved and define privacy-safe telemetry fields for each client.
  - *Route*: User/owner decision; no server upgrade or payload capture is implied.
  - *Evidence*: Codex Langfuse plugin requires server `>=3.95`, beyond current `2.95.11`; OpenCode plugin requires OpenCode `>=1.18.29` and captures prompts/tool payloads without a proven metadata-only switch; AGY metadata hook feasibility does not yet establish OTLP support.
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
- Codex requires a server version newer than the current deployment. Any Langfuse server migration needs a separate explicit decision and authorization.
- OpenCode's content-capturing behavior needs an explicit privacy decision or a verified metadata-only alternative.
- Production rollout requires explicit destination, operation, and credential/session authorization.

## Applicable Checks & Evidence

- Passive docs: `git diff --check` and full structural readback; no functional test runner applies.
- Hermes behavior changes: relevant test first, then `scripts/run_tests.sh` with focused selectors and real import. Require an approved positive canary only when the change activates telemetry.
- Client integration changes: official version compatibility, config validation, and privacy-field review. Require a positive canary only when the change activates telemetry.
- Record each command's exact observed result in its task before checking the item off. A reviewer gate is separate from functional verification.

## Progress & Next Step

F1 inventory and review are accepted, with profile counts sourced from the explorer handoff rather than reviewer enumeration. Initial documentation work-unit: `d1f34cba59` (`docs(observability): define phased Langfuse fleet plan`). Review corrections were committed as `27b2e43a51` (`docs(observability): clarify phase-specific canary gates`); the initial commit was not amended. F2.1 read-only discovery may proceed. Keep F2.2 implementation gated until the DEV staging owner, exact change surface, credential injection, pins, rollback, and explicit authorization are resolved.
