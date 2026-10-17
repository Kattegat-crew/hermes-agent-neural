# Feature Specification: [Feature Name]

* **Status**: Draft | Approved | In Progress | Completed
* **Author**: [Author Name / Agent]
* **Target Module**: [e.g. `gateway/`, `agent/`, `plugins/`]
* **Created**: YYYY-MM-DD
* **Updated**: YYYY-MM-DD

---

## 1. Problem Statement & Motivation
* **What is the problem?** Describe the current limitation, architectural debt, or missing capability.
* **Why solve it now?** Business impact, developer experience, or system stability justification.

---

## 2. Goals & Non-Goals
### Goals
- [ ] Primary goal 1
- [ ] Primary goal 2

### Non-Goals (Out of Scope)
- Explicitly state what will NOT be built or addressed in this iteration.
- Prevents scope creep and uncontrolled file modification.

---

## 3. User Stories & Functional Requirements
* **US-1**: As a [role/system], I want to [action], so that [outcome].
  * **Requirement 1.1**: The system must...
  * **Requirement 1.2**: In the event of [condition], the system must...

---

## 4. Acceptance Criteria & Invariants
Use concrete Given-When-Then criteria:
* **Scenario 1**: Successful path
  * **Given**: [Initial system state]
  * **When**: [Action occurs]
  * **Then**: [Expected result and side effects]

* **Scenario 2**: Failure / Edge case path
  * **Given**: [Invalid input or offline service]
  * **When**: [Action occurs]
  * **Then**: [Graceful error handling and exit codes]

---

## 5. Security, VPS & Operational Considerations
* Any new environment variables required? (Must reside in `/opt/vault/` or `.env` `0600`).
* Does this affect systemd services, open ports, or memory limits?
* Any potential impact on prompt caching or token latency?

---

## 6. Applicable Project Skills
List the project-local skills from `.skills/` (`.agents/skills/`) and `.atl/skill-registry.md` that govern this specification:
- [ ] `.skills/codebase-inspection/SKILL.md` — Subsystem exploration and dependency tracing
- [ ] `.skills/api-and-interface-design/SKILL.md` — Tool schemas, gateway contracts, and plugin interfaces
- [ ] `.skills/systematic-debugging/SKILL.md` — Root-cause analysis and edge-case verification
- [ ] `.skills/code-review-and-quality/SKILL.md` — Clean architecture, prompt-cache preservation, and test coverage

