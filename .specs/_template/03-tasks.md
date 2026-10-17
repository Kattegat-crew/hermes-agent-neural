# Implementation Tasks: [Feature Name]

* **Associated Spec**: [01-spec.md](./01-spec.md)
* **Associated Design**: [02-design.md](./02-design.md)
* **Status**: In Progress | Completed

---

## Execution Guidelines
1. **TDD First**: Write tests that fail before implementing feature code.
2. **Atomic Verification**: Run the specified command after completing each task.
3. **No Batching**: Never check off a task without executing its verification command.

---

## Task Checklist

### Phase 1: Test Scaffolding & Interfaces
- [ ] **Task 1.1**: Define interfaces/types and scaffold failing unit tests in `tests/`.
  - *Target Files*: `tests/test_feature.py`
  - *Skill*: `.skills/api-and-interface-design/SKILL.md`
  - *Verification*: `pytest tests/test_feature.py -v` (Expect failure on unimplemented methods).

### Phase 2: Core Domain Logic
- [ ] **Task 2.1**: Implement the core component logic according to `02-design.md`.
  - *Target Files*: `path/to/module.py`
  - *Skill*: `.skills/code-review-and-quality/SKILL.md`
  - *Verification*: `pytest tests/test_feature.py -v` (Must pass with exit code 0).
- [ ] **Task 2.2**: Implement edge cases and error handling.
  - *Target Files*: `path/to/module.py`, `tests/test_feature.py`
  - *Skill*: `.skills/systematic-debugging/SKILL.md`
  - *Verification*: `pytest tests/test_feature.py -k "test_error" -v`

### Phase 3: Integration & System Wiring
- [ ] **Task 3.1**: Wire the component into the gateway/agent lifecycle.
  - *Target Files*: `gateway/run.py` or `agent/...`
  - *Skill*: `.skills/codebase-inspection/SKILL.md`, `.skills/code-review-and-quality/SKILL.md`
  - *Verification*: `pytest tests/integration/test_feature_integration.py -v`

### Phase 4: Final Quality Gates & Cleanup
- [ ] **Task 4.1**: Run full linting, formatters, and type checkers.
  - *Verification*: `ruff check .` && `python -m mypy path/to/module.py`
- [ ] **Task 4.2**: Verify no untracked files or leftover debug logs remain in repo.
  - *Verification*: `git status --porcelain`
- [ ] **Task 4.3**: Mark specification status as `Completed` in `.specs/README.md`.
