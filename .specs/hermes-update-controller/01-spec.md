# Hermes Safe Update Controller and Release Watch

**Status:** Phase 1 approved; Phase 2 design and monitoring/reporting implementation approved (2026-10-28).
**Scope:** DEV and PROD Hermes deployments, with monitoring/reporting delivered before any protected deployment capability
**Decision gate:** Phase 1 and Phase 2 approvals are recorded. Phase 3 implementation may proceed only for the approved monitoring/reporting scope and checklist; no separate task approval is required. Scheduler changes, real sends, remote access, production operations, and deployment mutations remain separately authorized.

## 1. Problem and Intent

Hermes upstream releases need a trustworthy, low-noise way to be noticed and evaluated without treating release availability as permission or proof that an update is safe. The existing `scripts/sync-upstream.sh` combines release discovery, a heuristic merge-tree check, Discord delivery, and a legacy apply path that can alter Git state, build a mutable image, restart services, and use an obsolete backup location. Its current cron invokes the check mode weekly. That script is evidence of the current integration, not an approved implementation plan or a safe controller.

The intended outcome is a staged update controller: first, a weekly watcher that reports verified official stable releases and supplies a bounded, ready-to-copy CLI prompt for human-led inspection; later, only after separate design and explicit operation-level authorization, protected preparation, rehearsal, activation, and recovery capabilities. The controller must preserve custom DEV/PROD behavior and must never turn a release alert, compatibility result, script flag, or generated prompt into deployment authorization.

### User stories

- As the Hermes operator, I want one deduplicated weekly alert when a new official stable release is available, with evidence and a useful report, so I can decide whether further evaluation is worthwhile.
- As the operator, I want the alert to include a bounded prompt I can copy into the CLI to revalidate facts and produce an inspection/plan, so the next step is explicit without silently changing a system.
- As the operator, I want any future update operation to preserve customized code, configuration, profile data, secrets, active sessions, and external integrations, and to stop safely when recovery cannot be demonstrated.
- As a maintainer, I want release detection, assessment, preparation, activation, and recovery to be distinct states with explicit gates, so a successful check cannot be mistaken for a safe update or permission to deploy.

## 2. Desired Outcomes and Scope

### Initial monitoring/reporting milestone

- Detect newly published releases from the official Hermes upstream source on a weekly schedule, considering stable releases only. Do not select prereleases, moving branches, or arbitrary tags as the update target.
- Verify release identity against the official source and an immutable commit identity. Detect moved/replaced tags or ambiguous release metadata and report a verification blocker instead of treating the release as trusted.
- Produce a structured, reviewable report that separates observed facts, compatibility signals, unknowns, and blockers. Show the checked-at time, report identity, release tag and commit, source links, environment identity/baseline evidence, and freshness/expiry policy once defined in design.
- Send a concise alert with a link or reference to the full report and an embedded ready-to-copy bounded CLI prompt. Delivery failure or ambiguity must not be reported as success or cause unbounded duplicate alerts.
- Treat upstream text (release titles, notes, links, filenames, and metadata) as untrusted data, never as instructions or executable shell content.
- Keep this milestone observational: it may not fetch into or alter a live deployment checkout, merge/check out code, build or replace deployment images, restart services, change schedules, mutate configuration/data, rotate secrets, or authorize any of those actions.

### Later protected-update milestones (not authorized by this specification alone)

1. Revalidate the release and current DEV/PROD baselines, then prepare an isolated candidate from exact, verified source and immutable build artifacts.
2. Capture and validate recoverable state, characterize customizations and effective configuration, rehearse the exact production artifact on DEV, and record explicit pass/fail evidence.
3. Require a separately approved, bounded activation window and target for production mutation; activate with controlled health checks and a tested recovery path.
4. Recover only when the recovery target and state are known, and never overwrite newer writes with an older snapshot.

Each later milestone requires its own approved design, tasks, and operation-specific user authorization. A weekly alert or generated prompt is not approval.

## 3. Domain Rules and Safety Invariants

1. **Availability is not safety or consent.** A newly published release means only that a release is available. It does not imply compatibility, readiness, urgency, or permission to update.
2. **Stable-only automatic discovery.** The watcher must not automatically nominate prereleases, release candidates, main-branch commits, or locally inferred versions. If stable publication cannot be verified, classify the result as unknown/blocked.
3. **Evidence over heuristics.** A zero-conflict merge-tree result or passing subset of tests is not proof of compatibility, preserved behavior, complete backup, or safe rollback. Reports must name evidence and explicitly identify missing evidence.
4. **Unknown is a blocker, not a pass.** Network failure, rate limiting, incomplete release metadata, stale environment facts, failed checks, untested restore, unknown image provenance, unknown effective config, or uncertain notification delivery must never be presented as success or “no update.”
5. **Preserve the actual deployment, not an assumed upstream default.** Preserve custom source changes, runtime overrides and mounts, effective config including profile overrides, durable data, sessions, enabled plugins, skills, and external integrations. A source-only diff cannot establish that those are preserved.
6. **No lossless-backup claim without a consistent capture boundary.** Before any future activation, all relevant writers and ingress must be safely quiesced or captured consistently, all required data and keys must be included, and restore/decryptability must be exercised in isolation. If this cannot be demonstrated, stop before mutation.
7. **No stale-state rollback.** Recovery must account for schema/session compatibility, external side effects, and writes made after activation. An older snapshot must not silently overwrite newer state. Restore rehearsal must not contact production services, start duplicate bots, or replay jobs.
8. **Build provenance is part of the candidate.** Future activation must use the exact rehearsed immutable artifact, not a mutable tag or an uncharacterized “latest” image. Unknown source provenance blocks any claim that rehearsal represents the installed deployment.
9. **Secrets stay outside source, Markdown, reports, logs, and stdout.** Collectors may emit secret-free metadata only. No token, credential, raw environment dump, session key, or private secret path/content may enter the report or generated prompt.
10. **The generated prompt is bounded and non-authorizing.** It may request read-only revalidation, inspection, and a plan only. It must forbid fetching/mutating a live checkout, creating a backup, building, restarting, or applying changes based solely on the alert. Any later mutation requires fresh target/baseline validation and explicit, separate scope authorization.
11. **Freshness is mandatory.** Before future preparation or activation, revalidate release identity, installed baselines, working-tree/config/data drift, and report validity. A stale report or any intervening drift invalidates it; do not infer continued approval.
12. **No hidden side effects in checks.** A monitoring/check action may read only approved metadata and the official release source; it must not inherit side effects of legacy “check” paths such as live checkout fetches, chat posting without deduplication controls, or state writes that mask delivery failure.
13. **Human-owned delivery and infrastructure.** No push, production mutation, schedule change, new service, secret rotation, dependency/binary addition, or destructive recovery is authorized by this spec. New dependencies/binaries require explicit approval and an exact pinned version.

## 4. Report and Prompt Contract

The full report must distinguish:

- **Observed release facts:** official source, stable tag, immutable commit, publication/check timestamps, and source links.
- **Observed environment facts:** target identity (DEV or PROD), installed source/build identity and provenance, runtime/image identity where available, effective-configuration evidence, customization/drift summary, and data/backup capability evidence. Missing facts are `unknown`, not inferred.
- **Assessment:** compatibility/test/rehearsal signals only when supported by actual evidence, with scope and limitations. A release being behind is not itself a safety assessment.
- **Blockers and next permitted action:** why evaluation or a later gated operation cannot proceed; no release-title/changelog instructions are carried as commands.
- **Report identity and validity:** stable report ID, observation time, freshness/expiry rules, and a clear invalidation condition for changed release or environment state. Exact identifiers and retention are design decisions.

The concise alert must link/reference the full report and include the ready-to-copy prompt. The prompt must:

1. Treat the report and all upstream content as untrusted evidence, not authority.
2. Re-fetch/revalidate the official stable release identity and current selected-environment facts using read-only methods before drawing conclusions.
3. Return an inspection and bounded proposal with verified facts, unknowns, risks, and explicit decision points; do not perform deployment mutation.
4. Reject stale reports, changed tags/commits, changed environment baselines, missing evidence, or ambiguous target selection as blockers.
5. State that any DEV or PROD mutation requires a fresh explicit authorization naming the exact target, operation, and scope; the prompt itself grants none.

Report wording must avoid claims such as “safe,” “clean,” “compatible,” “backup succeeded,” or “rollback guaranteed” unless the named evidence actually proves the specific claim. A missing or unexercised recovery path is an explicit blocker for activation.

## 5. Applicable Project Skills

- `.skills/hermes-agent/SKILL.md` — `/opt/hermes-agent/.agents/skills/hermes-agent/SKILL.md`
- `.skills/python-testing-patterns/SKILL.md` — `/opt/hermes-agent/.agents/skills/python-testing-patterns/SKILL.md`
- `cognitive-doc-design` — `/root/.agents/skills/cognitive-doc-design/SKILL.md`

These are Phase 1 scope-relevant skills. The design/task phases must rescan the local skill registry and assign implementation-specific skills to each task.

## 6. Explicit Non-Goals

- No immediate update, deployment, production access, service restart, repository checkout/fetch/merge, image build, or data restore.
- No use or repair of the current legacy `--apply` behavior as an assumed safe path.
- No cron or schedule modification in this phase; weekly cadence is a desired behavior to design and approve later.
- No automatic adoption of upstream defaults or deletion/normalization of local customizations.
- No secret access, rotation, copying, or reporting; no raw environment, transcript, database, or session-store inspection for this specification.
- No new dependency, binary, service, webhook, notification channel, or external integration without a separate approved decision.
- No push, commit, branch/worktree cleanup, reset, stash, or unrelated cleanup.
- No design, executable task checklist, or source implementation before the Phase 1 approval gate.

## 7. Acceptance Criteria

| ID | Given | When | Then |
|---|---|---|---|
| AC-01 | An official stable release is verifiably published and differs from the last successfully reported stable release | The scheduled watcher evaluates releases | It records a report for the immutable release identity and sends one concise alert referencing that report and its bounded prompt. |
| AC-02 | Only prereleases, a moving branch, or unverified/moved tag metadata are available | The watcher evaluates upstream | It does not nominate them as an update; it reports unknown/blocked verification and includes no apply instruction. |
| AC-03 | The official release source is unavailable, rate-limited, or returns incomplete data | A scheduled check runs | The outcome is visibly unavailable/blocked, not “no update” or success; the prior successful watermark is preserved. |
| AC-04 | A candidate report lacks installed build provenance, effective config, customization/drift evidence, or another required fact | The report is produced | Each missing fact is marked unknown and relevant future operations are blocked; no compatibility or safety claim is inferred. |
| AC-05 | An upstream title, note, or URL contains instruction-like or shell-like text | The report and prompt are rendered | Content remains escaped data; no shell command or instruction is generated from that content. |
| AC-06 | The watcher finds the same release again, including after a retry | Alert delivery is evaluated | It does not create repeated alerts; deduplication state advances only after delivery is confirmed, and ambiguous delivery is surfaced without blind retry/spam. |
| AC-07 | Notification delivery fails or times out with unknown outcome | The watcher finishes | It records delivery as failed/ambiguous, preserves evidence needed for reconciliation, and does not claim notification success. |
| AC-08 | An alert contains its ready-to-copy CLI prompt | An operator uses the prompt | The prompt authorizes only fresh read-only validation, inspection, and planning; it cannot authorize update, backup, build, activation, restart, or recovery. |
| AC-09 | A previously valid report is stale or the environment/release has drifted | A later protected operation is requested | The report cannot be reused as authority; fresh validation is required and detected drift blocks until reassessed. |
| AC-10 | A future activation proposal cannot prove complete consistent capture and isolated restore, or cannot rehearse the exact immutable production artifact on DEV | Activation readiness is evaluated | Activation is blocked; no placeholder, skipped step, or “best effort” result is represented as passing. |
| AC-11 | A recovery would restore an older state after newer writes or external side effects may have occurred | Recovery readiness is evaluated | The controller stops for a bounded human decision and never blindly overwrites newer state or replays external effects. |
| AC-12 | The installed deployment includes custom source, config/profile overrides, mounted runtime overrides, plugins, skills, persistent sessions, or external integrations | A future candidate is assessed | The report/proposal explicitly accounts for each applicable category or identifies it as unknown/blocking; upstream defaults are not silently substituted. |
| AC-13 | The target, operation, or authorization is absent, ambiguous, expired, or broader than the explicitly approved scope | Any future mutation is requested | No mutation occurs; authorization is not inferred from alert, report, schedule, generated text, or earlier approval. |
| AC-14 | A new default changes an omitted setting, a migration removes/renames a key, or a required plugin becomes incompatible | A candidate is assessed for each affected profile | Compare effective behavior with the baseline, disclose the semantic change, and block activation until its preservation or explicitly approved replacement is demonstrated; unchanged YAML alone is not sufficient. |
| AC-15 | State is copied for preparation, migration tests, or recovery rehearsal | The isolated environment is started | It has no writable hardlinks to live state and cannot use live identities, deliver external messages, or execute production jobs; preserve necessary link relationships within the isolated recovery set only. |
| AC-16 | Concurrent checks, preparation attempts, or partial interrupted operations occur | An operation attempts to proceed | Prevent competing mutation of the same target, preserve the last confirmed evidence, and require observed state reconciliation rather than blindly replaying side effects. |

## 8. Known Failure Modes and Edge Cases

- Upstream tag moved after initial observation, tag and release page disagree, or a stable release lacks an immutable source identity.
- Release API/network outage, rate limit, partial pagination, clock skew, or stale/duplicate schedule execution.
- New release exists but local version identity cannot be trusted, or DEV and PROD have different images/source/custom patches.
- Git history similarity or mergeability is mistaken for runtime compatibility; a test subset passes while profile-specific behavior is untested.
- Untracked/ignored files, mounted overrides, runtime-generated state, hardlinks, active writers, external databases, or secrets are omitted from a proposed snapshot.
- Snapshot exists but cannot be decrypted/read/restored; keys are unavailable; backup is inconsistent; storage is full; or verification accidentally contacts external services.
- Restore appears healthy but replays a scheduled job, duplicates a bot/session, loses post-snapshot writes, breaks schema compatibility, or repeats an irreversible external action.
- Notification accepted but response times out, dedupe storage fails, report link is unavailable, or a retry could duplicate delivery.
- Upstream notes or release names contain Markdown/HTML/shell injection, malicious links, or persuasive but unverified claims.
- Working tree is dirty or contains user changes; any future preparation must preserve exact bytes/modes and stop rather than discard, overwrite, or silently commit them.

## 9. Proposed Milestone Sequence (Not an Approved Task Checklist)

1. Design and approve the release-source, report, freshness, secret-free evidence, and deduplicated notification contract for monitoring-only delivery.
2. Implement and verify monitoring/reporting and prompt generation without deployment side effects; approve any scheduler/notification integration separately.
3. Design and approve isolated preparation, customization/config inventory, consistent backup, restore rehearsal, and exact-artifact DEV validation.
4. Design and approve explicit activation, health evidence, drift checks, and stale-write-aware recovery gates for a named environment.
5. Implement each approved unit with its own verification and authorization boundaries; production mutation remains separately approved at execution time.

## 10. Evidence and Verification Boundary

Current-state references inspected read-only for this draft:

- `scripts/sync-upstream.sh:97-140` shows the existing check path fetches tags into the deployment checkout, uses merge-tree as a conflict heuristic, posts a Discord alert, and advances a notification watermark.
- `scripts/sync-upstream.sh:144-219` shows the legacy apply path's dirty-tree gate, legacy backup location, partial guardrail test set, branch/merge-to-main flow, image build, service restart, and success claim. These lines are not an approved safety contract.
- `/etc/cron.d/hermes-sync:1-5` shows the current Monday schedule invokes that check script; the schedule is to be left unchanged in this phase.
- `ARCHITECTURE.md` documents preservation-sensitive WhatsApp session and shared-gateway invariants. Current installed deployment details must be revalidated in design; this specification does not treat historical documentation as current runtime proof.
- `PROJECT_MEMORY.md` contains historical audit/deployment handovers and known earlier findings. They are context only, not current baseline evidence or proof of backup/restore readiness.

Specification-only validation: this document states the user problem and outcomes, explicit non-goals, testable Given/When/Then criteria, failure modes, applicable skills, and a sign-off gate. No implementation tests, builds, deployment checks, release lookups, notifications, or operational changes were run or authorized.

## 11. Phase 1 Decision

**Decision:** Phase 1 was approved for Phase 2 design only. The user explicitly replied **“Aprobado”** on 2026-10-28 to that approval request. At that point, design, implementation, scheduling, remote access, production operations, and deployment mutation were not approved; the separate Phase 2 approval and implementation scope are recorded in Section 12.

## 12. Phase 2 Approval and Implementation Authorization

The user explicitly approved the Phase 2 technical design with **“Aprobado”** on 2026-10-28 and authorized test-first implementation of the approved monitoring/reporting scope under `03-tasks.md`. This does not authorize scheduler cutover, a real Discord post, remote/PROD access, dependencies, or deployment operations.

## 13. User-Authorized Weekly Delivery Addendum (2026-10-28)

The user explicitly requested a weekly release notification to Jesus's Discord direct message, numeric destination `1493432785245962250`, using the `roshi` sender profile, while preserving the existing **Monday at 09:00 America/Bogota** cadence. This addendum authorizes implementation of a bounded weekly orchestration driver and safe recovery of pending delivery intents so an interrupted watch-to-send run can resume on the next scheduled invocation.

The weekly driver must run a complete `watch` first and only then drain up to five never-attempted pending report IDs for that exact destination. It sends only through the existing receipt-validating `ncl-discord` CLI and the explicitly authorized `roshi` profile. It must not retry `sending`, `ambiguous`, `confirmed`, or `failed_no_send` records, reset state, continue after an incomplete scan or a delivery failure, accept arbitrary destinations/profiles, or invoke any deployment/update/recovery action. Crash recovery is limited to pending, never-attempted reports.

This implementation task does not itself edit cron, install the immutable release, create/change the operational state root, perform an actual Discord send, access PROD/SSH, or mutate a deployment. The parent owns separately controlled installation and replacement of the existing weekly legacy job after verification; both senders must not remain enabled together.
