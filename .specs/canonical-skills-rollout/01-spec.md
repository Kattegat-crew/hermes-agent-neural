# Feature Specification: Canonical Skills Rollout & Hardening

* **Status**: Approved
* **Author**: Senior Architect (Antigravity) / Peer Review: Codex
* **Target Module**: `skills/`, `.agents/skills/`, `.atl/`, `tools/`
* **Created**: 2026-10-20
* **Updated**: 2026-10-20

---

## 1. Problem Statement & Motivation
* **What is the problem?**
  1. The new engineering skills (`codebase-design`, `wizard`, `code-review-and-quality`) were deployed across repositories, but the `wizard` script template (`template.sh`) possessed security vulnerabilities: following symlinks without target safety validation, lack of POSIX key format enforcement, and non-atomic file replacement.
  2. The 574-skill Hermes fleet catalog contained 26 files with broken YAML frontmatter syntax, failing native linter and frontmatter parser verification.
  3. Git worktree isolation was vulnerable to accidental shared-registry contamination if symlinked carelessly to main branches.
  4. SDD formal specification was missing for this cross-cutting VPS capability.
* **Why solve it now?**
  Securing secret management in automated scripts, maintaining full catalog parseability across all fleet tooling, and establishing immutable SDD compliance prevents security vulnerabilities, broken tool execution, and regression in future audits.

---

## 2. Goals & Non-Goals
### Goals
- [x] Harden `template.sh` in all `wizard` instances: explicitly reject symlinks for `$ENV_FILE`, validate `$key` with POSIX regex, enforce `0600` permissions, and use atomic replacement.
- [x] Provide an automated isolated bash test suite (`test_template_hardening.sh`) proving all security invariants.
- [x] Repair YAML frontmatter syntax errors in the 26 fleet skills without altering language or prompt instructions.
- [x] Maintain strict branch isolation for Git worktrees (no symlinking `.atl` to main checkouts).
- [x] Differentiate and record verification levels honestly (unit test, plugin integration test, and runtime test).

### Non-Goals (Out of Scope)
- No bulk `chown -R` across worktrees without demonstrated, reproducible `EACCES` failures.
- No cosmetic language translation of skills (preserving standard English and Spanish where authored).
- No directory syncing of Codex internal system directories (`.system/`).
- No modifications to feature branch git histories in worktrees.

---

## 3. User Stories & Functional Requirements
* **US-1 (Security)**: As an operator using `wizard`, I want secret writes to `.env` to be strictly local and atomic, so that symlink attacks or process interrupts cannot leak or corrupt credentials.
  * **Requirement 1.1**: If `$ENV_FILE` is a symbolic link (`[[ -L "$ENV_FILE" ]]`), the function must immediately abort with an error and return code 1.
  * **Requirement 1.2**: If `$key` does not conform to `^[A-Za-z_][A-Za-z0-9_]*$`, the function must abort with error code 1.
  * **Requirement 1.3**: The temporary file must be created with mode `0600` and moved atomically (`mv -f`) to `$ENV_FILE`.
* **US-2 (Catalog Integrity)**: As a fleet agent or router, I want all 574 `SKILL.md` files to be valid YAML mapping frontmatters, so that `_validate_frontmatter` passes on 100% of the catalog.
  * **Requirement 2.1**: Fix delimiter closures (`---`) and malformed tags in the 26 failing skills.
  * **Requirement 2.2**: Maintain canonical metadata and triggers without altering semantics.

---

## 4. Acceptance Criteria & Invariants
* **Scenario 1: Symlink Traversal Attempt**
  * **Given**: `$ENV_FILE` points via a symlink to an external file.
  * **When**: `write_env "KEY" "VALUE"` is executed.
  * **Then**: The command aborts with non-zero exit code and the target file is untouched.
* **Scenario 2: Malformed Key Attempt**
  * **Given**: Key contains spaces or punctuation (e.g. `BAD KEY=123`).
  * **When**: `write_env "BAD KEY=123" "VALUE"` is executed.
  * **Then**: The command aborts with non-zero exit code.
* **Scenario 3: Atomic Secret Upsert**
  * **Given**: A valid key and secret value.
  * **When**: `write_env "API_KEY" "secret'value"` is executed.
  * **Then**: `$ENV_FILE` exists with mode `0600`, quotes are properly escaped, and permissions are preserved.
* **Scenario 4: 100% Fleet Frontmatter Parseability**
  * **Given**: The 574 skills in `/opt/hermes-agent/skills/`.
  * **When**: `_validate_frontmatter` runs over every `SKILL.md`.
  * **Then**: 0 errors are returned.

---

## 5. Security & Operational Considerations
* Mode `0600` strictly enforced on secrets files.
* Zero external network calls required for verification.
* Atomic file operations prevent race conditions.
