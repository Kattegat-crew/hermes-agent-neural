# Specification: Lightweight Hermes Observability on Existing Langfuse

* **Status**: Local SDK4 legacy REST adapter implemented, tested, and reviewed; DEV activation remains pending
* **Author**: Codex
* **Scope**: Existing Hermes DEV/PROD integrations with current Langfuse server `2.95.11`
* **Updated**: 2026-10-17

## 1. Problem and outcome

The selected Hermes catalog plugin is version `2.0.0` and uses Langfuse SDK `4.15.2` in PM-managed Python 3.14. The selected DEV runtime imports successfully; PROD import evidence is from a diagnostic worker. The existing Langfuse server is `2.95.11`, below the documented `3.63.0` SDK v3/v4 compatibility floor. Imports and enabled profiles do not prove ingestion.

The user rejected the proposed heavy v3/v4 server migration and approved the minimum compatibility path using the existing Hermes fleet and existing Langfuse. An opt-in SDK4 legacy REST adapter has been implemented and locally reviewed without a global SDK downgrade, new service, or new dependency. Live DEV compatibility and queryable ingestion remain unverified.

## 2. Goals

- Map the current Hermes SDK4 integration and its actual transport/API calls against existing Langfuse v2 `2.95.11` support, using local source, tests, and authoritative documentation.
- Preserve the existing SDK pin and validate the implemented REST adapter through deterministic contract tests and independent review before any activation.
- Keep existing SDK `4.15.2` selected; do not change global pins or infer that a separate legacy SDK2 CPython 3.13 extension failure is the active root cause.
- Require independent review at the end of each implementation/activation phase.
- Verify ingestion only through an explicitly authorized, named DEV canary with approved credentials and no sensitive content. Production requires a separate authorization naming destination, operation, and credential/session.

## 3. Non-goals and constraints

- No Langfuse server migration/upgrade, new collectors, services, cloud resources, or alternate observability backend.
- No global SDK downgrade, package installation, or new dependency/binary without explicit approval and an exact pin.
- No Codex/OpenCode/AGY parity promise; those integrations are deferred and are not prerequisites for Hermes trace recovery.
- No traces during read-only mapping or documentation. No prompts, model outputs, tool arguments/results, or other sensitive content in any canary.
- No reading or copying secret values. Credential references remain unknown, not absent.
- No runtime/config/service/production operation is authorized by this assessment alone.

## 4. Requirements and acceptance

### L1 — read-only compatibility mapping (complete)

Record the selected SDK4 integration's entry point, exact transport/API operations, configuration and credential injection boundary, and relevant existing tests. Compare those operations with the current server's documented supported ingestion interfaces. Distinguish verified support, unsupported calls, and unresolved behavior; do not infer compatibility from import success, HTTP acceptance, or an SDK's presence. Do not emit a trace or access secret values.

### L2 — bounded local adapter (implemented and tested)

The explicit `HERMES_LANGFUSE_TRANSPORT=legacy` option uses the existing SDK4 low-level REST `LangfuseAPI`; the existing OTLP default remains unchanged. The local source-chain implementation and tests are complete. It is not runtime activation or live-ingestion proof. Preserve the SDK pin and do not add dependencies. See the task/design docs for commits and verification evidence.

### L3 — independent review

An independent reviewer checks the chosen adapter and tests before any runtime activation. A review result does not authorize credentials access, deployment, or a production operation.

### DEV activation gate

Before a canary, explicitly name and authorize the DEV environment/profile, confirm the credential reference and effective capture mode, and ensure the canary contains no sensitive content. Verify the trace becomes queryable in the intended project; HTTP acceptance alone is insufficient. Independent review follows the phase. Keep activation pending if any authorization, credential, privacy, or ingestion evidence is missing.

### PROD gate

Production is not authorized. A later request must name the target, operation, and credential/session; pass DEV acceptance and review; and retain a bounded rollback plan.

## 5. Preserved inventory facts

- Selected catalog plugin: `2.0.0`, source SHA `c2a95963c442f3f23e4bc6fe0da898e1dd1fb63d`, SDK `4.15.2`.
- DEV PM generation `2852166f2cb3454db180810e2f3d29ef`: Python `3.14.7`, pydantic-core `2.46.4`; import passed independent review. PROD generation `36f4b27c…`: same import result reported by diagnostic worker, not independently reviewed.
- Existing Langfuse server: `2.95.11`; documented SDK v3/v4 floor: `3.63.0`.
- A separate bundled SDK `2.60.10` lazy path has a CPython 3.13 extension failure under Python 3.14; this is not the selected PM runtime's global root cause.
- Short `langfuse` alias: 8 enabled in DEV and PROD; legacy `observability/langfuse`: 10 DEV, 11 PROD. DEV/PROD root profiles are disabled; two PROD test profiles are unconfigured. Coexisting aliases do not prove duplicate traces.
- Effective `HERMES_LANGFUSE_CAPTURE` is unknown; default `sanitized` is not content-free. Project credential references remain scoped-unknown; do not claim keys are absent.

## 6. Deferred integrations

Codex's Langfuse plugin requires server `>=3.95`, beyond current v2; native Codex OTLP is not supported by server `2.95.11`. OpenCode's plugin captures prompt/tool payloads without a proven metadata-only control. AGY metadata-hook feasibility does not establish OTLP compatibility. These are future, separate decisions—not scope for the minimum Hermes path.
