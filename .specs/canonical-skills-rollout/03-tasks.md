# Implementation Tasks: Canonical Skills Rollout & Hardening

* **Associated Spec**: [01-spec.md](./01-spec.md)
* **Associated Design**: [02-design.md](./02-design.md)
* **Status**: In Progress

---

## Execution Guidelines
1. **TDD First**: Write tests that fail before implementing feature code.
2. **Atomic Verification**: Run the specified command after completing each task.
3. **No Batching**: Never check off a task without executing its verification command.

---

## Task Checklist

### Phase 1: Security Test Scaffolding & Wizard Hardening
- [ ] **Task 1.1**: Author isolated test suite `tests/test_template_hardening.sh` verifying symlink rejection, key regex, quote escaping, and atomic replacement.
  - *Target Files*: `/opt/hermes-agent/tests/test_template_hardening.sh`
  - *Verification*: `bash /opt/hermes-agent/tests/test_template_hardening.sh` (fails on current template).
- [ ] **Task 1.2**: Update `write_env()` in `wizard/template.sh` to implement the hardened specification.
  - *Target Files*: `/opt/hermes-agent/.agents/skills/wizard/template.sh` and `/opt/hermes-agent/skills/software-development/wizard/template.sh`
  - *Verification*: `bash /opt/hermes-agent/tests/test_template_hardening.sh` (must pass 100% of test cases).
- [ ] **Task 1.3**: Propagate hardened `template.sh` across all repositories and CLI roots.
  - *Target Files*: All 9 instances across `/opt/` and `/root/`.
  - *Verification*: `for f in $(find /opt /root -name "template.sh" -path "*/wizard/*"); do grep -q "symbolic link" "$f" || echo "Missing in $f"; done`

### Phase 2: Fleet Catalog Frontmatter Syntax Repairs
- [ ] **Task 2.1**: Identify exact syntax errors across the 26 failing skills in `/opt/hermes-agent/skills/`.
  - *Target Files*: The 26 identified files in `skills/`.
  - *Verification*: Run diagnostic script collecting failure reasons.
- [ ] **Task 2.2**: Repair delimiter closures (`---`), invalid YAML syntax, and formatting while preserving original skill language and prompt instructions.
  - *Target Files*: The 26 identified files.
  - *Verification*: Run `_validate_frontmatter` on all 574 files. (Must return 0 errors).

### Phase 3: Worktree Isolation & Documentation
- [ ] **Task 3.1**: Validate that worktrees remain isolated and that no `.atl` symlinks point to main checkouts.
  - *Verification*: Check absence of cross-worktree symlinks in `.atl`.
- [ ] **Task 3.2**: Update `PROJECT_MEMORY.md` in all 5 repositories to record the hardened skills architecture.
  - *Target Files*: `/opt/<repo>/PROJECT_MEMORY.md` (hermes-agent, ai-platform, golden-game-landing, marketing-campaign-generator, paradise-casino-landing).
  - *Verification*: Verify `PROJECT_MEMORY.md` diffs.

### Phase 4: Final Verification, Conventional Commits & Engram Recording
- [ ] **Task 4.1**: Run Tier 1, Tier 2, and Tier 3 verification commands and capture traces.
  - *Verification*: `bash tests/test_template_hardening.sh` && Python catalog audit script.
- [ ] **Task 4.2**: Commit changes cleanly using Conventional Commits with strictly zero AI co-authorship.
  - *Verification*: `git status` clean across all repos.
- [ ] **Task 4.3**: Persist closure observation in Engram (`neuralops` / `hermes-agent`).
  - *Verification*: `engram search "Canonical Skills Rollout"`.
