# Feature Specification: Langfuse Fleet Observability

* **Status**: In Progress — Phase 1 inventory accepted with downstream gaps tracked
* **Author**: Codex
* **Target Module**: Hermes DEV/PROD operations, Codex, OpenCode, and AGY integrations
* **Created**: 2026-10-16
* **Updated**: 2026-10-16

---

## 1. Problem Statement & Motivation

Langfuse is present in the fleet, but the evidence does not establish reliable trace ingestion across Hermes profiles and developer tools. The current server is Langfuse `2.95.11`; SDK packages are present but Hermes imports fail because the active environment is CPython 3.14 while its lazy-package tree contains CPython 3.13 extensions. A successful import or profile configuration alone is not proof that an event reached Langfuse.

The work is phased so that compatibility, privacy, credentials, and rollback are validated in DEV before any separately authorized production rollout.

## 2. Goals & Non-Goals

### Goals
- [ ] Restore Hermes DEV importability using the existing pinned dependency set and a compatible environment; do not add dependencies without approval and an exact pin.
- [ ] For an activation phase, prove a positive ingestion canary in a specifically named, explicitly authorized environment before declaring an integration operational; include no sensitive content.
- [ ] Inventory and instrument the approved Hermes profiles, Codex, OpenCode, and AGY only after compatibility and data-minimization decisions are resolved.
- [ ] Require an independent review at the end of every phase before advancing.
- [ ] Stage production only after DEV acceptance and explicit approval of the server, credential, and rollout operations.

### Non-Goals (Out of Scope)
- No blanket authorization to upgrade Langfuse, modify services, restart processes, read or disclose secrets, or access remote systems.
- Inventory and documentation work do not emit traces. An activation canary requires a named, explicitly authorized environment and must contain no sensitive content.
- No production rollout is authorized by this specification.
- No prompt, tool-argument, model-response, or other sensitive-content capture unless an explicit privacy decision approves the exact fields and retention.
- No assertion that missing credentials or incomplete service/profile bindings imply absence of telemetry.

## 3. User Stories & Functional Requirements

* **US-1**: As an operator, I want each approved integration to be verifiably compatible and ingesting, so that dashboards reflect real fleet activity rather than package-presence assumptions.
  * **Requirement 1.1**: Record exact runtime, SDK, server, and plugin versions before changing an environment.
  * **Requirement 1.2**: A phase is not accepted until its independent reviewer returns a terminal result and its applicable phase acceptance evidence is recorded.
  * **Requirement 1.3**: For an activation phase, require a positive ingestion canary only in a specifically named, explicitly authorized environment, with no sensitive content. No trace is emitted as part of inventory or documentation work.
  * **Requirement 1.4**: Keep credentials in Vault or approved mode-0600 secret files; never put secret values in Git or Markdown.
  * **Requirement 1.5**: Default to metadata-only, minimized telemetry; block integrations that cannot meet the approved data policy.

## 4. Acceptance Criteria & Invariants

* **Scenario 1 — DEV Hermes recovery**
  * **Given**: The active Hermes runtime is Python 3.14 and the package tree contains CPython 3.13 extensions.
  * **When**: The approved DEV repair is staged using the existing exact pins.
  * **Then**: A real Hermes runtime imports the SDK successfully. If the phase activates telemetry, a canary is observed in the intended Langfuse project only after the environment is named and authorized, and the canary contains no sensitive content. Document rollback before the phase reviewer is requested. Inventory/documentation phases emit no trace and do not require runtime rollback.

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
- Codex's official plugin requires Langfuse `>=3.95`, while the current server is `2.95.11`; this is a decision gate, not authorization to upgrade.
