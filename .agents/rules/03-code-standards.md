# Code Standards & Quality Gates

## Architectural Philosophy
* **SOLID Foundations & Clean Architecture**: Prioritize separation of concerns, explicit interfaces, and decoupled adapters over monolithic scripts.
* **Hermes Narrow Waist**: The agent core must stay minimal. Capability lives at the edges (plugins, skills, tools), not inside bloated core loops.
* **Preserve Prompt Caching**: Never modify active conversation prefixes, swap toolsets dynamically mid-conversation, or inject dynamic timestamps into cached prompts.

---

## Technical Standards

### 1. Python Code Quality
* **Type Annotations**: Mandatory type hinting across all function signatures, parameters, and return types (`typing` / `types`).
* **Linting & Formatting**: Follow project linters (`ruff`, `flake8`, `black`, `isort`). Ensure code compiles cleanly with zero syntax warnings.
* **Error Handling**: Fail fast with descriptive custom exceptions. Avoid broad `except Exception: pass` without structured logging.
* **Imports**: Group imports cleanly (Standard library -> Third-party packages -> Local modules).

### 2. Testing Discipline (TDD)
* **Unit Testing**: Every new tool, skill, adapter, or helper must have accompanying tests in `tests/`.
* **Test Isolation**: Mock external APIs and network requests. Never perform unmocked live calls to third-party providers inside unit tests.
* **Verification Command**:
  ```bash
  pytest tests/<target_module>/ -v
  ```
* **Exit Code Guarantee**: Always check and confirm exit code 0 (`$? == 0`) before marking any implementation task as complete.

### 3. Documentation Integrity
* Public classes, methods, and complex functions must include clear docstrings explaining arguments, returns, and raised exceptions.
* Keep `AGENTS.md` and relevant architecture docs synchronized when domain contracts evolve.
