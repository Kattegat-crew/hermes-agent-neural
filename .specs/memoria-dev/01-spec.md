# Feature Specification: DEV Memory Continuity and Delivery

* **Status**: Approved — user sign-off 2026-10-08
* **Author**: NeuralCrew Labs / Codex, with user approval
* **Target Module**: DEV memory operations across the existing Hermes, Engram, graph, scheduled-job, backup, and skill surfaces
* **Created**: 2026-10-08
* **Updated**: 2026-10-08 (specification and design approved; implementation remains scoped by 03-tasks.md)

---

## 1. Problem Statement and Motivation

The DEV memory ticket raises concerns about continuity, path handling, graph freshness, scheduled-job success/delivery, duplication, backups, and skill visibility. The read-only baseline confirms the presence of several stores and outputs but does not prove their complete read/write, invocation, freshness, delivery, or restore behavior. The project needs an evidence-backed contract before design or runtime changes.

The objective is to make intended DEV memory available and recoverable through the existing systems while preserving user control, project isolation, and the single shared Engram database requirement. A reported issue is not accepted as a defect until its current behavior and failure mode are reproducible or otherwise supported by direct evidence.

## 2. Goals and Non-Goals

### Goals

- Establish which existing memory stores are authoritative for session continuity, shared cross-agent context, and operational graph use.
- Ensure each in-scope DEV agent can retrieve the intended current context and preserve approved updates across sessions.
- Establish observable success and failure criteria for any in-scope memory graph or scheduled-job run, including whether expected output was produced and delivered.
- Preserve recoverability through verified backups and scoped restore procedures.
- Make skill/catalog visibility and any actual duplicate producers verifiable without inferring from counts or historical reports.
- Maintain the existing shared Engram database and avoid accidental cross-project memory mixing.
- Treat `/root/AGENTS.md` as the canonical global policy source, with `.codex/AGENTS.md` and repository `AGENTS.md` files as scoped overlays; verify that relationship against the actual entrypoints used by Codex, OpenCode, Gemini, Copilot, Antigravity, and Hermes rather than assuming every runtime loads every file.
- Maintain a Markdown audit of every discovered first-party repository/worktree, with inventory completeness explicit; if a root is inaccessible or cannot be identified, record the blocked scope rather than claim exhaustive coverage.
- Keep current handover and governance documents aligned with verified state while preserving dated history and avoiding edits to generated sources unless an exact deletion list is separately approved.
- Define a rollback outcome for each approved implementation unit, separate from any backup/restore validation, preserving user memories, their history, and prior configuration.

### Non-Goals

- Creating a second active memory database, replacing Engram, or introducing a new persistence service.
- Automatically merging memories across agents/projects, bulk migration, blanket deletion, or content deduplication without an explicit approved scope.
- Treating a one-time `status=ok`, file presence, byte count, or graph timestamp as proof of delivery, freshness, or recoverability.
- Adding or redesigning handoff, MCP gateway, ticketing, or general orchestration capabilities.
- Changing production services, executing remote operations, or rolling out to production as part of this DEV specification.
- Assuming a defect exists in runtime paths, cron semantics, backups, or duplicate-job behavior before the evidence gaps in the baseline are closed.
- Claiming that all six named agent entrypoints already load the same files or obey the contract until their actual runtime entrypoints and behavior are verified.
- Bypassing protected read-only `.codex/`, `.agents/`, `.git/`, or `.aws/` boundaries using chmod, namespace tricks, alternate paths, or other permission workarounds.

## 3. User Stories and Functional Requirements

- **US-1 — Session continuity**: As a DEV agent or contributor, I need the approved project context and recent verified handover to be retrievable at the start of work, so that I do not rely on stale or missing memory.
  - **FR-1.1**: In-scope agents must identify the existing source(s) for project-local handover and shared memory before proposing a change.
  - **FR-1.2**: A verified update must remain available to its intended audience after a new session, subject to the approved isolation rules.
- **US-2 — Shared context without pollution**: As a user operating multiple DEV agents and projects, I need shared memories to remain available where intended and unrelated project context not to be silently mixed.
  - **FR-2.1**: The existing shared Engram database remains the only active Engram database for this environment.
  - **FR-2.2**: Memory readers and writers must preserve project/scope identity; no automatic cross-project merge is allowed by this specification.
- **US-3 — Trustworthy graph and scheduled results**: As a maintainer, I need a successful job result to correspond to the expected graph output and delivery, and failures to be visible.
  - **FR-3.1**: Before implementation, the actual producer, consumer, expected output, freshness requirement, and delivery path must be established.
  - **FR-3.2**: Completion reporting must distinguish process completion from verified output and user/consumer delivery.
  - **FR-3.3**: Current overlap or duplication must be demonstrated before adding deduplication or changing jobs.
- **US-4 — Recoverability**: As a maintainer, I need backups to be restorable before relying on them for memory recovery.
  - **FR-4.1**: A backup inventory alone must not be represented as restore proof.
  - **FR-4.2**: Any restore validation must use an explicitly authorized isolated target and preserve source data.
- **US-5 — Discoverable capabilities**: As a DEV agent, I need the memory-related skills relevant to my profile to be discoverable and usable without assuming a file count proves availability.
  - **FR-5.1**: Catalog, link, profile, and load behavior must be verified on the actual in-scope surfaces before changing skill distribution.
- **US-6 — Consistent governance across agents and projects**: As a maintainer, I need the canonical global policy in `/root/AGENTS.md` applied alongside scoped `.codex/AGENTS.md` and project rules for every supported agent entrypoint and discovered first-party repo/worktree, so that memory work follows the same safety and approval boundaries.
  - **FR-6.1**: Verify the actual instructions/context-loading entrypoint for Codex, OpenCode, Gemini, Copilot, Antigravity, and Hermes; do not infer runtime loading from a document link or from another agent's behavior.
  - **FR-6.2**: Keep a Markdown inventory of every discovered first-party repository and worktree in the declared audit boundary. Mark it complete only when the boundary is reconciled; otherwise enumerate inaccessible/unidentified roots and report the inventory as blocked/incomplete.
  - **FR-6.3**: Update current-state documentation by adding dated reconciliations or correcting only stale current pointers; preserve historical handovers and provenance. Do not delete generated sources or project data without explicit human approval naming the exact files.
  - **FR-6.4**: Treat `.codex/`, `.agents/`, `.git/`, and `.aws/` as protected read-only boundaries where so configured. If required information is unavailable, stop that investigation and record the blocker; no chmod, namespace manipulation, alternate-path access, or other bypass is allowed. Guarded writes require explicit authorization for the exact target and operation.
- **US-7 — Safe rollback and recoverability**: As an operator, I need each approved change to have a reversible outcome distinct from backup validation, so that rollback does not erase user memory or history.
  - **FR-7.1**: Each approved implementation work unit must name its rollback target, expected restored behavior, and preserved state before execution.
  - **FR-7.2**: Rollback of a change and backup/restore testing are separate procedures with separate authorization and evidence; both preserve user memories, memory history, and prior configuration unless a later explicit scoped approval says otherwise.

## 4. Acceptance Criteria and Invariants

### Scenario 1 — Context available to a new session

- **Given** an in-scope DEV agent starts a new session with an identified project/workspace,
- **When** it follows the approved memory-start procedure,
- **Then** it can locate the intended current project handover and relevant shared context without reading unrelated project content or assuming an unverified runtime path.

### Scenario 2 — Approved update persists

- **Given** an authorized session makes a verified, non-sensitive memory update,
- **When** the session closes and a fresh session reads the same intended scope,
- **Then** the new session can retrieve the update, the source and timestamp are identifiable, and no unrelated project scope was overwritten.

### Scenario 3 — Shared store binding

- **Given** the environment is configured to use the existing shared Engram database,
- **When** an in-scope agent performs an approved read/write validation,
- **Then** evidence identifies the active database binding and the operation's project/scope, while no new database is created and no other memory is merged or deleted.

### Scenario 4 — Job completion and output delivery

- **Given** an in-scope memory graph job is invoked with a known input and expected output,
- **When** it completes successfully,
- **Then** the run evidence distinguishes process exit from output validation and expected consumer delivery; a failed or missing output is not reported as successful delivery.

### Scenario 5 — Backup restore proof

- **Given** an approved backup has been selected and an isolated restore target authorized,
- **When** the restore validation is performed,
- **Then** the source remains unchanged, the restored data can be read, and the result is recorded without exposing raw memory content.

### Scenario 6 — Duplicate producer handling

- **Given** investigation identifies multiple active producers for the same intended memory job,
- **When** the specification is approved and a later design defines safe ownership,
- **Then** the chosen behavior prevents unintended concurrent or repeated effects and preserves a clear, observable owner; absence of current evidence does not trigger job deletion.

### Scenario 7 — Skill visibility

- **Given** an in-scope profile is expected to use a memory-related skill,
- **When** its catalog and load path are checked on that runtime surface,
- **Then** the skill is discoverable and available, or the specific missing link is reported; aggregate skill count alone is insufficient proof.

### Scenario 8 — Global and project instructions across agent entrypoints

- **Given** a supported Codex, OpenCode, Gemini, Copilot, Antigravity, or Hermes session enters a discovered first-party repo/worktree,
- **When** its actual instruction/context-loading entrypoint and governing project instructions are inspected,
- **Then** the audit records what is loaded, from which scope, and what is merely linked; no agent is declared compliant based only on another runtime or on a document's assertion.

### Scenario 9 — Repository/worktree inventory has an explicit boundary

- **Given** a bounded first-party repository/worktree audit,
- **When** roots are enumerated and access is checked within the authorized boundary,
- **Then** the Markdown audit lists each discovered root and marks inventory complete only when the declared boundary is reconciled; inaccessible or unidentified roots are named as blocked/incomplete, never omitted to imply completeness.

### Scenario 10 — Protected source or metadata is unavailable

- **Given** required evidence is within a protected read-only `.codex/`, `.agents/`, `.git/`, or `.aws/` surface,
- **When** the authorized read path cannot access it,
- **Then** the audit records the limitation and stops that investigation; no permission, namespace, or alternate-path workaround is attempted.

### Scenario 11 — Change rollback preserves user state

- **Given** a later approved implementation work unit has named its rollback outcome and preserved state,
- **When** that unit is rolled back under its own authorization,
- **Then** the agreed behavior/configuration is restored without deleting user memories, their history, or prior configuration; any backup restore is separately authorized and validated.

### Invariants

- Human approval is required before technical design and before any destructive, migratory, service, or production action.
- Preserve the single shared Engram database; do not create an alternate active store or automatically merge project memories.
- Keep secrets, credentials, raw memory dumps, and unnecessary personal data out of Git and Markdown.
- Existing user data and unrelated repository changes remain untouched.
- Unknown or unverified behavior is reported as unknown, not silently converted into a requirement or root cause.

## 5. Dependencies and Operational Considerations

- Before technical design, resolve or explicitly record as blocked the read-only scope inputs: intended DEV agent/profile set, discovered repository/worktree boundary, actual entrypoints, and read-only invocation/consumer facts needed to choose a safe design. The five roots in the baseline are not asserted to be exhaustive.
- Write/read round trips, restore exercises, failure injection, configuration changes, and other side-effecting validation are not prerequisites to drafting design. An approved design must name their exact targets, side effects, permissions, and rollback outcomes before those checks run.
- Existing Hermes native memory, Engram, graph generation, scheduled jobs, backup routines, and skill catalogs are dependencies; their current binding and behavior are not fully established.
- Any future design must describe failure visibility, backup/restore safety, project isolation, concurrency, observability, maintenance ownership, and rollback for each approved implementation unit.
- No new dependency, binary, active database, service, or remote access is authorized by this draft.

## 6. Approval

- **Specification approval**: Approved by the user on 2026-10-08.
- **Technical design**: Approved by the user on 2026-10-08 (Adelante).
- **Implementation**: Only safe, exact scopes in 03-tasks.md may proceed under the approved spec/design; unsafe or protected operations remain blocked until separately authorized.


## Approval Status Update (2026-10-08)

- Specification: approved by the user.
- Technical design: approved by the user (Adelante).
- Task breakdown: recorded in `03-tasks.md`; implementation has not started.
- Safe implementation remains bounded to exact verified scopes; protected and unsafe operations require separate authorization.
