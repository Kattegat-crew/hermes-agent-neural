# Hermes Project Memory & Session Continuity

> **Session Lifecycle Contract**:
> - **On Session Start**: Read this file and [`ARCHITECTURE.md`](file:///opt/hermes-agent/ARCHITECTURE.md) to recover active context and understand current flows before taking any action.
> - **On Session Close**: Update this file with what was accomplished, verification results, and immediate next steps.

---

## 1. Active Focus & Current Goal
* **Current Initiative**: Prepare and execute the approved DEV memory plan only within verified, safe task scopes; unsafe operations remain blocked.
* **Lead Agent**: Antigravity (`agy`) / Ragnar, with Codex preparing the initial documentation unit.
* **Target Path**: [`/opt/hermes-agent/`](file:///opt/hermes-agent/).
* **Delivery strategy:** feature-branch-chain approved by the user on 2026-10-08 (Aprobado); local slices only.
* **Approval State**: Specification/design approved by the user on 2026-10-08 (Adelante); feature-branch-chain approved (Aprobado); no PR, push, merge, or unsafe runtime action is authorized.

---

## 2. Handover from Last Session
* **Current Reconciliation (2026-10-08)**:
  - Verified that `AGENTS.md` now references the project continuity and architecture files and the SDD/memory rulebooks.
  - Verified that `.agents/rules/04-memory-and-reuse.md` now exists. Earlier pending entries below describe the state recorded by that prior handover and are retained as history; the fleet `SOUL.md` synchronization was not verified in this audit.
  - The user approved the specification and design on 2026-10-08 (Adelante). Slice A (`23945c6ec16a`) and Slice B (`795cfa0ef8`) are local documentation milestones. T05a adds an offline versioned wrapper and tests, verified but awaiting parent commit; no deployed wrapper, live job, DB, service, or configuration was changed.
  - Read-only runtime evidence remains incomplete for active Engram binding, graph invocation/freshness, job output delivery, restore success, and skill visibility. See `.specs/memoria-dev/00-baseline.md`.
  - The bounded cross-project audit confirmed five product Git roots: Hermes, Golden Game, Paradise Casino, Marketing Campaign Generator, and AI Platform. Each has six active governance Markdown documents; all five SDD indices list only their template. The audit counted 142 checked local links and found two unresolved architecture references with unknown replacements. `/opt/hermes-agent-data` is a separate runtime data/workspace path, not one of the five repositories; it was not accessible in the initial audit. Tool repositories and all worktrees are not exhaustively inventoried. No architecture fixes were made.
  - Namespace-visible `stat` projected UID/GID `65534:65534` for the five authorized documentation files (mode `644`) and `.git` (mode `755`). Separate approved host-level `stat` proof confirmed `hermes:hermes` UID/GID `10000:10000` for all five files and `.git` (file mode `644`, `.git` mode `755`). The namespace projection is not evidence of an ownership fault; no chown retry or permission workaround was attempted.
  - Parent reports Hermes executor `os.access` read/write true for both distinct Engram DB paths; this is not proof of live service binding. Canonical DB mode `666`, parent directory mode `777`; no automatic permission changes. Native RDD status access returned PermissionDenied, so mode is unknown and no bypass/toggle is permitted.
  - T05a verification (2026-10-08): initial RED was 8 expected failures before the versioned wrapper existed; initial GREEN was 8 passed. A later TERM-resistant-process test reproduced an unbounded cleanup wait (RED); after bounded TERM→KILL process-group cleanup and `timeout --kill-after=5s`, `PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider tests/cron/test_brain_graph_wrapper.py tests/cron/test_cron_no_agent.py` passed 26 tests. `bash -n scripts/brain_graph_update_wrapper.sh`, `git diff --check`, and authored-file whitespace checks passed. No pre-implementation cron-regression baseline was captured. T05a is uncommitted and parent-owned; T05b deployment/live validation remains blocked.
  - Feature-branch-chain delivery was approved on 2026-10-08 (Aprobado); Slice A `23945c6ec16a` and Slice B `795cfa0ef8` are local docs-only commits. No PRs, pushes, or merges were created.
  - Existing modified TikTok ingestion skill is unrelated work and must remain untouched.
* **Prior Handover (historical; file mtime observed 2026-10-03, exact event dates absent from its body)**:
* **Completed (historically recorded; not current verification)**:
  - Established `.agents/rules/` with `01-sdd-workflow.md`, `02-vps-guardrails.md`, and `03-code-standards.md`.
  - Created `.specs/` repository index and base templates (`01-spec.md`, `02-design.md`, `03-tasks.md`).
  - Created [`ARCHITECTURE.md`](file:///opt/hermes-agent/ARCHITECTURE.md) documenting active daemons, WhatsApp persistence invariants, and reusable code catalog.
  - Configured `PROJECT_MEMORY.md` as the official session continuity ledger.
* **Verified by (older handover report; not reverified on 2026-10-08)**:
  - File presence and permissions (`chown -R hermes:hermes`).
  - Process audit confirmed active running daemons (Ragnar, Roshi, Vigia, WhatsApp bridge on `:3000`, Dashboard on `:9112`).
* **Pending / Incomplete (status at that older handover, not current state)**:
  - Establish rule `04-memory-and-reuse.md` in `.agents/rules/`.
  - Update `AGENTS.md` and `SOUL.md` to bind all external CLI agents and internal Hermes fleet profiles to this memory and reuse contract.

---

## 3. Operational Decisions & Gotchas
* **Separation of Concerns**: Kept `ARCHITECTURE.md` (static operational truth and reusable code inventory) decoupled from `PROJECT_MEMORY.md` (ephemeral session state) to protect system maps from accidental agent truncation and prevent prompt cache degradation.
* **WhatsApp Session**: Never touch `/opt/hermes-agent-data/whatsapp/session/` (symlink `/opt/data/whatsapp/session/`).
* **Ownership**: All project files must remain owned by `hermes:hermes`.

---

## 4. Next Immediate Actions
- [ ] Parent reviews and owns the T05a code/test work-unit commit. T05b live scheduler/artifact validation and deployment remain blocked pending separate evidence and authorization.
- [ ] Resolve blocked scope inputs and obtain scoped approval before protected writes, DB operations, restores, job invocations, or other unsafe validation.
- [ ] Parent owns doc-slice staging/commits; no push, PR, or merge is authorized.
- [ ] Verify fleet SOUL.md synchronization separately; this audit did not establish it.
