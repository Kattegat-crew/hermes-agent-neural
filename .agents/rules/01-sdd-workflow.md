# Spec-Driven Development (SDD) Workflow

## Core Principle
**CONCEPTS > CODE. Never write code without an approved specification.**
No feature, major refactor, or non-trivial architectural change may be committed without a corresponding specification folder in `.specs/<feature-name>/`.

---

## The 4-Phase SDD Lifecycle

```
[Phase 1: Spec] ──(Approval)──> [Phase 2: Design] ──(Approval)──> [Phase 3: Tasks] ──> [Phase 4: Implementation]
   01-spec.md                      02-design.md                      03-tasks.md              TDD & Skill-Guided Verification
```

### Phase 1: Specification (`01-spec.md`)
* **Goal**: Establish the business and functional contract. Clarify WHAT and WHY.
* **Requirements**:
  1. Define user stories, business intent, and core domain requirements.
  2. Document explicit non-goals (what is strictly out of scope).
  3. Detail acceptance criteria using clear, testable assertions (Given / When / Then).
  4. List known edge cases and error failure modes.
  5. **Skill Audit**: Scan `.skills/` (and `.agents/skills/`) to identify relevant domain and technology skills applicable to the scope.
* **Gate**: Halt for stakeholder / human sign-off before proceeding to architecture design.

### Phase 2: Technical Design (`02-design.md`)
* **Goal**: Define the system architecture and contracts. Clarify HOW.
* **Requirements**:
  1. Model system components, boundaries, and public API / function signatures.
  2. Detail data flows, state machines, persistence schemas, and sequence diagrams.
  3. Analyze trade-offs, dependencies, performance implications, and security risks.
  4. Define telemetry, observability, and logging standards for the change.
  5. **Skill Pattern Compliance**: Align technical choices with architectural patterns and anti-patterns defined in the project's loaded skills (e.g., React best practices, Python patterns, etc.).
* **Gate**: Halt for stakeholder / human sign-off on technical feasibility and architecture.

### Phase 3: Task Breakdown (`03-tasks.md`)
* **Goal**: Create an executable, atomic, and test-driven implementation plan.
* **Requirements**:
  1. Break work into small, ordered, and independent units of work.
  2. Enforce Test-Driven Development (TDD): tests are scaffolded first.
  3. Every single task MUST specify an automated verification command (e.g., `pytest <path>`, `ruff check`, `npm test`, `tsc --noEmit`).
  4. **Skill Attribution**: Explicitly tag each task with the relevant skill(s) (e.g., `react-best-practices`, `next-cache-components`, `python-testing-patterns`) governing its execution.
  5. Explicitly mark dependencies between tasks.

### Phase 4: Implementation & Verification
* **Goal**: Execute the plan with zero regressions.
* **Rules**:
  1. **Mandatory Pre-Execution Skill Check**: Before writing code, the executor MUST read the referenced `SKILL.md` from `.skills/<skill>/` (or `.agents/skills/<skill>/`). Execution without consuming relevant skills is considered a violation of the SDD protocol.
  2. Work strictly from the checklist in `03-tasks.md`.
  3. Check off tasks only after their verification commands exit with code 0.
  4. Do not modify files outside the agreed design boundaries.
  5. **Continuous Skill Nutrition**: When solving novel framework edge cases or discovering new project conventions, enrich the corresponding skill in `.skills/` or run `npx autoskills` to keep procedural memory updated.
  6. Once all tasks are complete, execute full regression suites and archive/mark the spec as `Completed`.

---

## 2. Catalog Boundary & Repository Engineering Skills (CRITICAL)

`/opt/hermes-agent` serves two distinct roles that MUST NEVER be conflated when developing or debugging this repository:

1. **Repository Engineering Skills (`.skills/` $\to$ `.agents/skills/` & `.claude/skills/`, 13 stack skills)**:
   - When intervening in the **Hermes codebase itself** (Python core, gateway, tools, plugins, `apps/desktop` Electron/React, `scripts/whatsapp-bridge` Node.js, or Docker/s6), agents MUST consult **only** `.atl/skill-registry.md` and load the relevant stack skill(s) from `.skills/<skill>/SKILL.md`:
     - *Core & Architecture*: `hermes-agent`, `hermes-agent-skill-authoring`, `api-and-interface-design`, `codebase-inspection`, `code-review-and-quality`
     - *Python & Testing*: `python-patterns`, `python-testing-patterns`, `systematic-debugging`
     - *Desktop & Web (`apps/desktop`, `website`)*: `react-best-practices`, `typescript-advanced-types`
     - *Bridge & Infra (`scripts/whatsapp-bridge`, `docker/`)*: `nodejs-backend-patterns`, `hermes-s6-container-supervision`, `bash-defensive-patterns`
2. **Bundled Fleet Runtime Catalog (`skills/` & `optional-skills/`, ~571 skills)**:
   - The top-level `skills/` and `optional-skills/` directories are **bundled product data** distributed for end-user/fleet agents at runtime.
   - **STRICT PROHIBITION**: Coding agents modifying the Hermes engine MUST NOT scan, index, or bulk-load `skills/` or `optional-skills/` as repository development instructions, unless the task explicitly asks to author or edit a bundled fleet skill.

