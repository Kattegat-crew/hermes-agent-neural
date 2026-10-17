# Feature Specification: Langfuse Fleet Observability

* **Status**: In Progress — corrected Phase 1 inventory accepted conditionally on these documentation corrections
* **Author**: Codex
* **Target Module**: Hermes DEV/PROD operations, Codex, OpenCode, and AGY integrations
* **Created**: 2026-10-16
* **Updated**: 2026-10-16

---

## 1. Problem Statement & Motivation

The selected Hermes catalog plugin is Langfuse plugin `2.0.0`, source commit `c2a95963c442f3f23e4bc6fe0da898e1dd1fb63d`, using Langfuse SDK `4.15.2` in PM-managed Python 3.14 environments. The deployed server is `2.95.11`, below the documented `3.63.0` minimum for SDK v3/v4. Imports can succeed while server compatibility and ingestion remain unproven. A separate legacy SDK `2.60.10` path has a CPython 3.13 lazy-package import failure, but that is not the selected runtime's global root cause.

The work is phased so that compatibility, privacy, credentials, and rollback are validated in DEV before any separately authorized production rollout.

## 2. Goals & Non-Goals

### Goals
- [ ] Reconcile the selected SDK4 catalog path, legacy SDK2 path, profile aliases, and Langfuse server compatibility before choosing implementation.
- [ ] Obtain the user's decision on server migration for SDK4/OTLP or adaptation of the modern integration to the legacy server route before functional implementation.
- [ ] For an activation phase, prove a positive ingestion canary in a specifically named, explicitly authorized environment before declaring an integration operational; include no sensitive content.
- [ ] Inventory and instrument approved Hermes profiles, Codex, OpenCode, and AGY only after compatibility and data-minimization decisions are resolved.
- [ ] Require an independent review at the end of every phase before advancing.
- [ ] Stage production only after DEV acceptance and explicit approval of the server, credential, and rollout operations.

### Non-Goals (Out of Scope)
- No blanket authorization to upgrade Langfuse, modify services, restart processes, read or disclose secrets, or access remote systems.
- Inventory and documentation work do not emit traces. An activation canary requires a named, explicitly authorized environment and must contain no sensitive content.
- No production rollout is authorized by this specification.
- No SDK reinstall/downgrade, server migration, dependency change, or integration adaptation is approved before the explicit compatibility decision.
- No prompt, tool-argument, model-response, or other sensitive-content capture unless an explicit privacy decision approves the exact fields and retention.
- No assertion that missing credentials or incomplete service/profile bindings imply absence of telemetry.

## 3. User Stories & Functional Requirements

* **US-1**: As an operator, I want each approved integration to be verifiably compatible and ingesting, so that dashboards reflect real fleet activity rather than package-presence assumptions.
  * **Requirement 1.1**: Distinguish the selected PM-managed SDK4 catalog plugin from the separate legacy SDK2 implementation; record exact versions and import evidence separately.
  * **Requirement 1.2**: A phase is not accepted until its independent reviewer returns a terminal result and its applicable phase acceptance evidence is recorded.
  * **Requirement 1.3**: For an activation phase, require a positive ingestion canary only in a specifically named, explicitly authorized environment, with no sensitive content. No trace is emitted as part of inventory or documentation work.
  * **Requirement 1.4**: Keep credentials in Vault or approved mode-0600 secret files; never put secret values in Git or Markdown.
  * **Requirement 1.5**: Default to metadata-only, minimized telemetry; block integrations that cannot meet the approved data policy.
  * **Requirement 1.6**: Audit the effective `HERMES_LANGFUSE_CAPTURE` setting before activation. Supported modes are `metadata`, `sanitized`, and `full`; default `sanitized` is not content-free.

## 4. Acceptance Criteria & Invariants

* **Scenario 1 — SDK/server compatibility decision**
  * **Given**: The selected profile plugin uses SDK `4.15.2` and the deployed server is `2.95.11`.
  * **When**: The user selects and separately authorizes a compatible migration or integration adaptation path.
  * **Then**: Verify the exact selected path, audit effective capture mode before activation, and document rollback. Any canary is limited to a named, authorized environment and contains no sensitive content. Inventory/documentation phases emit no trace and do not require runtime rollback.

* **Scenario 2 — Unsupported integration or privacy mismatch**
  * **Given**: A plugin requires a newer Langfuse server or captures prompt/tool payloads without an approved minimization control.
  * **When**: The compatibility/privacy gate is evaluated.
  * **Then**: The integration remains disabled; no server upgrade, payload capture, or production change is inferred as authorized.

* **Scenario 3 — Production rollout**
  * **Given**: DEV acceptance and its phase review are complete.
  * **When**: A distinct production authorization names the target, operation, and credential/session.
  * **Then**: Stage only the approved profiles, verify a positive canary with no sensitive content and health in the named authorized production environment, and retain a reversible rollback boundary; otherwise do not touch production.

## 5. Security, VPS & Operational Considerations

- Project API keys were not found in the scoped Vault metadata review; this is not evidence that keys do not exist. No key value may be copied into this spec or task file.
- Existing PROD Vault access uses the specifically authorized DEV SSH identity; local Vault bootstrap is unavailable. Do not probe or substitute another remote identity.
- The service-to-profile binding is incomplete; do not infer service ownership from unit names.
- OpenCode's official Langfuse integration captures prompts and tool payloads; no metadata-only control has been proven. AGY metadata-only hook feasibility is not equivalent to verified OTLP ingestion.
- Codex's official plugin requires Langfuse `>=3.95`; native Codex OTLP is not supported by the current v2.95.11 server. This and the SDK4 server minimum are decision gates, not authorization to upgrade.
