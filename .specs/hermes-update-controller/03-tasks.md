# Hermes Safe Update Controller — Phase 3 Tasks

**Status:** Approved implementation checklist; T01 is functionally verified with its work-unit commit pending; T02–T04 are pending.
**Parent design:** [02-design.md](02-design.md), approved by the user with “Aprobado” on 2026-10-28.
**Scope:** Monitoring/reporting only. Do not implement scheduler changes or protected prepare, backup, rehearse, activate, update, restart, or recovery operations.

## Objective and acceptance

Implement the approved standalone standard-library watcher that discovers official stable Hermes releases, records immutable secret-free reports and an auditable delivery outbox, and provides a tightly bounded CLI with a receipt-validating `ncl-discord` transport seam. A release alert is evidence only, never compatibility, safety, consent, or update authorization.

Acceptance is the approved design’s contract, especially AC-01 through AC-08 and AC-16. AC-09 and AC-13 remain advisory/future-operation blockers only; AC-10, AC-11, and AC-15 are explicitly unsupported in this milestone; AC-12 and AC-14 remain unknown/blocking rather than inferred passes. No task may claim a future protected operation is implemented or safe.

## Constraints and scope boundary

- No new dependency or binary. Use the existing Python standard library and the existing project runner.
- No real GitHub requests, Discord sends/reads, secret access, SSH/remote work, checkout mutation, scheduler changes, deployment writes, service operations, backup, build, or install in tests or implementation verification.
- The test suite uses deterministic HTTP/subprocess seams, fake evidence and transport clients, and temporary directories. Never write to `~/.hermes` or live operational state.
- Persisted report/state paths must be explicit test seams and must reject checkout paths; operational owner/path and send destination/profile remain separate installation/operation gates.
- Follow the approved public functions, typed result boundary, report/outbox schemas, stable reason codes, bounded limits, and no-retry behavior in `02-design.md`. No generic framework or Hermes runtime import.
- Keep all checklist items unchecked until the outcome and its required verification have been observed. Do not mark runner/bootstrap, native review, or operational gates as passed without evidence.

## Approved file map and task sequence

The implementation is planned around the design’s package boundary and one behavior-contract test file:

- `scripts/hermes-update-watch.py` — executable entry point.
- `scripts/hermes_update_watch/__init__.py` — package boundary/public exports.
- `scripts/hermes_update_watch/model.py` — typed config, release, report and result values shared across modules.
- `scripts/hermes_update_watch/releases.py` — fixed-host GitHub API reader, stable filtering, bounded tag resolution and candidate selection.
- `scripts/hermes_update_watch/report.py` — environment evidence representation, secret-free report creation/integrity and fixed prompt/message rendering.
- `scripts/hermes_update_watch/state.py` — locked atomic state/report persistence and delivery outbox transitions.
- `scripts/hermes_update_watch/transport.py` — bounded, typed subprocess adapter for `ncl-discord`; no credential or direct HTTP handling.
- `scripts/hermes_update_watch/cli.py` — thin CLI and orchestration for inspect/watch/deliver; no protected verbs.
- `tests/scripts/test_hermes_update_watch.py` — behavior-contract tests for the public module surface and CLI seams.

Tasks are sequential because later layers consume the prior public contracts. Task implementation route is **delegated direct**: each task changes multiple non-trivial source/test files and reading prepares the write. Use one writer at a time; no parallel writers.

### T01 — Discover and verify stable release identities

- [x] Add typed release/result/config/client boundary and the fixed-host, anonymous GitHub release reader.
- [x] Enforce HTTPS, reject all redirects before following them (including same-host redirects), validate same-host pagination links, apply response/request budgets, bound page/tag traversal, parse strict stable tags, allowlist response fields, and verify immutable tag-to-commit identities.
- [x] Implement cold-start/new-release selection, bounded oldest-first catch-up, pending overflow, republished-identical handling, and moved-tag/release identity blockers. No raw upstream title/body/response text may escape as report data.
- [x] Write behavior tests first: stable vs prerelease filtering, direct and annotated tag resolution, moved/mismatched/cyclic/unsupported refs, malformed/oversized/non-JSON/network/rate-limit responses, pagination cap, cold start and candidate bounds. Network must be fully faked.
- **Depends on:** none.
- **Allowed edit surfaces:**
  - `scripts/hermes_update_watch/__init__.py`
  - `scripts/hermes_update_watch/model.py`
  - `scripts/hermes_update_watch/releases.py`
  - `tests/scripts/test_hermes_update_watch.py`
- **Applicable skills:** `.skills/hermes-agent/SKILL.md`; `.skills/python-testing-patterns/SKILL.md`.
- **Test-first evidence:** Contract tests were added before implementation and the focused `-k release` selection was run; after correcting the verifier’s counterexamples, the guarded focused selection passed 17 tests and the full feature file passed 32 tests.
- **Verification command:** `env -u __HERMES_ACTIVATED HERMES_PYTHON=/usr/bin/python3 scripts/run_tests.sh tests/scripts/test_hermes_update_watch.py -k release`
- **Runtime harness:** Fake HTTP responses and exercise urllib’s redirect pipeline with a fake HTTPS handler; assert no redirect (even same-host) produces a second physical request. No real HTTP or remote runtime.
- **Acceptance trace:** AC-01, AC-02, AC-03, AC-05, AC-16 (discovery bounds only).

### T02 — Produce secret-free evidence, reports, and bounded prompt

- [ ] Add read-only environment evidence collection limited to the design’s fixed DEV Git commands and explicit field allowlist; PROD remains unknown, and no effective config, secrets, user data, or arbitrary command is inspected.
- [ ] Build the versioned report from validated release identity and evidence, marking uncollected categories unknown/blocking; canonicalize and verify its integrity digest and byte bound.
- [ ] Render only the fixed prompt and validated report metadata. Do not interpolate upstream titles, notes, arbitrary URLs, local errors, or filenames; enforce the full-message UTF-16-unit and attachment byte limits without truncation.
- [ ] Write behavior tests first: unknown DEV/PROD evidence, hostile/untrusted upstream fields excluded, valid digest/readback, fixed prompt prohibitions and no-authority text, stale times, and size-bound rejection. Use fake subprocesses and deterministic time/UUID seams where needed.
- **Depends on:** T01.
- **Allowed edit surfaces:**
  - `scripts/hermes_update_watch/model.py`
  - `scripts/hermes_update_watch/report.py`
  - `tests/scripts/test_hermes_update_watch.py`
- **Applicable skills:** `.skills/hermes-agent/SKILL.md`; `.skills/python-testing-patterns/SKILL.md`.
- **Test-first evidence:** Add the report/evidence contract tests and observe them fail before implementation; then run the focused selection green.
- **Verification command:** `env -u __HERMES_ACTIVATED HERMES_PYTHON=/usr/bin/python3 scripts/run_tests.sh tests/scripts/test_hermes_update_watch.py -k 'report or prompt or evidence'`
- **Runtime harness:** Fake the fixed Git subprocess boundary; assert generated report JSON is secret-free and never touch a live checkout for test setup.
- **Acceptance trace:** AC-04, AC-05, AC-08, AC-09 (expiry is advisory in this milestone), AC-12, AC-14 (unknown/blocking behavior).

### T03 — Persist reports and reconcile the delivery outbox atomically

- [ ] Implement versioned local state and immutable report storage, same-directory temp write + flush/fsync + atomic replace + directory fsync, restrictive modes, symlink/owner/path validation, and the POSIX process lock.
- [ ] Persist discovery progress only after a complete validated scan and durable report/state writes; never import the legacy watermark or advance confirmed-delivery state from release discovery.
- [ ] Implement release/destination uniqueness, tag-to-SHA binding, pending/sending/confirmed/failed/ambiguous transitions, stale-sending recovery to ambiguous, 24-hour delivery expiry, and no automatic replay/ambiguous-send reconciliation.
- [ ] Write tests first with temporary state roots: corruption, wrong owner/mode/symlink/checkout path, lock contention, atomic-write failure, interrupted intent, duplicate identity, moved tag, disk/write failure, expiry, stale sending, and preservation of last confirmed state. Tests must not change live ownership or permissions.
- **Depends on:** T01 and T02.
- **Allowed edit surfaces:**
  - `scripts/hermes_update_watch/state.py`
  - `tests/scripts/test_hermes_update_watch.py`
- **Applicable skills:** `.skills/hermes-agent/SKILL.md`; `.skills/python-testing-patterns/SKILL.md`.
- **Test-first evidence:** Add state-transition and failure-injection tests and observe failure before implementation; then verify the focused selection passes.
- **Verification command:** `env -u __HERMES_ACTIVATED HERMES_PYTHON=/usr/bin/python3 scripts/run_tests.sh tests/scripts/test_hermes_update_watch.py -k 'state or outbox or lock or atomic or ambiguous'`
- **Runtime harness:** Temporary directories and injected failures only; do not write under the proposed operational state root or alter owner/mode outside test fixtures.
- **Acceptance trace:** AC-03, AC-06, AC-07, AC-16 (state, concurrency, and interruption behavior).

### T04 — Expose bounded CLI and receipt-validating Discord transport

- [ ] Add the thin executable and CLI orchestration for `inspect`, `watch`, and `deliver`, wired to the typed clients/store; reject unknown or future protected verbs with `unsupported_operation`.
- [ ] Implement the sole transport as `ncl-discord` argv with `shell=False`, explicit approved destination/profile configuration, fixed timeout/output bounds, and no retry. Do not include argv, message bodies, raw stdout/stderr, or credentials in output/logs.
- [ ] Confirm delivery only from a valid typed success receipt matching destination, exactly one message ID, timestamp, report attachment filename/size, stored hashes and digest; classify unknown/nonzero/malformed outcomes ambiguous except proven pre-invocation validation failure.
- [ ] Wire end-to-end tests through fake release/evidence/transport/store seams and CLI subprocess capture. Verify inspect has no writes/send, watch has no send, deliver requires a pre-existing unexpired report, duplicate/ambiguous sends are not invoked again, CLI output is bounded, and no unsupported action mutates anything. Never invoke real `ncl-discord`.
- **Depends on:** T01, T02, and T03.
- **Allowed edit surfaces:**
  - `scripts/hermes-update-watch.py`
  - `scripts/hermes_update_watch/__init__.py`
  - `scripts/hermes_update_watch/cli.py`
  - `scripts/hermes_update_watch/transport.py`
  - `tests/scripts/test_hermes_update_watch.py`
- **Applicable skills:** `.skills/hermes-agent/SKILL.md`; `.skills/python-testing-patterns/SKILL.md`.
- **Test-first evidence:** Add CLI/orchestration/transport contract tests and observe failure before implementation; then run focused and complete feature tests.
- **Verification command:** `env -u __HERMES_ACTIVATED HERMES_PYTHON=/usr/bin/python3 scripts/run_tests.sh tests/scripts/test_hermes_update_watch.py`
- **Runtime harness:** Inject a fake executable/transport and assert the exact argv contract without starting the real CLI. No send, read probe, target discovery, or secret access.
- **Acceptance trace:** AC-01, AC-06, AC-07, AC-08, AC-13 (no mutation command), AC-16.

## Feature-level verification and gates

- The exact final feature test is the T04 command above. It is expected to exercise deterministic fake seams only; it is not a deployment, GitHub smoke, Discord check, state-root installation, or scheduler test.
- Before running the project runner, verify that `/usr/bin/python3` still has the already-present pytest and that the runner will honor explicit `HERMES_PYTHON` without entering `scripts/run-in-hermes-env`. The runner source documents that behavior. If it would bootstrap/apply an environment or the interpreter lacks pytest, stop and report the exact blocker; do not install, build, or bypass the project runner with bare pytest.
- A previously observed native review authority/ownership problem at the live source repository is not permission to alter ownership, modes, switch state, or review state. Before source implementation, the parent must perform the required read-only RDD status and candidate assessment for this worktree. An unknown/failed assessment or owner/authority error is treated as high/unavailable; do not repair permissions, chown, toggle RDD, or substitute a non-native review path. Follow the parent’s native review gate and report any unavailable result honestly.
- At task closure, run applicable complete feature checks and parent-required native assessment/review. Parent owns the one review-boundary spot check and any escalation; no task checkbox or commit is itself approval.
- Real `ncl-discord` send, scheduler cutover, operational state-root ownership/path confirmation, PROD evidence, and all protected update/recovery work remain separately gated and out of this task checklist.

## Delivery plan and progress record

- **Route:** delegated direct, one writer per task. Trigger evidence: each task touches a behavior module plus the shared behavior-contract test file; task dependencies require sequential interfaces.
- **Review base:** isolated feature branch `feat/hermes-update-watch`, starting boundary `cd397afc64` (full revision to be read from the worktree before implementation/review). The live checkout’s unrelated dirty files remain outside scope.
- **Forecast:** T01 currently contains 1,478 authored source/test lines; revise the whole-feature forecast to approximately 2,000–2,600 authored changed lines (generated files excluded) based on T01’s observed size. Recount from work-unit diffs before commit rather than shrinking tests/docs to hit a budget.
- **Delivery strategy:** `feature-branch-chain`, explicitly chosen by the user with “Sí” on 2026-10-28. T01 is slice 1, a standalone reviewable work unit on the feature branch; T02, T03, and T04 are planned as subsequent reviewable slices chained off-main. No PR or push is authorized or planned.
- **Planned work units (not commits yet):** Slice 1 / T01 planned Conventional Commit: `feat(ops): verify official Hermes release identities`. The actual commit SHA is pending the parent’s commit. Slices 2–4 are T02, T03, and T04 respectively, each with its own code and tests. No commit has occurred yet.
- **Current progress:** T01 behavior and fake-only verification are complete; its four checklist items are checked, but its work-unit commit remains pending. T02–T04 remain unchecked and unstarted. No network request, operational send, install, or runtime change occurred. T01 contains 1,478 authored source/test lines; this is a coherent bounded HTTP client/identity-verification slice with adversarial regression tests, so it will not be artificially split or have tests removed to fit the approximate 400-line planning heuristic.
- **T01 TDD/verification evidence:** The original scoped behavioral REDs covered persisted `seen_not_notified`, pending overflow, redirect routing, malformed response URLs/read timeouts, and a bounded oversized version tag. The verifier’s counterexamples were added test-first: republished overflow suppression, malformed integer/deep-nesting JSON, timezone-underflow metadata, exact ref/tag-object identity, and external/same-host redirects using urllib’s real redirect flow over a fake HTTPS handler. That focused correction selection observed 8 failures and then passed 8/8. An additional non-latest pending-republication regression observed 1 failure and then passed with the related republishing tests (2/2). Final project-runner focused command (`-k release`) passed 17 tests; full feature file passed 32 tests (0 failed). The first pre-implementation run was only a collection error because the new package did not yet exist and is not counted as behavioral RED.
- **T01 bounded deviation:** The source rejects every HTTP redirect before a follow-up request, including redirects that remain on `api.github.com`; validated pagination links are separate new requests and remain accepted. This intentionally fails closed rather than attempting to account for urllib’s internal physical redirect hops within the per-run request budget.
- **Independent verification:** A separate verifier reproduced four introduced defects (pending republication, redirect request accounting, parser exceptions, mismatched tag references), then confirmed all four corrected with targeted counterexamples. Its guarded full-file runner exited 0 with 32 passed, 0 failed. Parent independently reran the same guarded full-file command: exit 0, 32 passed, 0 failed. These are functional checks, not a native review receipt. Native mode status was unavailable due Git authority ownership; candidate assessment returned high/unassessable for undeclared untracked paths. No permission or review-mode changes were made.
- **Next step:** Parent records the T01 work-unit commit and actual SHA; only then proceed to T02. T02 remains unstarted. The live checkout HEAD remains `cd397afc64c91e759d49c1db6418e4b7ab107d12`. Native review status failed before mutation because Git authority ownership was UID 10000 versus root; no receipt exists and no ownership, mode, or review-switch changes were made.

## Relevant files

- `01-spec.md` — approved business scope and acceptance criteria.
- `02-design.md` — approved architecture, contracts, safety bounds, and operational gates.
- `03-tasks.md` — this executable Phase 3 checklist and verification record.
