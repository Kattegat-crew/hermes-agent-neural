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
- Slice A documentation milestone: locally committed as `23945c6ec16a` (229 additions); P1 remains incomplete. Slice B documentation milestone: locally committed as `795cfa0ef8`. T05a source/tests are verified but uncommitted; parent owns the work-unit commit. No task is checked off until verification and commit evidence exist.

## Approval Gates

- Specification: approved by the user on 2026-10-08.
- Technical design: approved by the user on 2026-10-08 (Adelante).
- Task plan: bounded read-only discovery remains open. T05a source/tests are implemented and offline-verified, pending parent commit; T05b live rollout and protected operations remain blocked. No task/phase is complete.
- Safe exact implementation scopes may proceed only when activated with verified targets/checks; protected or unsafe operations remain blocked pending separate authorization.

## Stable Phase Checklist

| ID | Phase | Route and trigger evidence | Acceptance / proof | Status |
|---|---|---|---|---|
| P1 | Baseline evidence | Delegated; runtime and cross-project facts exceed the inline evidence budget. | Record the five confirmed product Git roots, six governance docs per root, template-only SDD indices, memory/job/backup/skill evidence, missing references, and pre-existing dirty state. Keep tool repositories/worktrees beyond this bounded inventory explicitly incomplete. | Documentation underway; bounded inventory |
| P2 | Protection and SDD governance | Delegated; policy and human approval gates span multiple artifacts. | Preserve confidentiality, scoped deletion authority, the shared Engram constraint, and spec approval before design. | Pending |
| P3 | Global/project instruction alignment and SDD delivery | Delegated writer; multiple agents, repositories/worktrees, protected paths, and human gates require cross-document alignment. | Document the actual plan: canonical global contract plus project rules; verify actual entrypoints, preserve history, identify blocked inventory, and keep spec approval before design. This phase is not merely preparation of documents. | Design approved; task plan recorded; evidence gates remain |
| P4 | Native memory and Engram validation | Delegated after approval; cross-store runtime verification needs focused evidence. | Verify native read/write and active Engram binding without creating another DB or merging memories. | Pending; approval and evidence required |
| P5 | Graph validation | Delegated after approval; graph output and runtime source differ. | Establish actual generator, path resolution, invocation, output freshness, and consumer behavior before any fix. | Pending; cause unverified |
| P6 | Scheduled-job validation | Delegated after approval; execution and delivery semantics require runtime evidence. | Verify job identity, schedule, overlap/idempotency, exit status, output delivery, and failure reporting. | Offline versioned wrapper unit implemented; commit pending; live delivery unverified |
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

Use .specs/memoria-dev/03-tasks.md to resolve read-only blockers first. Parent owns staging/commits for the approved local feature-branch chain; no PR, push, or merge is authorized. Do not mark tasks/phases complete without accepted verification and commit evidence; preserve unsafe operations as blocked.


## Task Breakdown Status

- User approved technical design on 2026-10-08 (Adelante); user approved feature-branch-chain delivery on 2026-10-08 (Aprobado).
- `03-tasks.md` contains T01–T10 plus T05a/T05b; all remain unchecked pending task-specific evidence/commit gates. T05a offline source/tests verified, pending parent commit; T05b live/protected work remains blocked. No phase is complete.
- Slice A: approved baseline + spec, locally committed as `23945c6ec16a` with 229 additions; this is a documentation milestone, not P1 completion.
- Slice B: design + tasks + tracker/index/PROJECT_MEMORY reconciliation; current worktree measure against HEAD is 340 additions + deletions, excluding TikTok. Recompute the staged snapshot before delivery. Full feature forecast remains unassessable pending evidence gates.


## T05a Implementation Evidence (2026-10-08)

- Added versioned `scripts/brain_graph_update_wrapper.sh` and offline `tests/cron/test_brain_graph_wrapper.py`; deployment source at `/opt/hermes-agent-data/scripts/brain_graph_update_wrapper.sh` was read-only and not changed or executed.
- Initial RED: 8 expected failures while versioned wrapper was absent; initial GREEN: 8 passed. Correction RED: TERM-resistant process-group test exceeded its bounded test deadline against unbounded wait; correction GREEN: bounded TERM→KILL cleanup plus `timeout --kill-after=5s`. Full offline+cron command `PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider tests/cron/test_brain_graph_wrapper.py tests/cron/test_cron_no_agent.py` passed 26 tests. No pre-implementation cron-regression baseline was captured. `bash -n`, `git diff --check`, and authored-file whitespace checks passed.
- Signal cleanup now bounds TERM-resistant process-group shutdown with TERM then KILL; timeout also uses a 5-second kill-after while retaining its 3300-second limit. No graph output path, cron configuration, database, service, permissions, or live artifact changed. T05a awaits parent commit; T05b remains blocked.
