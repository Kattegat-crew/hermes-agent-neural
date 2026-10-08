# Memoria DEV — ODD Feature Tracker

## Objective

Diagnose and repair only reproducible defects in DEV memory continuity, storage, graph generation, scheduled jobs, skill visibility, and end-to-end delivery. Preserve the existing memory architecture unless evidence and an approved specification justify a narrow change.

## Problem and Why

The DEV memory ticket reports several concerns, but the static audit and runtime evidence do not yet establish every reported cause. A staged, evidence-led specification is needed before technical design or runtime changes.

## Scope

- Reconcile the requested memory outcomes with current native memory, Engram, graph, cron, backup, and skill state.
- Verify only defects supported by observed evidence; carry unresolved runtime facts as explicit gaps.
- Use the existing SDD approval sequence before design and implementation.

## Constraints and Non-Goals

- No new active memory database, bulk merge, blanket deletion, or unapproved memory migration.
- No runtime/code fixes, handoff or MCP enhancements, production changes, service restarts, remote work, or secrets in docs in this initial documentation unit.
- Deletions require explicit approval scoped to named memories/files; do not infer deletion authority from a diagnosis.
- Do not claim active Engram DB binding, cron output freshness, duplicate-job elimination, backup restorability, or fleet skill availability without evidence.
- Preserve unrelated work already present in the repository.

## Delivery and Review State

- Route: delegated direct writer; preparation required reading the existing project rules, memory, and architecture, and this work spans multiple substantive documents.
- Delivery strategy: feature-branch-chain, approved by the user on 2026-10-08 (Aprobado); local slices only, no PR/push/merge.
- Latest measured documentation-unit diff: see final measured line-count statement below; excludes unrelated TikTok change. Recalculate exact staged snapshots; never code-golf or split cosmetically.
- Full runtime-feature forecast: unassessable until blocked targets and behavior scope are established; recompute before implementation and each work-unit commit. Slice A is baseline+spec (229 additions), locally committed as `23945c6ec16a`; documentation milestone, not P1 completion. Recompute Slice B additions + deletions against current HEAD, excluding unrelated TikTok edits.
- Native RDD state: unknown/unavailable; status access was refused with PermissionDenied and earlier output was contradictory. Do not infer effective mode, toggle it, or bypass the refusal.
- Last reviewed boundary: `70a846f7e63fc3e8ef7717decfd4e89be99ec2c5` (branch point supplied by parent; no review receipt claimed).
- Slice A documentation milestone: locally committed as `23945c6ec16a` (229 additions); P1 remains incomplete. Slice B documentation milestone: locally committed as `795cfa0ef8`. T05a source/tests are verified and committed as `e1feeb1d51`; only T05a is checked off. Progress reconciliation is recorded in local documentation commit `91b8ba8d3e`.

## Approval Gates

- Specification: approved by the user on 2026-10-08.
- Technical design: approved by the user on 2026-10-08 (Adelante).
- Task plan: bounded read-only discovery remains open. T05a source/tests are verified and committed; T05b live rollout and protected operations remain blocked. No phase is complete.
- Safe exact implementation scopes may proceed only when activated with verified targets/checks; protected or unsafe operations remain blocked pending separate authorization.

## Stable Phase Checklist

| ID | Phase | Route and trigger evidence | Acceptance / proof | Status |
|---|---|---|---|---|
| P1 | Baseline evidence | Delegated; runtime and cross-project facts exceed the inline evidence budget. | Record the five confirmed product Git roots, six governance docs per root, template-only SDD indices, memory/job/backup/skill evidence, missing references, and pre-existing dirty state. Keep tool repositories/worktrees beyond this bounded inventory explicitly incomplete. | Documentation underway; bounded inventory |
| P2 | Protection and SDD governance | Delegated; policy and human approval gates span multiple artifacts. | Preserve confidentiality, scoped deletion authority, the shared Engram constraint, and spec approval before design. | Pending |
| P3 | Global/project instruction alignment and SDD delivery | Delegated writer; multiple agents, repositories/worktrees, protected paths, and human gates require cross-document alignment. | Document the actual plan: canonical global contract plus project rules; verify actual entrypoints, preserve history, identify blocked inventory, and keep spec approval before design. This phase is not merely preparation of documents. | Design approved; task plan recorded; evidence gates remain |
| P4 | Native memory and Engram validation | Delegated after approval; cross-store runtime verification needs focused evidence. | Verify native read/write and active Engram binding without creating another DB or merging memories. | Pending; approval and evidence required |
| P5 | Graph validation | Delegated after approval; graph output and runtime source differ. | Establish actual generator, path resolution, invocation, output freshness, and consumer behavior before any fix. | Pending; cause unverified |
| P6 | Scheduled-job validation | Delegated after approval; execution and delivery semantics require runtime evidence. | Verify job identity, schedule, overlap/idempotency, exit status, output delivery, and failure reporting. | Source-only wrapper unit committed; live deployment/delivery unverified |
| P7 | Skill visibility and duplication review | Delegated after approval; inventory and catalog evidence are incomplete. | Verify catalog/link/load behavior and identify any duplicate job only from current evidence. | Pending; historical duplicate count not treated as current fact |
| P8 | End-to-end rollout and regression proof | Delegated after approval; changes span runtime entrypoints and discovered repositories/worktrees. | Run an acceptance matrix for Codex, OpenCode, Gemini, Copilot, Antigravity, and Hermes against each discovered in-scope repo/worktree; record blocked surfaces and expand the five-root product inventory only from evidence. Exclude production rollout. | Pending; broader inventory incomplete |
| P9 | Closure and handover | Delegated after preceding proof; requires durable state reconciliation. | Record verified changes, commands/results, remaining unknowns, next actions, and mirror status; close through ordinary repository policy. | Pending |

## Verification for This Documentation Unit

- `git diff --check`
- `git status --short`
- Structural readback of all seven authorized documentation files, including new `03-tasks.md` and corrected approval footer.
- A temporary inline Python check validates approved-spec/approved-design/gated-implementation states, task IDs/dependencies/guards, chain strategy, candidate-map and blocker evidence, stable P1–P9 phases, tracker state, and local links resolving under /opt.
- Record the approved host-level ownership/mode proof and the namespace-visible projection accurately; do not retry chown or use namespace workarounds.
- Measure additions plus deletions in the authored documentation diff; do not include generated files.
- No source tests or runtime checks are applicable to this passive-documentation unit. This exception does not prove any runtime memory behavior.

## Current Evidence and Remaining Gaps

- Baseline observations are dated 2026-10-08 and summarized in `.specs/memoria-dev/00-baseline.md`; counters are point-in-time and may change. Five confirmed product Git roots are enumerated; tools and all worktrees are not exhaustively inventoried.
- The active Engram database binding is unverified even though a shared database and MCP entry were observed.
- Default, Roshi, and Vigia are configured to a different Engram DB inode than the policy-designated root DB; this is configuration evidence, not proof of live binding. Preserve both stores and defer any alignment choice until safe access and data divergence are assessed.
- The memory-named cron completed with `status=ok`, but known invocation/output delivery was not established; this does not prove successful delivery or false success.
- Parent source inspection found a graph producer/consumer path mismatch and a wrapper that exits 0 after capturing an inner error code; the runtime files were inaccessible to this writer. Do not equate this source defect with proven end-to-end staleness or delivery impact.
- Cross-repository audit found two unresolved local architecture references; replacement targets are unknown and no architecture/catalog fix is authorized here.
- Protected read-only paths remain inaccessible without authorization; do not use permission or namespace workarounds. Host-level ownership is verified despite the namespace-visible UID/GID projection; no repair is needed.
- Restore testing, dynamic project-memory reads across surfaces, profile/fleet skill catalog availability, and any current duplicate-job condition remain open evidence gaps.
- The repository contains a pre-existing modified TikTok ingestion skill; preserve it and do not include it in this feature's edits.

## Next Step

Continue with independent read-only inventory and actual global/project instruction plus managed-loader provenance reconciliation. Parent reports native RDD preflight was refused because the executor UID (0) does not match repository owner UID (10000); no review mutation, receipt, switch, chown, or workaround occurred. Do not infer RDD state. T05b deployment/live validation remains blocked. No PR, push, or merge is authorized. Do not mark tasks/phases complete without accepted verification and commit evidence; preserve unsafe operations as blocked.


## Task Breakdown Status

- User approved technical design on 2026-10-08 (Adelante); user approved feature-branch-chain delivery on 2026-10-08 (Aprobado).
- `03-tasks.md` contains T01–T10 plus T05a/T05b. T05a alone is checked: source-only offline wrapper unit committed as `e1feeb1d51`; T05b live/protected work remains blocked. All nine phases remain incomplete.
- Slice A: approved baseline + spec, locally committed as `23945c6ec16a` with 229 additions; this is a documentation milestone, not P1 completion.
- Slice B: design + tasks + tracker/index/PROJECT_MEMORY reconciliation; 340 additions + deletions, excluding TikTok, committed as `795cfa0ef8`. Slice C: source-only wrapper and tests plus task/tracker updates, 367 additions + deletions, committed as `e1feeb1d51`. Full feature forecast remains unassessable pending evidence gates.


## T05a Implementation Evidence (2026-10-08; source-only unit committed)

- Added versioned `scripts/brain_graph_update_wrapper.sh` and offline `tests/cron/test_brain_graph_wrapper.py`; commit `e1feeb1d51` (`fix(memory): preserve graph wrapper failures and bound cancellation`, 357 additions + 10 deletions). Deployed source at `/opt/hermes-agent-data/scripts/brain_graph_update_wrapper.sh` was read-only and not changed or executed. Versioned source provenance does not establish deployment.
- Initial RED: 8 expected failures while versioned wrapper was absent; initial GREEN: 8 passed. Correction RED: TERM-resistant process-group test exceeded its bounded test deadline against unbounded wait; correction GREEN: bounded TERM→KILL cleanup plus `timeout --kill-after=5s`. Full offline+cron command `PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider tests/cron/test_brain_graph_wrapper.py tests/cron/test_cron_no_agent.py` passed 26 tests; parent reports independent final run 26 passed in 9.99s. No pre-implementation cron-regression baseline was captured. `bash -n`, `git diff --check`, and authored-file whitespace checks passed.
- Signal cleanup bounds TERM-resistant process-group shutdown with TERM then KILL; timeout uses a 5-second kill-after and retains its 3300-second limit. Committed source SHA-256: `d1b03ff0377b6b372e5929590ff6c8f3931752ed71048e8ed359252a5c8dcb24`. No graph output path, cron configuration, database, service, permissions, or live artifact changed. T05b remains blocked; all nine phases remain incomplete.
