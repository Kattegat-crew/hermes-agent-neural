# Technical Design: DEV Memory Continuity and Delivery

**Status:** Approved — user sign-off “Adelante” on 2026-10-08
**Specification:** `.specs/memoria-dev/01-spec.md` (user-approved 2026-10-08)
**Baseline:** `.specs/memoria-dev/00-baseline.md` (observed 2026-10-08)
**Implementation boundary:** Only safe, exact scopes represented by the approved task plan may proceed. Protected or unsafe operations remain blocked pending their required approvals. No runtime, service, database, scheduled-job, or production operation was executed during document authoring.

## 1. Design intent and boundary

Use the existing native Hermes memory, the one intended shared Engram store, existing graph/job/backup mechanisms, and profile-scoped skills. First establish their real bindings and contracts; then make only the smallest approved corrections supported by evidence. Keep project-local continuity distinct from shared, explicitly scoped Engram knowledge. Treat the six named agents and discovered repository/worktree inventory as an audit matrix, not as proof that all runtimes have identical instruction loaders.

The five repositories in the baseline are confirmed product roots, not an exhaustive universe. `/opt/hermes-agent-data` is a separate runtime workspace and is not a repository in that count. Expand inventory only through an authorized, bounded discovery process. Protected `.codex/`, `.agents/`, `.git/`, and `.aws/` surfaces remain read-only where configured; an inaccessible path is a recorded blocker, never an invitation to use another path or alter permissions.

## 2. Proposed component boundaries

| Concern | Existing boundary to retain | Proposed contract / evidence before any change |
|---|---|---|
| Global and project policy | `/root/AGENTS.md` as intended canonical global contract; scoped agent configuration and repository instructions as overlays. | For Codex, OpenCode, Gemini, Copilot, Antigravity, and Hermes, record the actual loader entrypoint, loaded files, scope precedence, and linked-but-not-loaded files. A document's existence or link is not evidence of runtime loading. Preserve historical handovers; update current pointers with dated reconciliation. Do not assert all agent/repository combinations comply until the inventory and matrix support it. Managed-rule generator/source provenance and regeneration/update ownership are unknown; do not edit generated/managed instructions until that source and safe update process are identified and authorized. |
| Native project continuity | Existing Hermes `MEMORY.md`, `USER.md`, and prompt construction. | Verify the selected profile, project/workspace, effective character budget, and inclusion path. Measure text length in characters when applying character limits; byte sizes are only storage metadata. Keep user and project scope distinct and avoid copying whole memory files into Markdown. |
| Shared cross-agent memory | Existing policy-designated `/root/.engram/engram.db`. | Verify live provider binding and safe read/write access as the service identity before choosing alignment. Default/Roshi/Vigia configuration currently names `/opt/hermes-agent-data/home/.engram/engram.db`, a different inode; this is configured state, not live-process proof. Preserve both stores and their divergent history. No third active DB, implicit merge, move, or deletion. If the canonical store cannot be used safely, pause for a human architecture decision rather than loosening `/root` permissions. |
| Graph production and consumption | Existing runtime producer, graph artifacts, and consumer. | Establish input source, actual invoked producer, output schema/path, every consumer, freshness watermark, and error propagation. Parent inspection found the inner producer writes `brain/graphify-out/graph.json`, while `tools/memory_graph.py:11` prefers `brain/graphify-out-v2/graph.json`; both files exist. This path mismatch is not yet proof of stale or failed delivery. Validate provenance, schema compatibility, and consumer expectations before selecting one canonical artifact. Preserve both existing outputs until an exact deletion/retention decision is approved. |
| Scheduled job and wrapper | Existing scheduler/job and wrapper; no replacement scheduler proposed. | A reported run should distinguish invocation and process exit from validated artifact and consumer delivery. Parent inspection found the wrapper captures the inner return code (`scripts/brain_graph_update_wrapper.sh:29–39`) but exits 0 unconditionally (`:41–48`); impact on the observed scheduler or consumer remains unverified. Future correction, if approved, must propagate a meaningful failure and retain evidence of the inner result without representing mere process completion as delivery. Inspect current scheduler overlap/idempotency controls before designing concurrency changes. Never execute the wrapper during this documentation task. |
| Backups and recovery | Existing backup routine and its configured paths. | Inventory what the active provider actually backs up and prove restore only in an explicitly authorized isolated target. The observed backup provider backs up its active provider's `backup_paths`; this does not prove coverage of all memory stores or restoreability. A work-unit rollback is separate from backup restore and must name the exact behavior/configuration to revert while preserving user memories, memory history, and previous configuration. |
| Skills | Existing profile-specific skill discovery and loading. | Check catalog/list, search, link, and load behavior on the actual profile. Skills are on-demand and profile-scoped; total file count does not show availability. Reuse an existing relevant skill where present; do not create duplicates or redistribute skills based on counts alone. |

## 3. Data flow and authority

1. A supported agent session resolves its project/workspace and reads only the actual global and project instructions supplied by its loader. The audit records loader evidence and any unavailable entrypoint per agent; `/root/AGENTS.md` is not assumed to be an ancestor policy automatically loaded by a process rooted under `/opt`.
2. Native Hermes memory remains the project/session continuity surface where the existing runtime uses it. A memory update is not considered durable merely because a tool returned success: a later authorized read must identify the intended profile/project scope and update provenance.
3. Engram remains the shared cross-agent store at the one policy-designated database only after active binding and service-identity access are verified. Project isolation and scope labels remain required. Configuration path alignment is not itself permission to migrate data.
4. Graph/job output is a derived operational view, not a source of truth for native or Engram memories. A future run record should identify input/source watermark, process outcome, artifact validation, and downstream consumption as separate facts. No freshness threshold or consumer-delivery event is assumed until the owner specifies and evidence identifies it.
5. Backup evidence records source scope, timestamp, and validation result without raw memory contents. Restore evidence is gathered only in an approved isolated target and never substitutes for a rollback plan.

No new service, database, dependency, executable, API, or orchestration layer is proposed. If the existing mechanisms cannot provide required evidence, document the specific gap and bring a bounded decision to the human before adding infrastructure.

## 4. Observable outcome model

For any future memory graph job, distinguish these stages rather than collapsing them into one `ok`:

| Stage | Minimum evidence | Failure interpretation |
|---|---|---|
| Invocation | Job identity, invocation time, selected profile/workspace, and input/source watermark where available. | Missing invocation evidence means the job was not verified as run. |
| Process | Inner operation exit/result preserved by wrapper and visible to scheduler/operator. | Non-zero or unavailable result is a failed/unknown run, not success. |
| Artifact | Expected output path, parse/schema validation, and source watermark or equivalent freshness evidence. | A present but invalid or uncorrelated old artifact is not a successful update. A valid no-change result must be distinguishable from failure. |
| Delivery | Identified consumer and evidence it read/accepted the validated artifact, if delivery is part of the requirement. | Do not claim delivery from file existence, mtime, process exit, or scheduler status alone. |

The exact freshness policy, no-change semantics, job concurrency mechanism, and delivery observer remain unresolved inputs. They must be selected from the real consumer contract, not guessed from current timestamps. Do not add persistent logs or a new state store unless a concrete need and safe retention/access design are approved.

## 5. Instruction and repository audit model

Create a Markdown audit (within the approved documentation scope) with one row per supported agent × discovered first-party repository/worktree. For each row record: canonical root and worktree identity; governing global/project instructions; actual loader evidence; precedence; whether the file is loaded, only linked, inaccessible, or unknown; and the observed outcome. Name the inventory boundary and mark it complete only when reconciled. An inaccessible or unidentified repository/worktree remains a visible blocked row; the current five-root list cannot be labeled exhaustive.

Known loader evidence is intentionally uneven: Hermes has source evidence for AGENTS discovery from Git root to cwd, `.hermes.md`/`HERMES.md` precedence, and separate SOUL handling; Codex uses configured model instructions plus managed AGENTS; OpenCode configuration has global AGENTS but no observed instructions field. Gemini's `GEMINI.md`/`system.md` names were observed as candidate instruction files, but this does not prove either file is loaded or that a context override is active. Copilot's user instructions were absent and config parsing failed; Antigravity's loader remains unknown. These candidate facts require current-path verification for the eventual audit, and none proves universal runtime adherence. Policy files describe obligations; source/config evidence determines loading.

Current governance reconciliation must preserve prior handover text and provenance. Add a dated current-state note or correct only a demonstrably stale current pointer. Do not delete generated sources or data without explicit approval naming exact targets. The two unresolved architecture links in Hermes and Golden remain unresolved until replacement targets are evidenced; this memory design does not authorize unrelated architecture cleanup.

### Candidate file map — evidence inventory, not edit authorization

Paths below identify audit candidates and known evidence only. `Read/status` records what was established in the bounded audit; `operation` is a proposed future audit or correction, not permission to write. `Owner` means filesystem owner unless it says document/configuration ownership. Unknown values stay unknown; protected-path read denial cannot be worked around. Exact source paths for managed-rule generation and exact native profile config files were not established, so they are deliberately not guessed.

| Root / candidate | Owner, access, and read status | Proposed operation / blocker |
|---|---|---|
| `/root/AGENTS.md` (global contract) | Read and reviewed; intended canonical global source. | Read-only comparison with each actual agent loader; no change authorized. |
| `/root/.codex/AGENTS.md`, `/root/.codex/engram-instructions.md`, `/root/.codex/config.toml` (Codex candidates) | Managed/configured surfaces were observed; exact generator provenance and safe update owner are unknown. Treat `.codex/` as protected read-only. | Verify precedence and configured instruction filename read-only. Do not edit managed files until generator/source, regeneration path, and owner are identified and exact write authority is granted. |
| `/root/.config/opencode/AGENTS.md`, `/root/.config/opencode/` config (OpenCode candidates) | Global AGENTS/configuration were observed; exact config filename and loader linkage require revalidation. Access/owner for any proposed change not established. | Read-only loader/config trace; no writes. |
| `/root/.gemini/GEMINI.md`, `/root/.gemini/system.md` (Gemini candidates) | Names were observed; effective loading and context override are unverified. | Verify actual read path and precedence; no writes. |
| Copilot user-instructions/config locations | User instructions were reported missing and config parsing failed; exact locations/read state are not sufficiently established here. | Identify actual entrypoint/config through an authorized read; blocked until path and loader are known. No speculative file creation. |
| Antigravity instruction/config locations | Loader, exact paths, owner, access, and read status are unknown. | Read-only discovery if authorized; no path or mutation assumed. |
| Each confirmed repo: `/opt/hermes-agent`, `/opt/golden-game-landing`, `/opt/paradise-casino/paradise-casino-landing`, `/opt/marketing-campaign-generator`, `/opt/ai-platform` — root `AGENTS.md`, `PROJECT_MEMORY.md`, `ARCHITECTURE.md` candidates | Bounded governance audit covered six active Markdown docs per repo and 142 local links overall. Host ownership proof covered the five documentation files in Hermes and `.git`; do not generalize those ownership results to every repository/path. | Read-only comparison and dated reconciliation only after loader evidence; any write requires exact target approval and owner/access check. Five roots are not exhaustive. |
| `/opt/hermes-agent/agent/skills_registry.py` and `/opt/golden-game-landing/src/utils/scrollAnimations.js` (broken-link targets) | Target paths were unresolved from Hermes `ARCHITECTURE.md:63` and Golden `ARCHITECTURE.md:72`; existence/replacements, owners, and access are unknown. | No edit or replacement. Trace source only if separately authorized; preserve the broken references as gaps until evidence identifies the right target. |
| `/opt/hermes-agent-data/scripts/brain_graph_update_wrapper.sh`, `scripts/brain_graph_update_inner.sh`, `tools/memory_graph.py` (runtime code candidates) | Parent source inspection read the wrapper and producer/consumer. This writer's direct read was denied; ownership and managed-source provenance are unknown. | Treat as evidence only; do not execute or edit. Identify generator/provenance and safe DEV test owner before any future change. Wrapper has recursive ownership/mode side-effect hazards; never invoke it as a test. |
| Native profile configuration files for default/Roshi/Vigia | Configured DB value is known, but exact config filenames, owner/access, and live process binding are not established in this audit. | Verify exact path and service identity read-only before proposing a config correction. No config write or permission broadening. |
| `/root/.engram/engram.db` and `/opt/hermes-agent-data/home/.engram/engram.db` | Distinct database inodes and divergent stores were reported; live provider binding and service-identity access remain unverified. Do not broaden `/root` traversal or relax secret permissions. | Preserve both. Verify safe access to the policy-designated shared DB before any config alignment; otherwise pause for a human choice. No merge, move, delete, third DB, or DB rollback. |

### Selected approach and alternatives

| Decision area | Selected direction for this draft | Alternative and trade-off |
|---|---|---|
| Instruction governance | Keep one canonical global contract and thin, verified agent/project overlays; verify each loader. | Copy full rules into every agent and repository, which may make an isolated loader simpler but increases drift and multiplies update/ownership work. |
| Engram divergence | Preserve both stores, establish live binding and safe service-identity access, then consider a narrowly scoped config alignment to the existing canonical DB. | Merge/migrate both stores, which could reconcile divergent content but risks losing provenance, mixing project scopes, and exceeding current authority. Alignment itself remains blocked until access and divergence are understood. |
| Graph path | Validate the existing producer, schemas, and all consumers, then select a canonical existing artifact without deleting the other. | Prefer the v2 path and overwrite/retire the legacy artifact immediately; this is simpler only if consumers are proven compatible, which is not yet known. |

For any later approved work unit, rollback targets the exact changed code or configuration: revert that unit's code commit or restore a separately preserved, permissioned pre-change configuration snapshot, then verify the prior behavior. This is not a database undo. Do not roll back by deleting or restoring over user memories/history. Any backup snapshot creation and any backup restore require their own scoped authorization and isolation; if safe snapshot/ownership cannot be established, the unit is not safely reversible and must not proceed. Unknown managed-source ownership remains a blocker, not an invitation to change ownership.

## 6. Validation and rollout proposal

Validation remains future work and requires the named target, exact verification command, and scoped permission for any side effect. Design approval does not approve protected or unsafe operations.

1. **Read-only discovery first:** verify agent/profile set, repository/worktree boundary, actual instruction loaders, native memory readers/writers, live Engram binding, graph consumers, scheduler invocation contract, backup scope, and skill catalog access. Record unavailable facts rather than bypassing permissions.
2. **Offline behavior tests before runtime effects:** if implementation changes behavior, add focused deterministic tests with temporary/mock inputs for scope selection, path choice, inner return-code propagation, valid no-change versus stale/failed output, and absence of cross-project mixing. Observe meaningful failing cases before implementing; no artificial test is required for passive docs.
3. **Permissioned DEV validation:** only after approval, perform narrowly scoped read/write continuity checks and job/output checks on an identified DEV profile. Avoid actual user memory contents in logs. Keep any restore exercise separate and use a separately authorized isolated target.
4. **Matrix and regression evidence:** evaluate the six named agents against each in-scope repository/worktree for actual loaded policy and memory behavior. Include blocked/unknown results; do not turn them into pass. Expand beyond the five confirmed repositories only when inventory evidence supports the boundary.
5. **Bounded rollout:** stage one reversible DEV work unit at a time. Each unit names exact paths/configuration, expected result, rollback target and preserved state, validation command/evidence, and required permissions. Observe the result before proceeding. No production rollout is included.

No source tests, runtime smoke tests, DB operations, job invocations, restores, service restarts, permission changes, or remote operations were executed to produce this design draft.

## 7. Phasing and dependencies

| Phase | Design implication / exit evidence |
|---|---|
| P1 — Baseline | Bounded baseline exists; do not call inventory exhaustive or phase complete until required roots and runtime facts are reconciled. |
| P2 — Protection and SDD governance | Retain global/project policy boundaries, confidentiality, explicit deletion scope, and approval gates. Protected-path inability remains a blocker. |
| P3 — Instruction alignment and SDD delivery | Verify real loaders and maintain the agent × repository/worktree audit; preserve history and avoid generated-source deletion absent exact approval. |
| P4 — Native memory and Engram | Establish effective limits in characters, project/profile isolation, live Engram binding, and safe canonical DB access; stop if access requires weakening permissions. |
| P5 — Graph | Resolve producer/consumer artifact contract and path provenance before selecting a canonical path or changing outputs. |
| P6 — Scheduled jobs | Verify invocation, return-code propagation, overlap/idempotency, artifact status, freshness, and delivery semantics. |
| P7 — Skills and duplication | Verify profile-specific discovery/load paths and active producers; no count-based conclusions or deletion. |
| P8 — End-to-end | Collect matrix evidence across six named agents and all discovered in-scope repositories/worktrees; record unknown/blocked outcomes. |
| P9 — Closure | Reconcile dated docs and Engram mirror, report observed checks and residual gaps, and leave delivery decisions to ordinary repository policy. |

P4–P7 depend on read-only discovery and then explicitly authorized scoped validation. P8 depends on a bounded inventory and functioning test/access paths. P9 cannot claim completion while material gaps or approval gates remain. No phase is completed by this design document.

## 8. Decisions still required before implementation

- Design approved by the user on 2026-10-08 (Adelante); the task breakdown is recorded in 03-tasks.md.
- The intended DEV agent/profile set and the declared, reconciled repository/worktree audit boundary.
- The active service identity and live binding for native and Engram operations; whether safe access to the canonical shared DB is possible without permission changes.
- Graph schema, expected canonical output path, consumer set, freshness/no-change contract, and who observes delivery.
- The exact scheduler ownership/overlap behavior and acceptable run evidence/retention; no duplicate job has been established.
- Backup coverage needed and separately authorized isolated restore target; no restore proof exists.
- Per-profile skill expectations and actual catalog/load evidence.
- Exact implementation unit scopes and rollback targets after the above evidence is available.

These remain gates, not assumptions. The task plan records unresolved inputs as blocked and requires exact paths, access, and verification before a task is activated. Do not bypass protected boundaries; destructive, privileged, database, service, restore, and production actions require their own explicit scoped authorization.

## 9. Approval and Delivery

- **Independent offline unit:** the approved plan permits a separate repository-owned wrapper/test unit at `scripts/brain_graph_update_wrapper.sh` and `tests/cron/test_brain_graph_wrapper.py`. These files are not tracked source and would not establish deployed provenance. It may test exit propagation and private per-run evidence without changing graph paths, runtime config, scheduler, or deployment.
- Parent reports Hermes executor read/write access to both distinct Engram DB paths, but live service binding remains unknown. The policy DB was observed mode `666`, its containing directory `777`; no automatic permission changes are authorized. Native RDD status access was refused with PermissionDenied; mode remains unknown and must not be toggled or bypassed.

- **Design approval**: Approved by the user on 2026-10-08 (Adelante).
- **Delivery strategy**: Feature-branch-chain approved by the user on 2026-10-08 (Aprobado). This records local slice boundaries only; no PR, push, or merge was created or authorized.
- **Implementation**: Follow the gated tasks in 03-tasks.md. Unsafe/protected operations remain individually blocked until separately authorized.
