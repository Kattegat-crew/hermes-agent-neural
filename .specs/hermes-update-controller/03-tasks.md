# Hermes Safe Update Controller — Phase 3 Tasks

**Status:** Monitoring implementation T01–T04 functionally verified; T04 ready for local slice commit. Operational activation and protected update/recovery stages remain out of scope.
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

The implementation follows the design’s package boundary. Contract tests are split by task so later suites remain focused and below the repository’s per-file test-size guidance:

- `scripts/hermes-update-watch.py` — executable entry point.
- `scripts/hermes_update_watch/__init__.py` — package boundary/public exports.
- `scripts/hermes_update_watch/model.py` — typed config, release, report and result values shared across modules.
- `scripts/hermes_update_watch/releases.py` — fixed-host GitHub API reader, stable filtering, bounded tag resolution and candidate selection.
- `scripts/hermes_update_watch/process.py` — shared bounded shell-free subprocess execution with concurrent capped pipe reads and deadline enforcement.
- `scripts/hermes_update_watch/report.py` — environment evidence representation, secret-free report creation/integrity and fixed prompt/message rendering.
- `scripts/hermes_update_watch/state.py` — locked atomic state/report persistence and delivery outbox transitions.
- `scripts/hermes_update_watch/transport.py` — bounded, typed subprocess adapter for `ncl-discord`; no credential or direct HTTP handling.
- `scripts/hermes_update_watch/cli.py` — thin CLI and orchestration for inspect/watch/deliver; no protected verbs.
- `tests/scripts/test_hermes_update_watch.py` — release discovery/identity contract tests.
- `tests/scripts/test_hermes_update_watch_report.py` — T02 process/evidence/report/prompt contract tests.
- `tests/scripts/test_hermes_update_watch_state.py` — planned T03 state/outbox contract tests.
- `tests/scripts/test_hermes_update_watch_cli.py` — planned T04 CLI/transport contract tests.

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

- [x] Add read-only environment evidence collection limited to the design’s fixed DEV Git commands and explicit field allowlist; PROD remains unknown, and no effective config, secrets, user data, or arbitrary command is inspected.
- [x] Build the versioned report from validated release identity and evidence, marking uncollected categories unknown/blocking; canonicalize and verify its integrity digest and byte bound.
- [x] Render only the fixed prompt and validated report metadata. Do not interpolate upstream titles, notes, arbitrary URLs, local errors, or filenames; enforce the full-message UTF-16-unit and attachment byte limits without truncation.
- [x] Write behavior tests first: unknown DEV/PROD evidence, hostile/untrusted upstream fields excluded, valid digest/readback, fixed prompt prohibitions and no-authority text, stale times, and size-bound rejection. Use fake subprocesses and deterministic time/UUID seams where needed.
- **Depends on:** T01.
- **Allowed edit surfaces:**
  - `scripts/hermes_update_watch/model.py`
  - `scripts/hermes_update_watch/process.py`
  - `scripts/hermes_update_watch/report.py`
  - `tests/scripts/test_hermes_update_watch_report.py`
- **Applicable skills:** `.skills/hermes-agent/SKILL.md`; `.skills/python-patterns/SKILL.md`; `.skills/python-testing-patterns/SKILL.md`.
- **Test-first evidence:** RED: the report file ran 8 tests and failed all 8 against the missing T02 report/process API (no collection error). GREEN: the report file passed 13 tests after two review corrections; the combined T01 release and T02 report files passed 45 tests, 0 failed. Initial RED was 8 missing-API behavior failures; review-correction RED was 2 counterexample failures.
- **Verification command:** `env -u __HERMES_ACTIVATED HERMES_PYTHON=/usr/bin/python3 scripts/run_tests.sh tests/scripts/test_hermes_update_watch_report.py`; combined regression: `env -u __HERMES_ACTIVATED HERMES_PYTHON=/usr/bin/python3 scripts/run_tests.sh tests/scripts/test_hermes_update_watch.py tests/scripts/test_hermes_update_watch_report.py`
- **Runtime harness:** Fake the fixed Git subprocess boundary; assert generated report JSON is secret-free and never touch a live checkout for test setup.
- **Acceptance trace:** AC-04, AC-05, AC-08, AC-09 (expiry is advisory in this milestone), AC-12, AC-14 (unknown/blocking behavior).

### T03 — Persist reports and reconcile the delivery outbox atomically

- [x] Implement versioned local state and immutable report storage, same-directory temp write + flush/fsync + atomic replace + directory fsync, restrictive modes, symlink/owner/path validation, and the POSIX process lock.
- [x] Persist discovery progress only after a complete validated scan and durable report/state writes; never import the legacy watermark or advance confirmed-delivery state from release discovery.
- [x] Implement release/destination uniqueness, tag-to-SHA binding, pending/sending/confirmed/failed/ambiguous transitions, stale-sending recovery to ambiguous, 24-hour delivery expiry, and no automatic replay/ambiguous-send reconciliation.
- [x] Write tests first with temporary state roots: corruption, wrong owner/mode/symlink/checkout path, lock contention, atomic-write failure, interrupted intent, duplicate identity, moved tag, disk/write failure, expiry, stale sending, and preservation of last confirmed state. Tests must not change live ownership or permissions.
- **Depends on:** T01 and T02.
- **Allowed edit surfaces:**
  - `scripts/hermes_update_watch/state.py`
  - `tests/scripts/test_hermes_update_watch_state.py`
- **Applicable skills:** `.skills/hermes-agent/SKILL.md`; `.skills/python-testing-patterns/SKILL.md`.
- **Test-first evidence:** Add state-transition and failure-injection tests and observe failure before implementation; then verify the focused selection passes.
- **Verification command:** `env -u __HERMES_ACTIVATED HERMES_PYTHON=/usr/bin/python3 scripts/run_tests.sh tests/scripts/test_hermes_update_watch_state.py`; combined regression: `env -u __HERMES_ACTIVATED HERMES_PYTHON=/usr/bin/python3 scripts/run_tests.sh tests/scripts/test_hermes_update_watch.py tests/scripts/test_hermes_update_watch_report.py tests/scripts/test_hermes_update_watch_state.py`
- **Runtime harness:** Tests are isolated to temporary roots and fake discovery/report values; a child process tests real POSIX flock contention. No live checkout or operational state path is touched.
- **Runtime harness:** Temporary directories and injected failures only; do not write under the proposed operational state root or alter owner/mode outside test fixtures.
- **Acceptance trace:** AC-03, AC-06, AC-07, AC-16 (state, concurrency, and interruption behavior).

### T04 — Expose bounded CLI and receipt-validating Discord transport

- [x] Add the thin executable and CLI orchestration for `inspect`, `watch`, and `deliver`, wired to the typed clients/store; reject unknown or future protected verbs with `unsupported_operation`.
- [x] Implement the sole transport as `ncl-discord` argv with `shell=False`, explicit approved destination/profile configuration, fixed timeout/output bounds, and no retry. Do not include argv, message bodies, raw stdout/stderr, or credentials in output/logs.
- [x] Confirm delivery only from a valid typed success receipt matching destination, exactly one message ID, timestamp, report attachment filename/size, stored hashes and digest; classify unknown/nonzero/malformed outcomes ambiguous except proven pre-invocation validation failure.
- [x] Wire end-to-end tests through fake release/evidence/transport/store seams and CLI subprocess capture. Verify inspect has no writes/send, watch has no send, deliver requires a pre-existing unexpired report, duplicate/ambiguous sends are not invoked again, CLI output is bounded, and no unsupported action mutates anything. Never invoke real `ncl-discord`.
- **Depends on:** T01, T02, and T03.
- **Allowed edit surfaces:**
  - `scripts/hermes-update-watch.py`
  - `scripts/hermes_update_watch/__init__.py`
  - `scripts/hermes_update_watch/model.py`
  - `scripts/hermes_update_watch/state.py`
  - `scripts/hermes_update_watch/process.py`
  - `scripts/hermes_update_watch/cli.py`
  - `scripts/hermes_update_watch/transport.py`
  - `tests/scripts/test_hermes_update_watch_cli.py`
  - `docs/operations/hermes-update-watch.md`
  - `PROJECT_MEMORY.md`
  - `ARCHITECTURE.md`
  - `.specs/hermes-update-controller/02-design.md`
  - `.specs/hermes-update-controller/03-tasks.md`
- **Applicable skills:** `.skills/hermes-agent/SKILL.md`; `.skills/python-patterns/SKILL.md`; `.skills/python-testing-patterns/SKILL.md`; TDD skill; `.agents/skills/cognitive-doc-design/SKILL.md`.
- **Test-first evidence:** Add CLI/orchestration/transport contract tests and observe failure before implementation; then run focused and complete feature tests.
- **Verification command:** `env -u __HERMES_ACTIVATED HERMES_PYTHON=/usr/bin/python3 scripts/run_tests.sh tests/scripts/test_hermes_update_watch.py tests/scripts/test_hermes_update_watch_report.py tests/scripts/test_hermes_update_watch_state.py tests/scripts/test_hermes_update_watch_cli.py`
- **Runtime harness:** Inject a fake executable/transport and assert the exact argv contract without starting the real CLI. No send, read probe, target discovery, or secret access.
- **Acceptance trace:** AC-01, AC-06, AC-07, AC-08, AC-13 (no mutation command), AC-16.

## T04 implementation progress (2026-10-28)

- Implemented the explicit `inspect`, `watch`, and `deliver` CLI, protected unknown-operation handling, lazy injectable discovery/evidence/store/transport dependencies, bounded JSON summaries, and nonzero failure classifications. `watch` commits only complete discovery and never sends. `deliver` requires a report already in the explicit state root, an unexpired report, numeric destination, approved profile, and the exact `SEND <report-id> TO <target> AS <profile>` confirmation; the store lock spans intent, transport, and receipt. No scheduler, installation, real target authorization, PROD/SSH, or operation outside the bounded monitoring/reporting workflow was added.
- The only transport uses `/usr/local/bin/ncl-discord` with shell disabled, fixed profile/destination argument shapes, sanitized environment, 40-second timeout, stdout/stderr caps of 16/4 KiB, and no retries. `SendIntent.attachment_bytes` is validated and copied into a sealed anonymous Linux memfd passed via `pass_fds`; the adapter never resolves or reopens the report pathname. It validates the numeric physical descriptor filename and size in the receipt, then records the already-validated logical UUID filename. Missing memfd/procfs support is a pre-invocation failure; any uncertain post-invocation outcome is ambiguous and never replayed automatically.
- New T04 contract tests are isolated in `tests/scripts/test_hermes_update_watch_cli.py`; a deterministic procfs-unavailable regression observed RED (1 failed, expected `snapshot_unavailable`, actual runner invocation) before the adapter check, then GREEN (1 passed). A transport-factory exception regression also observed RED (1 failed, incorrectly classified `ambiguous`) then GREEN (1 passed) after it was classified as provably pre-invocation `failed_no_send`. A real local child-process invocation of the script exposed a RED import-path failure when launched outside the repository root; the entrypoint now adds its own `scripts/` directory before importing and the child test passes. Keep T04 unchecked pending independent verification and the parent-owned slice-4 commit.
- The operational runbook describes commands only; it does not install the tool, authorize a destination/profile, create a production state root, configure a scheduler, send a message, or enable update operations. Native review is unavailable from the previously observed Git ownership failure; no native receipt or approval is claimed.
- **Writer verification:** `env -u __HERMES_ACTIVATED HERMES_PYTHON=/usr/bin/python3 scripts/run_tests.sh tests/scripts/test_hermes_update_watch.py tests/scripts/test_hermes_update_watch_report.py tests/scripts/test_hermes_update_watch_state.py tests/scripts/test_hermes_update_watch_cli.py` exited 0: 93 passed, 0 failed (32 release, 13 report, 27 state, 21 CLI). This is writer functional verification only; independent verification and parent-owned slice-4 commit remain pending. AST parse succeeded for 10 Python files; `git diff --check` passed. No real `ncl-discord` invocation was made.
- **Bounded independent-review correction:** Added CLI regressions for expired pending renewal, no cursor/state advancement after incomplete identity revalidation, refusing a superseded report UUID before outbox mutation, and mapping actual `upstream_unavailable`/`upstream_rate_limited` codes to exit 3. The focused RED run showed 4 failures and 1 pass (the already-safe incomplete-scan case); after correction the same focused selection passed 5/5. Expiry refresh injects eligible IDs into the existing `discover_releases` pass, so the existing page/request/deadline/tag-resolution budgets remain in force; only pending rows with no attempt are eligible. The exact complete feature command then passed 98 tests (32 release, 13 report, 27 state, 26 CLI); `git diff --check` and AST parse of 10 Python files passed. This remains writer verification only; independent verification and parent-owned commit are pending.

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
- **Work-unit commits:** Slice 1 / T01: `874a1d1b61961124e91e9430a86a3b17efc8befe` — `feat(ops): verify official Hermes release identities`, 1,986 authored additions including the approved SDD documents and handover. Slices 2–4 are T02, T03, and T04 respectively, each with its own code and tests. No push or PR occurred.
- **Current progress:** T01–T03 are committed and functionally verified; their checklist items are checked. T04 is the active slice and remains unchecked pending independent verification and parent-owned commit. No live Git command, network request, operational send, secret read, install, or runtime change occurred. T01 contains 1,478 authored source/test lines and remains one coherent bounded HTTP client slice; it was not split artificially.
- **T01 TDD/verification evidence:** The original scoped behavioral REDs covered persisted `seen_not_notified`, pending overflow, redirect routing, malformed response URLs/read timeouts, and a bounded oversized version tag. The verifier’s counterexamples were added test-first: republished overflow suppression, malformed integer/deep-nesting JSON, timezone-underflow metadata, exact ref/tag-object identity, and external/same-host redirects using urllib’s real redirect flow over a fake HTTPS handler. That focused correction selection observed 8 failures and then passed 8/8. An additional non-latest pending-republication regression observed 1 failure and then passed with the related republishing tests (2/2). Final project-runner focused command (`-k release`) passed 17 tests; full feature file passed 32 tests (0 failed). The first pre-implementation run was only a collection error because the new package did not yet exist and is not counted as behavioral RED.
- **T01 bounded deviation:** The source rejects every HTTP redirect before a follow-up request, including redirects that remain on `api.github.com`; validated pagination links are separate new requests and remain accepted. This intentionally fails closed rather than attempting to account for urllib’s internal physical redirect hops within the per-run request budget.
- **Independent verification:** A separate verifier reproduced four introduced defects (pending republication, redirect request accounting, parser exceptions, mismatched tag references), then confirmed all four corrected with targeted counterexamples. Its guarded full-file runner exited 0 with 32 passed, 0 failed. Parent independently reran the same guarded full-file command: exit 0, 32 passed, 0 failed. These are functional checks, not a native review receipt. Native mode status was unavailable due Git authority ownership; candidate assessment returned high/unassessable for undeclared untracked paths. No permission or review-mode changes were made.
- **T01 closure:** Functionally verified and committed as `874a1d1b61961124e91e9430a86a3b17efc8befe`. After normalization, the guarded runner passed 32/32 again. Committed-only assessment against `cd397afc64` reported high risk (`hot_path: update`); its exact returned STATUS invocation failed safely before native mutation due UID 10000 versus root ownership. Native review is unavailable, not approved; independent functional verification remains the observed evidence. The native reviewed boundary has not advanced.
- **T02 progress:** TDD RED observed 8 failed tests (expected missing report/process behavior, no collection/environment error); GREEN report-file run passed 13 tests after the bounded review correction. Combined T01/T02 regression run passed 45 tests, 0 failed. T02 is verified and committed as `166412c5fde63a173225526def9cde98abe8025a`. Planned slice 2 commit: `feat(ops): generate bounded Hermes release reports`.
- **Historical T02 next-step note (superseded):** At that point, the next task was independent T03 verification and parent commit. T02 is closed as `166412c5fde63a173225526def9cde98abe8025a`, with 45 passing tests including independent and parent verification. The live checkout HEAD remains `cd397afc64c91e759d49c1db6418e4b7ab107d12`; no ownership, mode, or review-switch changes were made.

## Relevant files

- `01-spec.md` — approved business scope and acceptance criteria.
- `02-design.md` — approved architecture, contracts, safety bounds, and operational gates.
- `03-tasks.md` — this executable Phase 3 checklist and verification record.


## T02 Handover (2026-10-28)
- Implemented bounded standard-library subprocess reads with concurrent stdout/stderr selectors, 5-second caller deadline, immediate cap failure, child termination/reap, shell disabled, and stdin from `/dev/null`.
- Evidence collection uses only two fixed local Git argv forms and a fixed sanitized environment through the injectable process runner. It emits a source SHA/dirty count only after strict parsing; filenames and subprocess output never enter report evidence. All PROD and uncollected DEV categories stay unknown with stable reasons.
- Reports validate release identity fields, UTC timestamps, UUIDv4, exact nested allowlists/types, 24-hour expiry, canonical digest, fixed prompt, and 64 KiB cap. Alert rendering is fixed-text only and rejects above 1,900 UTF-16 units without truncation. Digest is integrity only, not authority.
- T02 tests are in `tests/scripts/test_hermes_update_watch_report.py`; T01’s release test file stays unchanged. RED was 8 expected missing-API failures; report GREEN was 13/13 after review correction; combined release/report GREEN was 45/45. No real Git command, API/network call, secret read, Discord invocation, or deployment operation was performed.
- Independent verifier found two bounded report defects: a re-signed report could claim a publication after `created_at`, and adding 24 hours at year 9999 leaked `OverflowError`. Test-first correction RED observed 2 failures, then both targeted regressions passed. Shared validation now checks publication ≤ creation even when digest is recomputed, and expiry overflow maps to sanitized `invalid_timestamp`. Full report tests pass 13/13 and combined T01/T02 tests pass 45/45.
- T02 is checked and committed after independent correction validation and parent verification. Planned slice 2 message: `feat(ops): generate bounded Hermes release reports`.

## T02 independent closure evidence

Writer and independent targeted verification both passed 45 combined tests (32 release, 13 report), with the parent spot check also exit 0 and 45 passed. Two independently demonstrated timestamp validation defects were corrected with observed RED/GREEN regressions. T02 is functionally verified; the parent records its commit identity after commit. Native authority remains unavailable; no native approval is claimed.

**Slice 2 commit:** `166412c5fde63a173225526def9cde98abe8025a` — `feat(ops): generate bounded Hermes release reports`; 1,046 additions / 26 deletions. Committed-only assessment reported high risk and the exact returned STATUS again failed safely before mutation due authority ownership. Native reviewed boundary remains unchanged; no native receipt is claimed.

## T03 Writer Handover (2026-10-28)
- Added `scripts/hermes_update_watch/state.py` as a root-scoped, fail-closed JSON store and outbox transaction API. Store construction/read are non-mutating; explicit initialization creates private files. State is capped at 8 MiB; reports remain immutable and capped by the report schema. State commits use same-directory exclusive temp files, fsync, atomic replacement, and directory fsync. POSIX `flock` spans the transaction, including a future send/result sequence.
- The store persists only complete validated discovery results, keeps discovery history and delivery states separate, deduplicates on release identity plus destination (not prompt template), blocks identity/tag rebinding, persists send intent before transport, confirms only from a typed receipt, and converts interrupted `sending` into `ambiguous` without replay. No retention/deletion path was added.
- T03 tests are in `tests/scripts/test_hermes_update_watch_state.py`; all filesystem fixtures use `tmp_path`, including child processes for lock contention and restrictive umask. Initial RED ran 16 contract tests against the missing module and observed 16 expected behavioral failures (no collection/environment failure). A later lock-mode regression observed 1 failure (`lock_mode_invalid`) under umask 0777; after fchmod of the exclusively created lock inode before mode validation, the regression passed. Independent verification then found namespace-replacement and report-directory-fsync retry defects; three new regressions observed 3 expected behavioral failures. The correction returns an immutable report-bytes snapshot, checks root/reports directory inode binding before beginning and persisting a send, and fsyncs the reports directory when reusing an existing identical report. The three counterexamples passed; the focused state suite passed 27 tests and the combined T01/T02/T03 guarded runner passed 72 tests, 0 failed.
- T03 closure evidence is recorded below; no live Git command, network, service/Discord operation, secret access, dependency install, state-root installation, permission repair, or native approval occurred.

## T03 independent closure evidence

Writer, independent targeted verifier, and parent guarded full feature check all passed 72 tests (32 release, 13 report, 27 state). Namespace substitution and orphan-report fsync retry regressions were observed RED and then corrected. SendIntent carries immutable attachment bytes; T04 must not reopen the original report pathname. T03 is functionally verified and committed as the slice-3 identity recorded below. Native review remains unavailable, not approved.

**Slice 3 commit:** `61b259ceef13ea14cccf69fff682b97e49c152d3` — `feat(ops): persist release reports and delivery intents safely`; 1,940 additions / 16 deletions. T03 is checked, verified with 72 passing tests and committed. The exact committed-only native STATUS again failed safely before mutation after a high assessment; no review receipt. Next active task: T04 CLI and snapshot-based Discord transport, without real sends. Earlier pending notes above are historical.

## Final monitoring verification

T04 independent counterexamples are resolved: pending renewal preserves discovery budgets, stale UUID delivery leaves current outbox unchanged, and upstream exit classification matches actual codes. Writer, independent verifier and parent guarded four-file runner each passed 98 tests, zero failures. This final status supersedes historical pending notes above. T01–T04 are functionally complete; native review remains unavailable, not approved. No installation, scheduling, real GitHub/Discord smoke, PROD access, push or update/recovery operation occurred.
