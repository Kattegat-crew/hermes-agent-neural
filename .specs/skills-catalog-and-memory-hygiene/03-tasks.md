# Implementation Tasks: Local Skills Catalog Hygiene, Discovery Exclusions & Memory Heading Fix

* **Associated Spec**: [01-spec.md](./01-spec.md)
* **Associated Design**: [02-design.md](./02-design.md)
* **Status**: Completed

---

## Task Checklist

### Phase 1: TDD Scaffolding (`/opt/hermes-agent`)
- [x] **Task 1.1**: Add failing tests in `tests/agent/test_skill_utils.py` for dot-prefixed internal directories (`.backup_*`) and `*.rollback-broken` exclusion in `iter_skill_index_files()`.
  - *Skill*: `.skills/python-testing-patterns/SKILL.md`
  - *Verification*: `/opt/hermes-agent/.venv/bin/python -m pytest tests/agent/test_skill_utils.py -v`
- [x] **Task 1.2**: Add failing test in `tests/tools/test_memory_tool.py` verifying `#ElevenLabs` (no space after `#`) and `# comment` inside code blocks do not trigger false heading suppression in `MemoryStore.search()`.
  - *Skill*: `.skills/python-testing-patterns/SKILL.md`
  - *Verification*: `/opt/hermes-agent/.venv/bin/python -m pytest tests/tools/test_memory_tool.py -v`

### Phase 2: Core Code Fixes (`/opt/hermes-agent`)
- [x] **Task 2.1**: Update `agent/skill_utils.py` (`EXCLUDED_SKILL_DIRS` + `iter_skill_index_files()`).
  - *Target Files*: `agent/skill_utils.py`
  - *Verification*: `/opt/hermes-agent/.venv/bin/python -m pytest tests/agent/test_skill_utils.py tests/tools/test_skills_tool.py -v`
- [x] **Task 2.2**: Update `_split_markdown_sections()` in `tools/memory_tool_store.py` to enforce ATX heading syntax `^#{1,6}\s+\S` and code-fence awareness.
  - *Target Files*: `tools/memory_tool_store.py`
  - *Verification*: `/opt/hermes-agent/.venv/bin/python -m pytest tests/tools/test_memory_tool.py -v`

### Phase 3: Live Catalog Cleanup (`/opt/hermes-agent-data/skills/`)
- [x] **Task 3.1**: Permanently delete `/opt/hermes-agent-data/skills/.backup_pre_consolidation` and the 6 `*.rollback-broken` dirs.
- [x] **Task 3.2**: Reconcile `creative/hyperframes*` and the 9 cross-category duplicates (merging `devops/devops-infrastructure` into `core/devops-infrastructure`).
- [x] **Task 3.3**: Verify `hermes:hermes` ownership and run live `_skill_catalog()` check (`0` ambiguous, `0` `.backup_*`/`.rollback-broken`).

### Phase 4: Handover
- [x] **Task 4.1**: Update `.specs/README.md` (`Completed`), `.specs/skills-catalog-and-memory-hygiene/`, `PROJECT_MEMORY.md` (without touching `.specs/sdd-governance-unification/`), and save to Engram.
