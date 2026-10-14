# Tasks: HTML Comment False-Positive Correction

## Objective

Apply the user-approved Unicode-aware lexical boundary correction to the existing HTML-comment trigger regex while preserving standalone threat detection and unrelated scanner behavior.

## Approval and Scope

- User approval: 2026-10-14, “si haz la correccion,” for the narrow correction captured in `01-spec.md`; no broader scanner-policy changes are authorized.
- Authorized source/test files: `tools/threat_patterns.py`, `tests/tools/test_threat_patterns.py`.
- Authorized supporting docs: this spec folder and `PROJECT_MEMORY.md`.
- No production deployment, remote operation, dependency installation, or RDD mode change.
- Planned delivery: one local work-unit commit; forecast under 150 authored lines, `ask-on-risk` by default, with no slice expected.

## Acceptance

- `Secretaría` embedded in a benign HTML comment does not produce `html_comment_injection`.
- Standalone existing malicious comment keywords continue to be detected across case, punctuation, and line-break variants.
- Unrelated scanner patterns remain unchanged.

## Work

- [x] **T01 — Add regression coverage and implement the minimal boundary correction.** Route: delegated direct; the change spans a non-trivial scanner implementation and its tests, with test reading/preparation performed by this worker. Added regression assertions first, observed the expected RED, then added Unicode-aware boundaries around only the existing HTML-comment keyword alternatives and verified GREEN.
  - **Files:** `tests/tools/test_threat_patterns.py`, `tools/threat_patterns.py`.
  - **Verification:** `HERMES_PYTHON=/usr/bin/python3 ./scripts/run_tests.sh tests/tools/test_threat_patterns.py` — RED: 34 passed, 6 expected failures for embedded trigger substrings; GREEN: 40 passed, 0 failed. `git diff --check` — exit 0. An additional combined check, `HERMES_PYTHON=/usr/bin/python3 ./scripts/run_tests.sh tests/tools/test_threat_patterns.py tests/agent/test_prompt_builder.py`, reported 115 passed and 1 unrelated failure: `TestBuildContextFilesPrompt.test_agents_md_no_git_root_stays_cwd_only` treats `/.git` as a repository root because `_find_git_root` checks only for `.git` existence; this failure is outside the authorized edit scope and remains unresolved.
  - **TDD evidence:** RED was observed before the production regex changed; the failing cases were the six embedded-word variants. GREEN preserved the existing malicious phrase and detected each standalone keyword with uppercase punctuation and multiline surrounding text.
- **Runtime harness:** N/A — the changed boundary is a pure in-process regex pattern; no live service/runtime integration is modified.
- **Rollback boundary:** Revert the work-unit commit to remove only this scanner boundary correction, its regression assertions, and this feature's documentation/memory note.
  - **Work-unit commit:** pending verification and commit.
  - **RDD:** `gentle-ai review mode status --cwd /root/hermes-agent-worktrees/html-comment-fix` reported `on` (global and clone-local unset). Read-only `gentle-ai review assess --cwd /root/hermes-agent-worktrees/html-comment-fix --json` returned risk `high`, `review_due: true`, reason `high_risk`, but exited 1 because untracked files require an explicit inventory/scope. No native STATUS or review lifecycle was started; parent owns any required preflight/consent.

## Next Step

Complete T01 locally, record exact verification and commit evidence, and report any native review requirement to the parent without claiming approval or delivery authority.
