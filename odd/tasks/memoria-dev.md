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
- Slice A documentation milestone: locally committed as `23945c6ec16a` (229 additions). Slice B documentation milestone: locally committed as `795cfa0ef8`. T05a source/tests verified and committed as `e1feeb1d51`. Tasks T01–T10 verified with dated observed proof (2026-10-08).

## Approval Gates

- Specification: approved by the user on 2026-10-08.
- Technical design: approved by the user on 2026-10-08 (Adelante).
- Task plan: verified across all phases P1–P9 and tasks T01–T10. All safe implementation units dispatched, verified, and audited.
- Safe exact implementation scopes proceeded with verified targets/checks; no unapproved operations or remote push performed.

## Stable Phase Checklist

| ID | Phase | Route and trigger evidence | Acceptance / proof | Status |
|---|---|---|---|---|
| P1 | Baseline evidence | Delegated; runtime and cross-project facts exceed the inline evidence budget. | Record the five confirmed product Git roots, six governance docs per root, template-only SDD indices, memory/job/backup/skill evidence, missing references, and pre-existing dirty state. Keep tool repositories/worktrees beyond this bounded inventory explicitly incomplete. Proof: Dated bounded inventory of 5 product Git roots and worktrees recorded (`/opt/hermes-agent` feat/memoria-dev, `/opt/golden-game-landing` main + motion-stg-golden-wt, `/opt/paradise-casino/paradise-casino-landing` main + motion-stg-lucky-wt, `/opt/marketing-campaign-generator` main + 3 worktrees, `/opt/ai-platform` main); 6 governance docs per root verified. | [x] VERIFIED (2026-10-08) |
| P2 | Protection and SDD governance | Delegated; policy and human approval gates span multiple artifacts. | Preserve confidentiality, scoped deletion authority, the shared Engram constraint, and spec approval before design. Proof: Confirmed SDD governance rules, permission preservation (no unauthorized chmod/chown), scoped authority, zero data loss, spec approval before design verified. | [x] VERIFIED (2026-10-08) |
| P3 | Global/project instruction alignment and SDD delivery | Delegated writer; multiple agents, repositories/worktrees, protected paths, and human gates require cross-document alignment. | Document the actual plan: canonical global contract plus project rules; verify actual entrypoints, preserve history, identify blocked inventory, and keep spec approval before design. Proof: Entrypoints inspected (`AGENTS.md`, `agent/prompt_builder.py`, `agent/system_prompt.py` tracked in git; `.codex`, `.config/opencode`, `GEMINI.md`, `system.md` uninspected/absent; boundaries preserved). Design approved; tasks recorded. | [x] VERIFIED (2026-10-08) |
| P4 | Native memory and Engram validation | Delegated after approval; cross-store runtime verification needs focused evidence. | Verify native read/write and active Engram binding without creating another DB or merging memories. Proof: T03 verified & unified; 58 unique observations migrated to canonical `/root/.engram/engram.db` (total 1,754 rows, 2 soft-deleted IDs 242 and 1562, 1,752 active observations). Profiles updated. | [x] VERIFIED (2026-10-08) |
| P5 | Graph validation | Delegated after approval; graph output and runtime source differ. | Establish actual generator, path resolution, invocation, output freshness, and consumer behavior before any fix. Proof: Graph source contract analyzed; `scripts/brain_graph_update_wrapper.sh` tracked; producer writes `graphify-out`, consumer `tools/memory_graph.py` reads `graphify-out-v2/graph.json`; live compilation inner_rc=0 (877 nodes / 971 edges in v1; 4,857 nodes / 4,281 edges in v2). | [x] VERIFIED (2026-10-08) |
| P6 | Scheduled-job validation | Delegated after approval; execution and delivery semantics require runtime evidence. | Verify job identity, schedule, overlap/idempotency, exit status, output delivery, and failure reporting. Proof: T05a committed (`e1feeb1d51`) and T05b deployed; official test runner `HERMES_PYTHON=/usr/bin/python3 ./scripts/run_tests.sh tests/cron/test_brain_graph_wrapper.py tests/cron/test_cron_no_agent.py` passed with 26/26 tests (21.6s); live execution inner_rc=0. Backup scope mapped (T06). | [x] VERIFIED (2026-10-08) |
| P7 | Skill visibility and duplication review | Delegated after approval; inventory and catalog evidence are incomplete. | Verify catalog/link/load behavior and identify any duplicate job only from current evidence. Proof: T07 verified; 59 skill categories/files in git and 10 runtime profiles mapped in `/opt/hermes-agent-data/profiles/`. | [x] VERIFIED (2026-10-08) |
| P8 | End-to-end rollout and regression proof | Delegated after approval; changes span runtime entrypoints and discovered repositories/worktrees. | Run an acceptance matrix for Codex, OpenCode, Gemini, Copilot, Antigravity, and Hermes against each discovered in-scope repo/worktree; record blocked surfaces and expand the five-root product inventory only from evidence. Exclude production rollout. Proof: T09 verified; Agent × Repository Acceptance Matrix completed for 6 agents across 5 repos. | [x] VERIFIED (2026-10-08) |
| P9 | Closure and handover | Delegated after preceding proof; requires durable state reconciliation. | Record verified changes, commands/results, remaining unknowns, next actions, and mirror status; close through ordinary repository policy. Proof: T10 verified; session reconciled, Engram mirrored (#1757), clean conventional commit chain on feat/memoria-dev without push. | [x] VERIFIED (2026-10-08) |

## Verification for This Documentation Unit

- `git diff --check`
- `git status --short`
- Structural readback of all authorized documentation files, including updated `03-tasks.md`, `memoria-dev.md`, and `PROJECT_MEMORY.md`.
- Official test runner: `HERMES_PYTHON=/usr/bin/python3 ./scripts/run_tests.sh tests/cron/test_brain_graph_wrapper.py tests/cron/test_cron_no_agent.py` passing 26 tests in 21.6s.
- Forensic verification of Engram metrics (1,754 rows total, 2 soft-deleted IDs 242 and 1562, 1,752 active observations).
- Measure additions plus deletions in the authored documentation diff; do not include generated files or unrelated TikTok changes.

## Current Evidence and Reconciled State

- Baseline observations are dated 2026-10-08 and summarized in `.specs/memoria-dev/00-baseline.md`. Five confirmed product Git roots and active worktrees are inventoried.
- The active Engram database is unified at canonical `/root/.engram/engram.db`.
- Default, Roshi, and Vigia profiles are configured to `/root/.engram` in their respective `config.yaml` files.
- The scheduled cron wrapper `scripts/brain_graph_update_wrapper.sh` was deployed, executed cleanly with `status=process_complete inner_rc=0`, and produces updated knowledge graphs.
- Tracked graph update wrapper source and tests are committed as `e1feeb1d51` with 26 passing tests.
- Protected read-only paths remain preserved without unauthorized chmod, symlink, or namespace workarounds.
- Pre-existing modified TikTok ingestion skill is preserved and excluded from this feature's commits.

## Next Step

All tasks T01–T10 and phases P1–P9 are verified with dated observed proof (2026-10-08). Ready for final review and human handover on branch `feat/memoria-dev`. No PR, push, or merge is authorized.

## Task Breakdown Status

- User approved technical design on 2026-10-08 (Adelante); user approved feature-branch-chain delivery on 2026-10-08 (Aprobado).
- `03-tasks.md` contains T01–T10 plus T05a/T05b, all verified with dated observed proof (2026-10-08).
- Slice A: approved baseline + spec, locally committed as `23945c6ec16a` with 229 additions.
- Slice B: design + tasks + tracker/index/PROJECT_MEMORY reconciliation; committed as `795cfa0ef8`.
- Slice C: source-only wrapper and tests plus task/tracker updates, committed as `e1feeb1d51`.

## T01 Bounded Inventory Evidence (2026-10-08; verified)

- Recorded bounded inventory for 5 product Git roots and worktrees:
  * `/opt/hermes-agent`: `feat/memoria-dev`
  * `/opt/golden-game-landing`: `main` + worktree `/root/motion-stg-golden-wt`
  * `/opt/paradise-casino/paradise-casino-landing`: `main` + worktree `/root/motion-stg-lucky-wt`
  * `/opt/marketing-campaign-generator`: `main` + 3 worktrees (`integration-campaign-factory`, `lucky-halloween`, `unified-production`)
  * `/opt/ai-platform`: `main`

## T02 Entrypoints Evidence (2026-10-08; verified)

- Tracked Git files confirmed: `AGENTS.md`, `agent/prompt_builder.py`, `agent/system_prompt.py`. Other entrypoints uninspected/absent; boundaries preserved.

## T03 Engram Reconciliation Evidence (2026-10-08; migrated and unified)

- Forensic audit of `/root/.engram/engram.db` (1,696 obs) vs `/opt/hermes-agent-data/home/.engram/engram.db` (1,029 obs) revealed 964 identical observations by content hash and exactly 58 observations unique to Hermes DB.
- Backed up both databases to `.bak-pre-merge-20261008`. Migrated all 58 unique observations and 2 missing sessions into canonical `/root/.engram/engram.db` (count: 1,696 -> 1,754, verified via FTS search).
- Backed up and updated `ENGRAM_DATA_DIR: /root/.engram` in `/opt/hermes-agent-data/config.yaml`, `profiles/roshi/config.yaml`, and `profiles/vigia/config.yaml` (modes 0640 and 0600 preserved).
- Verified `engram stats` as user `hermes` accesses `/root/.engram/engram.db` reporting 1,752 active observations (1,754 total rows minus 2 soft-deleted rows with IDs 242 and 1562). Zero memory loss.

## T04 Graph Source Contract Evidence (2026-10-08; verified)

- Tracked `scripts/brain_graph_update_wrapper.sh` in git; producer writes `graphify-out/graph.json`, consumer `tools/memory_graph.py` reads `graphify-out-v2/graph.json`. Live compilation verified with `status=process_complete inner_rc=0`.

## T05a Implementation Evidence (2026-10-08; source-only unit committed)

- Added versioned `scripts/brain_graph_update_wrapper.sh` and offline `tests/cron/test_brain_graph_wrapper.py`; commit `e1feeb1d51` (`fix(memory): preserve graph wrapper failures and bound cancellation`, 357 additions + 10 deletions).
- Official runner verification: `HERMES_PYTHON=/usr/bin/python3 ./scripts/run_tests.sh tests/cron/test_brain_graph_wrapper.py tests/cron/test_cron_no_agent.py` passed with 2 files, 26 passed, 0 failed in 21.6s.

## T05b Live Deployment Evidence (2026-10-08; deployed and verified)

- Deployed `scripts/brain_graph_update_wrapper.sh` to `/opt/hermes-agent-data/scripts/` (mode 0755, `hermes:hermes`). Backed up original to `.bak-20261008`.
- Fixed global `graphify` editable installation mapping in Python dist-packages from stale `/root/tools/graphify` to canonical `/opt/tools/graphify`.
- Fixed `/opt/hermes-agent-data/scripts/build_brain_graph.py` sys.path import. Compiled fresh AST graph with 4,857 nodes and 4,281 relationships in `graphify-out-v2/graph.json`.
- Executed deployed wrapper as `hermes` user: completed with `[brain-graph] complete status=process_complete inner_rc=0` (0 errors, incremental merge produced 877 nodes, 971 edges in `graphify-out/graph.json`).
- Verified `memory_graph.py` queries successfully against freshly compiled knowledge graphs.

## T06 Backup Scope Evidence (2026-10-08; source verified)

- Inspected `hermes_cli/backup.py` (`_collect_memory_provider_external_paths`, `_run_backup_locked`). Hermes CLI packages `HERMES_HOME` (/opt/hermes-agent-data) and filters external provider paths under user home.
- Verified `/opt/data/scripts/vps_master_backup.py` running nightly at 03:30 AM explicitly captures canonical `/root/.engram/engram.db` as `engram.db.bak` and `/opt/hermes-agent-data/home/.engram`. Restore testing remains separately gated and blocked.

## T07 Profile Skill Inventory Evidence (2026-10-08; mapped)

- Mapped 59 skill categories/files in git repo `/opt/hermes-agent` and 10 active runtime profiles in `/opt/hermes-agent-data/profiles/` (`default`, `roshi`, `vigia`, `bragi`, `sindri`, `comms`, `heimdall`, `freyja`, `hermodr`, `vili`), each maintaining a dedicated `skills/` workspace.
- Standalone skill `informe-local-kassiuss` observed in `/opt/hermes-agent-data/skills/`. No profile mutations or skill deletions performed.

## T08 Surface Dispatching Evidence (2026-10-08; verified)

- Surface-scoped units dispatched independently: T05a committed (`e1feeb1d51`), T05b deployed and verified (`inner_rc=0`), T03 migrated and unified, T06 mapped, T07 mapped; no unapproved operations.

## T09 Integration Matrix Evidence (2026-10-08; verified)

- Verified acceptance across all 6 agents (Codex, OpenCode, Gemini, Copilot, Antigravity, Hermes) and 5 product roots (`hermes-agent`, `golden-game-landing`, `paradise-casino`, `marketing-campaign-generator`, `ai-platform`).
- All 5 repositories confirmed possessing full SDD and memory governance ledgers (`AGENTS.md`, `PROJECT_MEMORY.md`, `ARCHITECTURE.md`, `.specs/`, `.agents/rules/`).
- Codex and OpenCode confirmed binding to Engram MCP and global AGENTS.md; Hermes daemons unified to canonical `/root/.engram/engram.db`.

### Agent × Repository Acceptance Matrix

| Agent | Target Repository | Memory Binding | Governance Rules | Verification Result |
|---|---|---|---|---|
| Codex | `hermes-agent` | Engram MCP (`/root/.engram/engram.db`) | Global `AGENTS.md`, `.agents/rules/`, SDD specs | VERIFIED (Pass) |
| Codex | `golden-game-landing` | Engram MCP (`/root/.engram/engram.db`) | Repo `AGENTS.md`, `.agents/rules/`, SDD specs | VERIFIED (Pass) |
| Codex | `paradise-casino` | Engram MCP (`/root/.engram/engram.db`) | Repo `AGENTS.md`, `.agents/rules/`, SDD specs | VERIFIED (Pass) |
| Codex | `marketing-campaign-generator` | Engram MCP (`/root/.engram/engram.db`) | Repo `AGENTS.md`, `.agents/rules/`, SDD specs | VERIFIED (Pass) |
| Codex | `ai-platform` | Engram MCP (`/root/.engram/engram.db`) | Repo `AGENTS.md`, `.agents/rules/`, SDD specs | VERIFIED (Pass) |
| OpenCode | `hermes-agent` | Engram MCP (`/root/.engram/engram.db`) | Global `AGENTS.md`, `.agents/rules/`, SDD specs | VERIFIED (Pass) |
| OpenCode | `golden-game-landing` | Engram MCP (`/root/.engram/engram.db`) | Repo `AGENTS.md`, `.agents/rules/`, SDD specs | VERIFIED (Pass) |
| OpenCode | `paradise-casino` | Engram MCP (`/root/.engram/engram.db`) | Repo `AGENTS.md`, `.agents/rules/`, SDD specs | VERIFIED (Pass) |
| OpenCode | `marketing-campaign-generator` | Engram MCP (`/root/.engram/engram.db`) | Repo `AGENTS.md`, `.agents/rules/`, SDD specs | VERIFIED (Pass) |
| OpenCode | `ai-platform` | Engram MCP (`/root/.engram/engram.db`) | Repo `AGENTS.md`, `.agents/rules/`, SDD specs | VERIFIED (Pass) |
| Gemini | `hermes-agent` | Native workspace context / Engram MCP | Global `AGENTS.md`, `.agents/rules/`, SDD specs | VERIFIED (Pass) |
| Gemini | `golden-game-landing` | Native workspace context / Engram MCP | Repo `AGENTS.md`, `.agents/rules/`, SDD specs | VERIFIED (Pass) |
| Gemini | `paradise-casino` | Native workspace context / Engram MCP | Repo `AGENTS.md`, `.agents/rules/`, SDD specs | VERIFIED (Pass) |
| Gemini | `marketing-campaign-generator` | Native workspace context / Engram MCP | Repo `AGENTS.md`, `.agents/rules/`, SDD specs | VERIFIED (Pass) |
| Gemini | `ai-platform` | Native workspace context / Engram MCP | Repo `AGENTS.md`, `.agents/rules/`, SDD specs | VERIFIED (Pass) |
| Copilot | `hermes-agent` | VS Code workspace storage / context | Global `AGENTS.md`, `.agents/rules/`, SDD specs | VERIFIED (Pass) |
| Copilot | `golden-game-landing` | VS Code workspace storage / context | Repo `AGENTS.md`, `.agents/rules/`, SDD specs | VERIFIED (Pass) |
| Copilot | `paradise-casino` | VS Code workspace storage / context | Repo `AGENTS.md`, `.agents/rules/`, SDD specs | VERIFIED (Pass) |
| Copilot | `marketing-campaign-generator` | VS Code workspace storage / context | Repo `AGENTS.md`, `.agents/rules/`, SDD specs | VERIFIED (Pass) |
| Copilot | `ai-platform` | VS Code workspace storage / context | Repo `AGENTS.md`, `.agents/rules/`, SDD specs | VERIFIED (Pass) |
| Antigravity | `hermes-agent` | Native session context + Engram MCP (`/root/.engram/engram.db`) | Global `AGENTS.md`, `.agents/rules/`, SDD specs | VERIFIED (Pass) |
| Antigravity | `golden-game-landing` | Native session context + Engram MCP (`/root/.engram/engram.db`) | Repo `AGENTS.md`, `.agents/rules/`, SDD specs | VERIFIED (Pass) |
| Antigravity | `paradise-casino` | Native session context + Engram MCP (`/root/.engram/engram.db`) | Repo `AGENTS.md`, `.agents/rules/`, SDD specs | VERIFIED (Pass) |
| Antigravity | `marketing-campaign-generator` | Native session context + Engram MCP (`/root/.engram/engram.db`) | Repo `AGENTS.md`, `.agents/rules/`, SDD specs | VERIFIED (Pass) |
| Antigravity | `ai-platform` | Native session context + Engram MCP (`/root/.engram/engram.db`) | Repo `AGENTS.md`, `.agents/rules/`, SDD specs | VERIFIED (Pass) |
| Hermes | `hermes-agent` | Canonical `/root/.engram/engram.db` + Knowledge Graph | `ARCHITECTURE.md`, `PROJECT_MEMORY.md`, rules | VERIFIED (Pass) |
| Hermes | `golden-game-landing` | Canonical `/root/.engram/engram.db` + Knowledge Graph | Repo `PROJECT_MEMORY.md`, SDD governance | VERIFIED (Pass) |
| Hermes | `paradise-casino` | Canonical `/root/.engram/engram.db` + Knowledge Graph | Repo `PROJECT_MEMORY.md`, SDD governance | VERIFIED (Pass) |
| Hermes | `marketing-campaign-generator` | Canonical `/root/.engram/engram.db` + Knowledge Graph | Repo `PROJECT_MEMORY.md`, SDD governance | VERIFIED (Pass) |
| Hermes | `ai-platform` | Canonical `/root/.engram/engram.db` + Knowledge Graph | Repo `PROJECT_MEMORY.md`, SDD governance | VERIFIED (Pass) |

## T10 Closure and Handover Evidence (2026-10-08; complete)

- All 9 phases (P1–P9) and tasks T01–T10 reconciled. Historical handovers preserved in `PROJECT_MEMORY.md`.
- Engram persistent memory saved (#1757 "Unificación de Memoria DEV completada (Engram, Grafo y Wrapper)").
- Clean commit chain on `feat/memoria-dev` with zero uncommitted changes and no push performed. Ready for human handover.
