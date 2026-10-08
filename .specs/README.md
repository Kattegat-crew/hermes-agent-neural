# Spec-Driven Development (SDD) Index

This directory contains specifications, architectural designs, and implementation plans for all non-trivial initiatives in this repository.

## Spec Status Conventions
* **Draft**: Work in progress. Requirements or design undergoing refinement.
* **Approved**: Specification and architecture signed off. Ready for implementation.
* **In Progress**: Active execution of tasks documented in `03-tasks.md`.
* **Completed**: Implemented, verified with automated tests, and merged.
* **Archived**: Deprecated, superseded, or abandoned.

---

## Active & Past Specifications

| ID | Title | Status | Author | Target Path | Date |
|---|---|---|---|---|---|
| `_template` | Base SDD Specification Template | N/A | System | `.specs/_template/` | 2026-10-03 |
| `memoria-dev` | DEV Memory Continuity and Delivery | Approved (spec + design); scoped tasks ready/gated | Codex | `.specs/memoria-dev/` | 2026-10-08 |

---

## How to Start a New Spec
1. Copy `.specs/_template/` to `.specs/<feature-name>/`:
   ```bash
   cp -r .specs/_template .specs/my-new-feature
   ```
2. Complete `01-spec.md` and obtain stakeholder review.
3. Complete `02-design.md` detailing technical architecture and contracts.
4. Fill out `03-tasks.md` with atomic tasks and verification commands.
5. Execute phase by phase, checking off tasks as tests pass.
