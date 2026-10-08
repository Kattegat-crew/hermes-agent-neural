# Memoria DEV — Executable Task Plan

**Status:** Approved plan; implementation has not started. Tasks are independently gated by surface. `[ ]` means unfinished even when READY. This document does not authorize runtime, protected, or production actions.

## Operating rules
- Safe exact work may proceed once its own evidence/checks are established. This does not authorize protected writes, permission changes, remote work, DB mutation/merge/deletion, live jobs, service changes, or production rollout.
- Do not alter owner/mode or bypass access controls. Permission denial remains a blocker. Preserve both Engram stores and existing memories/configuration; no replacement DB or merge.
- Rollback is per approved code/config unit: revert its code commit or restore its specifically preserved config snapshot. DB restore is a separate, isolated, explicitly authorized exercise, never an undo for memory deletion/merge.
- For behavior changes, add a deterministic offline test first and observe RED, then implementation/GREEN, then refactor. Tests must not execute the deployed wrapper or touch live graph/DB state.
- Commands below are read-only discovery or named offline tests, not blanket acceptance. Partial inventory is not full acceptance. Do not mark a task/phase complete without observed output and applicable evidence.

## Tasks

### T01 — Record bounded known repository/worktree inventory (P1)
- [ ] **READY — read-only, bounded inventory only.** Five known product Git roots can be checked; tools/worktrees are not exhaustive.
- **Depends on:** none.
- **Run:** `for p in /opt/hermes-agent /opt/golden-game-landing /opt/paradise-casino/paradise-casino-landing /opt/marketing-campaign-generator /opt/ai-platform; do git -C "$p" rev-parse --show-toplevel; git -C "$p" worktree list --porcelain; done`
- **Acceptance:** retain dated output and mark unchecked tool repos/worktrees unknown. `/opt/hermes-agent-data` is a separate runtime workspace, not one of these Git roots; do not bypass its access boundary. This does not complete P1.

### T02 — Inspect known instruction entrypoints and map uncertainty (P2/P3)
- [ ] **READY — read-only checks at known project paths; unknown loaders stay UNKNOWN/BLOCKED.** Managed generator provenance/update owner and some adapters are unresolved.
- **Depends on:** none for known-path checks; expand matrix as T01 evidence arrives.
- **Run:** `git -C /opt/hermes-agent ls-files -- AGENTS.md .codex .config/opencode GEMINI.md system.md agent/system_prompt.py agent/prompt_builder.py`
- **Acceptance:** record file/source evidence per entrypoint; existing documents are not proof of runtime loading. Copilot instruction state/config parsing, Antigravity loading, generator provenance, and uninspected adapters remain unknown. Protected `.codex`, `.agents`, `.git`, `.aws` are read-only absent separate authorization; no chmod, symlink, namespace workaround, or generated-source deletion.

### T03 — Reconcile configured memory paths and access evidence (P4)
- [ ] **READY — sanitized read-only config/metadata inspection. Active bindings and all writes remain BLOCKED.** Parent reports Hermes `os.access` read/write true for both paths; this does not prove live service use.
- **Depends on:** none.
- **Run:** `stat -c '%a %U:%G %n' /opt/hermes-agent-data/config.yaml /opt/hermes-agent-data/profiles/roshi/config.yaml /opt/hermes-agent-data/profiles/vigia/config.yaml /root/.engram/engram.db /opt/hermes-agent-data/home/.engram/engram.db`
- **Acceptance:** record only sanitized path/owner/mode/configured-path facts; preserve both distinct DBs. Canonical DB observed mode `666`, parent directory `777`; do not automatically change permissions. No secrets, write round-trip, broadened `/root` traversal, or active-binding inference from config/access alone.

### T04 — Confirm graph source/artifact facts without selecting a path change (P5)
- [ ] **READY — read-only source-contract analysis from parent evidence; canonical path change remains BLOCKED.**
- **Depends on:** none.
- **Run:** `git -C /opt/hermes-agent ls-files -- scripts/brain_graph_update_wrapper.sh scripts/brain_graph_update_inner.sh tools/memory_graph.py`
- **Acceptance:** parent-audited producer writes `graphify-out/graph.json`; consumer prefers `graphify-out-v2/graph.json`; runtime source is outside this Git root and no tracked copy exists. Verify schema/consumers/provenance before path choice. Mtimes do not prove freshness. Do not inspect via alternate path or execute generator.

### T05a — Add an offline versioned wrapper contract (P6; independent source-only unit)
- [ ] **IMPLEMENTED; offline verification recorded, pending parent work-unit commit. No deployed/runtime change.** New versioned wrapper source is not proof of deployed provenance.
- **Depends on:** none of T01–T04, T06, or T07.
- **Targets:** add `scripts/brain_graph_update_wrapper.sh`; first add `tests/cron/test_brain_graph_wrapper.py`. Deployed `/opt/hermes-agent-data/scripts/brain_graph_update_wrapper.sh` is outside this Git project; do not execute/edit it.
- **Run after writing test/source:** `pytest -q tests/cron/test_brain_graph_wrapper.py`; then `pytest -q tests/cron/test_cron_no_agent.py`.
- **Acceptance:** offline tests simulate success, non-zero, unavailable inner result, `EXTRACT_ERROR`, signal cleanup of a TERM-resistant process group, concurrency and private per-run evidence. The wrapper returns meaningful status, bounds termination with TERM then KILL and `timeout --kill-after`, and uses no recursive `chown`/`chmod`. Keep tests/code together. Leave graph output selection, runtime config, scheduler, live deployment and delivery untouched; rollback by reverting source/test unit, never by restoring user memory.
- **Observed verification:** initial TDD RED: 8 expected failures because the versioned wrapper was absent; GREEN after first implementation: 8 passed. Correction RED: TERM-resistant process-group test timed out against the unbounded wait; GREEN after bounded TERM→KILL cleanup and `timeout --kill-after=5s`: `PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider tests/cron/test_brain_graph_wrapper.py tests/cron/test_cron_no_agent.py` — 26 passed. `bash -n scripts/brain_graph_update_wrapper.sh`, `git diff --check`, and authored-file whitespace checks passed. No pre-implementation baseline for `test_cron_no_agent.py` was captured. The redacted summary treats `EXTRACT_ERROR` as failure, preserves the inner return code, and reports process completion/no-change only—not freshness or delivery. Concurrency checks cover private per-run directories only, not graph transaction locking.

### T05b — Validate live scheduler, artifact freshness, and delivery (P6)
- [ ] **BLOCKED — no live invocation or deployment.**
- **Depends on:** T05a only if deployment is considered, plus separate evidence and authorization for exact scheduler/artifact targets.
- **Required evidence:** scheduler identity/service account, invocation, overlap/idempotency, exit propagation, output destination, artifact validation/freshness, downstream observer. `status=ok` does not establish delivery.
- **Acceptance:** offline proof first; live run/deployment requires separate exact approval and named rollback. Do not assert duplicate jobs or successful delivery without current evidence.

### T06 — Map backup coverage; keep restore separately authorized (P6/P9)
- [ ] **READY — read-only backup-scope discovery. Restore remains BLOCKED.** Independent of memory binding and wrapper work.
- **Run (source only; do not inspect backup data):** `sed -n '296,345p' hermes_cli/backup.py`; `sed -n '911,927p' hermes_cli/backup.py`
- **Acceptance:** document caller, declared paths, retention/exclusions, unknowns without secret contents. Provider paths do not prove restore success. Isolated restore requires its own target, permissions, approval, and rollback.

### T07 — Map profile-scoped skills and producer evidence (P7)
- [ ] **READY — read-only inventory; runtime visibility remains unverified.** Independent of T05a.
- **Run:** `git -C /opt/hermes-agent ls-files -- 'skills/**' 'profiles/**'; find /opt/hermes-agent-data/profiles -maxdepth 2 -type d -print`
- **Acceptance:** record only repository path metadata and runtime profile directory names; do not dump profile content or use counts as proof of skill availability/duplicates. If runtime metadata access is denied, mark this part BLOCKED and do not try an alternate path. No deletion/live profile test without exact approval.

### T08 — Dispatch independently proven units by surface (P2–P7)
- [ ] **READY — routing rule, not blanket implementation gate.** A narrow unit can proceed when its own target, test, access, owner, risk, rollback are established; unresolved fleet/backup/skill/graph-path/DB work does not block unrelated offline source work.
- **Dependencies:** each unit only depends on its own evidence. T05a is independent and dispatchable; protected writes, DB mutations, restores, and live rollout remain separately BLOCKED.
- **Acceptance:** future worker uses test-first behavior changes and records exact evidence and per-unit code/config rollback. No DB undo, broad chown/chmod, or new DB. T08 is not a proxy for all implementation.

### T09 — Run scoped integration and agent × repository/worktree acceptance (P8)
- [ ] **BLOCKED — await applicable implementation, bounded inventory, and safe test paths.**
- **Depends on:** each in-scope unit/proof; T01/T02 matrix evidence. No exhaustive inventory claim.
- **Acceptance:** six named agents across every discovered in-scope root/worktree, with observed result or explicit unknown/blocked state. Offline fixtures precede authorized live effects. No production rollout.

### T10 — Reconcile docs, Engram mirror, and closure evidence (P9)
- [ ] **BLOCKED — only after applicable implementation and verification.**
- **Depends on:** completed in-scope units and T09 where applicable.
- **Acceptance:** preserve historical handover; record dated commands/results and gaps; parent owns full Engram task mirror/commits. No task/phase complete without proof. No push, PR, merge without explicit approval.

## Dependencies and ready work

T01, T02, T03, T04, T06, T07 are independent read-only discovery tasks within stated limits. T05a is independent offline source/test work. T05b depends on T05a only if deployment is considered, plus separate live evidence/authorization. T08 dispatches each validated unit independently and does not wait for all discovery. T09/T10 remain gated by applicable proof.

## Delivery slices (local only)
- **Slice A:** approved baseline + spec; local commit `23945c6ec16a` (`docs(memory): record approved DEV memory specification and baseline`), exactly 229 additions. Documentation milestone, not P1 completion.
- **Slice B:** approved design + task breakdown + tracker/index/current-memory reconciliation. Measure additions + deletions against current HEAD; exclude unrelated TikTok.
- **Future slices:** one coherent behavior-backed unit with tests per commit; recalculate boundaries when ready. No PR/push/merge authorized or created.
- Full feature forecast remains unassessable until live/protected scope is resolved.

## Current next step

Parent owns the T05a work-unit commit. T05b deployment/live validation remains blocked pending separate evidence and authorization. Do not execute the deployed wrapper, live job, DB operation, permission change, or production deployment.
