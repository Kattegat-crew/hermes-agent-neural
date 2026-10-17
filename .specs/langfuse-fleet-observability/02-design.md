# Technical Design: Lightweight Hermes Observability

* **Associated Spec**: [01-spec.md](./01-spec.md)
* **Status**: Two local source work units committed and tested; first native review approved/acknowledged, second remains under review budget; DEV validation pending
* **Target Revision**: `feat/langfuse-fleet-observability`

## 1. Scope and boundary

Keep the solution on the existing Hermes-to-Langfuse path. The selected PM-managed plugin uses SDK4 in Python 3.14; the current server is Langfuse `2.95.11`. SDK4 imports in DEV, but the server is below the documented SDK v3/v4 floor `3.63.0`. The local REST compatibility path is implemented as an opt-in; DEV compatibility and ingestion still require authorized validation.

Do not migrate/upgrade the server, add a collector or service, change global SDK pins, install dependencies, or expand to other clients. The previously prepared server migration route is retained as historical evidence in [04-migration.md](./04-migration.md), but the user rejected it as the current solution.

## 2. Assessment sequence

1. **Read-only mapping**: inspect selected plugin/runtime source and tests to identify exact transport calls, current legacy endpoint support, request/response semantics, and credential/config boundaries. Use documentation and local evidence; do not emit traces or read secret values.
2. **Bounded local adapter**: implemented in the authorized public source checkout using the existing SDK's low-level REST-only `LangfuseAPI` from `langfuse.api.client`, not the high-level `Langfuse(...).api` path. Preserve SDK `4.15.2`; no OTLP client or dependency was added. Contract tests cover serialized request schemas and current-server response handling.
3. **Independent review**: the local correction was independently accepted with limitations. Native review of the first source work unit ended approved and its exact acknowledgement burned authority; the second source work unit was assessed `under_budget` and was not yet due for native review. No activation authorization is implied. Do not substitute an SDK downgrade or infrastructure migration.
4. **Authorized DEV canary**: only after explicit environment/profile and credential scope are approved, effective capture settings are audited, and a no-sensitive-content canary is prepared. Confirm the resulting trace is queryable in the intended project; HTTP acceptance is not ingestion proof.
5. **Production**: requires separate explicit destination, operation, and credential/session authorization after DEV acceptance and review.

## 3. Invariants and privacy

- SDK import, plugin initialization, alias enablement, event emission, server acceptance, and queryable ingestion are separate evidence points.
- Keep selected SDK `4.15.2` unchanged unless separately approved. The legacy SDK2 CPython extension issue is a separate path, not a global-root-cause diagnosis.
- Never log or document API-key values. Existing credential references are unknown, not evidence of key absence.
- Effective `HERMES_LANGFUSE_CAPTURE` is unknown; `sanitized` is not content-free. Audit it before activation.
- Only operational metadata is in scope. Exclude prompts, outputs, tool arguments/results, and sensitive identifiers. A canary must contain no sensitive content.
- The `langfuse` and `observability/langfuse` aliases coexist; that is a duplication risk, not proof of duplicate emissions.
- No new dependencies/binaries without explicit approval and an exact pin. No runtime activation, service, server, or production changes have been made.

## 4. Trade-offs

| Path | Current disposition | Reason |
|---|---|---|
| Minimal local Hermes transport adaptation | Implemented locally; activation pending | Retains existing Langfuse and selected SDK through explicit opt-in REST transport; live compatibility is not yet proven. |
| Global SDK downgrade | Rejected as a blind fix | The selected plugin uses SDK4 APIs; the legacy SDK2 import issue is separate. |
| Langfuse v3/v4 server migration | Declined for current scope; retained in `04-migration.md` as historical evidence | User considers the required infrastructure disproportionate to the current Hermes need. |
| Codex/OpenCode/AGY parity | Deferred | Not required for Hermes trace recovery; privacy and compatibility gates remain unresolved. |

## 5. Compatibility evidence

The selected official catalog plugin is `2.0.0`, source SHA `c2a95963c442f3f23e4bc6fe0da898e1dd1fb63d`, pinning `langfuse==4.15.2`. DEV PM generation `2852166f2cb3454db180810e2f3d29ef` uses Python `3.14.7` and pydantic-core `2.46.4`; its import passed independent review. PROD generation `36f4b27c…` was reported to import the same stack by a diagnostic worker, not an independent reviewer. The legacy bundled SDK `2.60.10` has a CPython 3.13 extension failure under Python 3.14, separate from the selected PM runtime.

Short `langfuse` alias: 8 enabled in each environment. Legacy `observability/langfuse`: 10 DEV / 11 PROD. Root profiles are disabled; two PROD test profiles are unconfigured. Effective capture settings, per-profile credential mapping, and ingestion are not yet verified.

### L1 discovery and L2 local adapter — reviewed, not activated

The authorized public source chain is rooted at tracker revision `c2a95963c442f3f23e4bc6fe0da898e1dd1fb63d`. Unit 1 is commit `e52545c16942f33398c371a75a0cea5ffdacec4f` on `fix/langfuse-v2-rest-01-transport`; unit 2 is commit `de4c12af69e119e2fdde6d744fc8f19bb9e66cef` on `fix/langfuse-v2-rest-02-hermes-hooks`, parented exactly to unit 1. These commits add the explicit `HERMES_LANGFUSE_TRANSPORT=legacy` opt-in using existing SDK4 `LangfuseAPI` REST ingestion to `/api/public/ingestion`; default OTLP remains unchanged. The legacy route is metadata-only and applies its allowlist before queueing. No dependency, service, real credential, or live ingestion was added or used. The Hermes tracking repository remains on its feature branch; the child source branches are local only, with no merge to main, push, or PR.

The adapter contract and review covered:

- One REST transport only; no parallel OTLP client.
- Apply a strict metadata allowlist before any queue/buffer.
- Bounded request timeout, batch size, retries, flush/shutdown behavior; disable redirects so authorization headers cannot be forwarded.
- Stable event IDs across retries, while assigning distinct IDs to distinct updates; inspect HTTP `207` per-item failures rather than treating the status as full success.
- Preserve trace, parent, and session relationships. Usage input/output/total values are strict integers; do not fabricate missing values.
- Test serialized request schemas and responses against the `2.95.11` contract, not only SDK4 model validation.

Test/review evidence: initial test-first run had 6 failures; SDK contract testing exposed and corrected a `createdAt` timestamp-schema mismatch. A first independent review identified compounded SDK and outer retries (up to 6 requests and 4 long Retry-After sleeps); correction disables SDK retries and uses one module-level daemon worker with no network I/O under the producer lock, a 128-event/512-KiB queue, and one in-flight batch. Independent full suite: 155 passed, 2 skipped. Selected SDK4/Python 3.14 standalone contract and parent clean-environment rerun both exited 0; `git diff --check` exited 0. Review accepted the correction with limitations.

Known limits: one blocked HTTP request cannot be cancelled while the sole worker is occupied; queue saturation and process exit can drop telemetry; arbitrary HTTP response buffering is not bounded. The configured 50-ms wait is per flush, not a process-shutdown bound. No live ingestion acceptance was demonstrated. The first native review bound the clean unit-1 candidate digest `4e090ccd7b1e8d0dd0eab2e8f7e6fabe2f7c9f2719103e76aa29d0b89e900457`; reliability capture approved with two nonblocking advisories, and exact acknowledgement burned that authority. Do not reopen the unchanged unit. Unit 2 assessment against unit 1 returned `review_due=false`, reason `under_budget`; this is not approval of the whole feature. Recorded follow-up advisories concern the non-collected manual SDK function runner and schedule-dependent batch-wait test assertion; they were nonblocking, not auto-corrected, and do not alter reviewed candidate bytes. The review boundary remains unit 1 for future source commits.

The external source is the public `NousResearch/hermes-official-plugins` checkout described above. Repository acquisition did not add a runtime service or dependency. The installed copy is not a source fix, and the inactive bundled legacy implementation is not the target.

## 6. References

- [Langfuse SDK/server compatibility](https://langfuse.com/docs/compatibility)
- [Langfuse Python SDK overview](https://langfuse.com/docs/observability/sdk/overview)
- [Langfuse v2 → v3 self-hosted migration guide](https://langfuse.com/self-hosting/upgrade/upgrade-guides/upgrade-v2-to-v3) — relevant to existing v2 API boundaries only; no migration is planned.
- [Langfuse Codex integration](https://langfuse.com/integrations/developer-tools/codex) — deferred client.
- [Langfuse OpenCode integration](https://langfuse.com/integrations/developer-tools/opencode) — deferred client/privacy constraint.
