# Implementation Tasks: Canonical Skills Rollout & Hardening

* **Associated Spec**: [01-spec.md](./01-spec.md)
* **Associated Design**: [02-design.md](./02-design.md)
* **Status**: Completed
* **Completed At**: 2026-10-20
* **Peer Audit**: Codex (#2165, #2166)

---

## Execution Guidelines
1. **TDD First**: Write tests that fail before implementing feature code.
2. **Atomic Verification**: Run the specified command after completing each task.
3. **No Batching**: Never check off a task without executing its verification command.

---

## Task Checklist

### Phase 1: Security Test Scaffolding & Wizard Hardening
- [x] **Task 1.1**: Author isolated test suite `tests/test_template_hardening.sh` verifying symlink rejection, key regex, quote escaping, and atomic replacement.
  - *Target Files*: `/opt/hermes-agent/tests/test_template_hardening.sh`
  - *Verification*: `bash /opt/hermes-agent/tests/test_template_hardening.sh` (failed on unhardened template, proved TDD RED).
- [x] **Task 1.2**: Update `write_env()` in `wizard/template.sh` to implement the hardened specification.
  - *Target Files*: `/opt/hermes-agent/.agents/skills/wizard/template.sh` and `/opt/hermes-agent/skills/software-development/wizard/template.sh`
  - *Verification*: `bash /opt/hermes-agent/tests/test_template_hardening.sh` (passed 100% of test cases).
- [x] **Task 1.3**: Propagate hardened `template.sh` across all repositories and CLI roots.
  - *Target Files*: All 9 instances across `/opt/` and `/root/`.
  - *Verification*: `for f in $(find /opt /root -name "template.sh" -path "*/wizard/*"); do grep -q "symbolic link" "$f" || echo "Missing in $f"; done`
- [x] **Task 1.4**: Address Codex audit finding (#2165) by rejecting directory targets in `write_env()` and using destination-local temp files for guaranteed atomic rename on the same filesystem.
  - *Target Files*: `tests/test_template_hardening.sh` (added Test 5), `template.sh` in all 9 instances.
  - *Verification*: `bash /opt/hermes-agent/tests/test_template_hardening.sh` (5/5 tests passed).

### Phase 2: Fleet Catalog Frontmatter Syntax Repairs
- [x] **Task 2.1**: Identify exact syntax errors across the 26 failing skills in `/opt/hermes-agent/skills/`.
  - *Target Files*: The 26 identified files in `skills/`.
  - *Verification*: Diagnosed string concatenation defect attaching delimiter (`---`) directly to tokens without preceding newline.
- [x] **Task 2.2**: Repair delimiter closures (`---`), invalid YAML syntax, and formatting while preserving original skill language and prompt instructions.
  - *Target Files*: The 26 identified files.
  - *Verification*: Run `_validate_frontmatter` on all 574 files. (Returned 0 errors across 574/574 files).

### Phase 3: Worktree Isolation & Documentation
- [x] **Task 3.1**: Validate that worktrees remain isolated and that no `.atl` symlinks point to main checkouts.
  - *Verification*: Confirmed zero `.atl` cross-worktree symlinks; each branch preserves its standalone state.
- [x] **Task 3.2**: Update `PROJECT_MEMORY.md` in all 5 repositories to record the hardened skills architecture.
  - *Target Files*: `/opt/<repo>/PROJECT_MEMORY.md` (hermes-agent, ai-platform, golden-game-landing, marketing-campaign-generator, paradise-casino-landing).
  - *Verification*: Diffs verified and committed across all 5 repos.

### Phase 4: Final Verification, Conventional Commits & Engram Recording
- [x] **Task 4.1**: Run Tier 1, Tier 2, and Tier 3 verification commands and capture traces.
  - *Verification*: `bash tests/test_template_hardening.sh` (5/5 PASS), full catalog audit (574/574 PASS), plugin router integration probe (`fit=0.95`, `fit=0.94` PASS).
- [x] **Task 4.2**: Commit changes cleanly using Conventional Commits with strictly zero AI co-authorship.
  - *Verification*: Clean git status on skills files across all repos.
- [x] **Task 4.3**: Persist closure observation in Engram (`neuralops`).
  - *Verification*: Memory observations #2164 and #2167 saved.
