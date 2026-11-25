# Implementation Tasks: Unified SDD Governance Across `/opt/hermes-agent` and `/opt/hermes-agent-data`

* **Associated Spec**: [01-spec.md](./01-spec.md)
* **Associated Design**: [02-design.md](./02-design.md)
* **Status**: Completed

---

## Execution Guidelines
1. **Approval Gate**: Obtain explicit human approval on `01-spec.md` and `02-design.md` before executing Phases 1–4.
2. **Ownership Hygiene**: Keep `hermes:hermes` ownership on all created/edited files in `/opt/hermes-agent` and `/opt/hermes-agent-data`.
3. **Gateway Restart Gate**: Do not restart `hermes-agent.service` or `hermes-agent-roshi.service` after `config.yaml` changes without explicit human authorization.

---

## Task Checklist

### Phase 1: Verification Test Scaffolding (TDD)
- [x] **Task 1.1**: Check exact truncation limit in `agent/prompt_builder.py` (`_truncate_content`) so the Option A header in `/opt/hermes-agent/AGENTS.md` never causes truncation of downstream Nous sections.
  - *Skill*: `/opt/hermes-agent/.skills/codebase-inspection/SKILL.md`
  - *Verification*: Read-only check of `_truncate_content` limit in `agent/prompt_builder.py`.
- [x] **Task 1.2**: Add a governance verification test (`tests/agent/test_sdd_governance_discovery.py` or standalone test) asserting `build_context_files_prompt` loads SDD headers for both `/opt/hermes-agent` and `/opt/hermes-agent-data`, and `SubdirectoryHintTracker("/opt/hermes-agent-data")` activates subdirectory hints for `plugins/typesafe-skill-router/`.
  - *Skill*: `/opt/hermes-agent/.skills/python-testing-patterns/SKILL.md`
  - *Verification*: `scripts/run_tests.sh tests/agent/test_sdd_governance_discovery.py` (2 passed) & `/opt/hermes-agent-data/scripts/tests/test_sdd_governance.py` (3 passed). El wrapper del repo es la vía canónica; el carve-out de `pytest` directo para un archivo suelto queda documentado en `.agents/rules/03-code-standards.md`.

### Phase 2: `/opt/hermes-agent` SDD Alignment (Option A)
- [x] **Task 2.1**: Prepend the compact NCL SDD Governance & Repo Boundary header to `/opt/hermes-agent/AGENTS.md` preserving all Nous rules below.
  - *Skill*: `/opt/hermes-agent/.skills/hermes-agent/SKILL.md`
  - *Verification*: `wc -c /opt/hermes-agent/AGENTS.md` (`11943` bytes <= `12000`) and `test -f` check for every referenced doc.
- [x] **Task 2.2**: Create `/opt/hermes-agent/ARCHITECTURE.md` and reconcile `pytest` vs `scripts/run_tests.sh` in `/opt/hermes-agent/.agents/rules/03-code-standards.md`.
  - *Skill*: `/opt/hermes-agent/.skills/code-review-and-quality/SKILL.md`
  - *Verification*: `test -f /opt/hermes-agent/ARCHITECTURE.md` and consistency verified.

### Phase 3: `/opt/hermes-agent-data` SDD Scaffolding & `SubdirectoryHintTracker` Activation
- [x] **Task 3.1**: Create `/opt/hermes-agent-data/.agents/rules/01-sdd-workflow.md`..`04-memory-and-reuse.md`, `/opt/hermes-agent-data/ARCHITECTURE.md`, and `/opt/hermes-agent-data/PROJECT_MEMORY.md`.
  - *Skill*: `/opt/hermes-agent/.skills/hermes-agent/SKILL.md`
  - *Verification*: Confirmed every file listed in `/opt/hermes-agent-data/AGENTS.md` exists on disk.
- [x] **Task 3.2**: Update `/opt/hermes-agent-data/AGENTS.md` (fix skills SSOT pointer, add explicit **Hermes Self-Editing SDD Gate**, cross-link `/opt/hermes-agent`), deduplicate `profiles/*/AGENTS.md` SDD boilerplate, and whitelist SDD files in `/opt/hermes-agent-data/.gitignore`.
  - *Verification*: `test_sdd_governance.py` passed (`3 passed`).
- [x] **Task 3.3**: Audit `terminal.cwd` in `/opt/hermes-agent-data/config.yaml` and `profiles/*/config.yaml`; update `terminal.cwd: /opt/hermes-agent-data`.
  - *Verification*: Verified `YAML OK`, `load_config_readonly()`, and `test_sdd_governance.py` (`3 passed`).

### Phase 4: Final Verification & Handover
- [x] **Task 4.1**: Verify `hermes:hermes` ownership on all touched files, run governance tests, update `PROJECT_MEMORY.md` in both repos, save to Engram, and mark `.specs/README.md` as `Completed`.
  - *Verification*: `find ... -user root` returned empty; `test_sdd_governance_discovery.py` (`2 passed`) and `test_sdd_governance.py` (`3 passed`).

---

## Evidence Map (cross-repo)

`Status: Completed` covers both trees. The parts that cannot be reproduced from a checkout of `/opt/hermes-agent` alone are listed here so a reviewer can re-run them on the host:

| Claim | Where the evidence lives | Command |
|---|---|---|
| Data-tree governance docs exist | `/opt/hermes-agent-data/{AGENTS.md,ARCHITECTURE.md,PROJECT_MEMORY.md,.agents/rules/01..04,.specs/README.md}` | `ls -l` those paths |
| Data-tree discovery test passes | `/opt/hermes-agent-data/scripts/tests/test_sdd_governance.py` (3 tests) | `cd /opt/hermes-agent-data/scripts && /opt/hermes-agent/.venv/bin/pytest tests/test_sdd_governance.py -q` |
| `terminal.cwd` no longer home-anchored | `config.yaml` + `profiles/default/config.yaml` | `grep -n "cwd" /opt/hermes-agent-data/config.yaml` |
| `AGENTS.md` size cap | `scripts/ci/check_agents_md_size.py` | `python3 scripts/ci/check_agents_md_size.py` |

Items 2–4 require the runtime tree; the reviewer of the core PR only needs item 1 plus the in-tree test to validate the core half.
