# Feature Specification: Local Skills Catalog Hygiene, Discovery Performance & Memory Heading Fix

* **Status**: Approved
* **Author**: Antigravity (`agy`)
* **Target Module**: `/opt/hermes-agent/agent/skill_utils.py`, `/opt/hermes-agent/tools/skills_tool.py`, `/opt/hermes-agent/tools/memory_tool_store.py`, `/opt/hermes-agent-data/skills/`
* **Created**: 2026-11-17
* **Updated**: 2026-11-17
* **Companion Spec**: [`pre-lector-cognitivo-hardening`](file:///opt/hermes-agent-data/plugins/typesafe-skill-router/.specs/pre-lector-cognitivo-hardening/01-spec.md) (Draft)

---

## 1. Problem Statement & Motivation
* **What is the problem?**
  1. **Backup snapshot polluting live skills catalog (`/opt/hermes-agent-data/skills/.backup_pre_consolidation/`)**: A `108 MB` snapshot created `2026-11-15 07:22` (`975` `SKILL.md` files) sits inside `/opt/hermes-agent-data/skills/`. Because `.backup_pre_consolidation` is not in `EXCLUDED_SKILL_DIRS` (`agent/skill_utils.py:28-32`) and `iter_skill_index_files()` (`skill_utils.py:895-904`) has no generic leading-dot directory prune, `_skill_catalog()` scans `1,392` entries instead of `419`, injecting `974` duplicate/stale backup skills (`594` shadowed, `189` ambiguous).
  2. **15 live skill name collisions & `*.rollback-broken` artifacts in `/opt/hermes-agent-data/skills/`**: Even excluding `.backup_pre_consolidation`, `15` `name:` collisions exist (3 `*.rollback-broken` broken backups, 3 `hyperframes*` copies under `creative/` competing with top-level symlinks to `/root/.claude/skills/hyperframes*`, plus 9 cross-category duplicates: `blocked-page-recovery`, `devops-infrastructure`, `email-inbox-triage`, `gif-search`, `himalaya`, `obsidian`, `systematic-debugging`, `vps-forge`, `xurl`).
  3. **`locate_skill()` $O(N^2)$ catalog re-walks (`tools/skills_tool.py:405-445`)**: Calling `locate_skill()` per skill triggers `_collect_skill_candidates()` -> `iter_skill_index_files` + `rglob`, taking ~2.3–2.9s per lookup on large catalogs.
  4. **Hashtag / single-line `#` treated as Markdown heading (`tools/memory_tool_store.py:109, 882`)**: As recorded in `PROJECT_MEMORY.md:8`, `_split_markdown_sections()` treats `#tag` / `#ElevenLabs...` lines lacking a space after `#` as Markdown H1 headings, triggering heading-only suppression (`L882`) and dropping valid body matches.
* **Why solve it now?** Eliminating the 975 backup skills, resolving the 15 duplicates, hardening `EXCLUDED_SKILL_DIRS`, and fixing `#` heading parsing restores a clean single-source skills catalog across all 12 Hermes profiles and prevents false suppression in `MemoryStore.search()`.

---

## 2. Goals & Non-Goals
### Goals
- [ ] **G1 — Permanently Delete `.backup_pre_consolidation` from `skills/`**: Remove `/opt/hermes-agent-data/skills/.backup_pre_consolidation` (`108 MB`, `975` `SKILL.md` files from Nov 15 purge) permanently per Jesús's explicit authorization, eliminating all 974 stale/ambiguous catalog entries.
- [ ] **G2 — Reconcile the 15 Duplicate / Rollback Skills**: Archive/remove the 3 `*.rollback-broken` directories (`hermes-agent.rollback-broken`, `hermes-fleet-runtime.rollback-broken`, `hermes-plugin-e2e-verification.rollback-broken`), reconcile `hyperframes*` symlinks vs `creative/hyperframes*` (`21061 B` vs `15730 B` — keep the canonical single source of truth), and deduplicate the remaining 9 category duplicates into their canonical folders.
- [ ] **G3 — Harden `agent/skill_utils.py` Discovery Exclusions**: Update `EXCLUDED_SKILL_DIRS` / `iter_skill_index_files()` (`skill_utils.py:28-32, 895-904`) to skip `.backup_*` / dot-prefixed internal directories (excluding explicit root `.hermes` / `.agents`) and `*.rollback-broken` directories.
- [ ] **G4 — Optimize `tools/skills_tool.py` Candidate Lookup (if needed after G1)**: Evaluate `locate_skill` / `_collect_skill_candidates` single-pass lookup so repeated `locate_skill` calls do not re-walk the tree unnecessarily.
- [ ] **G5 — Fix Markdown Heading Detection (`tools/memory_tool_store.py:109, 882`)**: Require ATX Markdown heading syntax (`^#{1,6}\s+`) in `_split_markdown_sections()` so `#hashtag` tokens are never misparsed as section headings.

### Non-Goals (Out of Scope)
- Modifying `/opt/hermes_focus_plugin` (tracked separately under `/opt/hermes_focus_plugin/.specs/`).
- Re-implementing the **Pre-Lector Cognitivo** fixes already specified in `/opt/hermes-agent-data/plugins/typesafe-skill-router/.specs/pre-lector-cognitivo-hardening/01-spec.md`.
- Changing `plugins.entries.typesafe-skill-router` rollout across the 12 profiles before `pre-lector-cognitivo-hardening` is approved and executed.
- Deleting any backup data permanently without archiving under `/opt/hermes-agent-data/backups/`.

---

## 3. Functional Requirements & Acceptance Criteria
* **Scenario 1: Clean Catalog Count & Zero Backup Pollution**
  * **Given**: `/opt/hermes-agent-data/skills/.backup_pre_consolidation` is moved to `/opt/hermes-agent-data/backups/` and the 15 duplicates are reconciled.
  * **When**: `_skill_catalog(skip_disabled=True)` and `find_all_skills()` execute.
  * **Then**: Zero entries originate from `.backup_*` or `*.rollback-broken`, `ambiguous` count drops to `0`, and all 12 profile `skills/` symlinks resolve to the clean catalog.
* **Scenario 2: Defensive Dot-Dir Exclusion in `skill_utils.py`**
  * **Given**: A temporary `.backup_test/foo/SKILL.md` or `bar.rollback-broken/SKILL.md` inside a skills root.
  * **When**: `iter_skill_index_files()` runs.
  * **Then**: Both directories are skipped without altering normal category folders (`creative/`, `devops/`, etc.) or `.hermes/skills` / `.agents/skills` tier-0 roots.
* **Scenario 3: ATX Heading Strictness in `MemoryStore.search()`**
  * **Given**: A memory file containing `## AcmeCorp` and another section containing `#ElevenLabs voice pipeline`.
  * **When**: `MemoryStore.search("ElevenLabs")` runs.
  * **Then**: `#ElevenLabs` is parsed as body text, not an H1 heading, and matches reliably without triggering false heading suppression.

---

## 4. Security, VPS & Operational Considerations
* Preserve `hermes:hermes` ownership on `/opt/hermes-agent-data/skills/`, `/opt/hermes-agent-data/backups/`, and `/opt/hermes-agent/` files.
* Verify `hyperframes*` symlink targets (`/root/.claude/skills/hyperframes*`) vs `creative/hyperframes*` content timestamps/versions before deleting either copy.
* Prompt caching remains 100% intact (all changes affect on-demand skill lookup, catalog hygiene, or `MemoryStore.search()`, never active conversation prefixes).

---

## 5. Applicable Project Skills
- [ ] `.skills/hermes-agent/SKILL.md` — Hermes Agent runtime conventions and `skill_utils` / `skills_tool` contracts
- [ ] `.skills/systematic-debugging/SKILL.md` — Root-cause verification on duplicate skills and ATX heading parsing
- [ ] `.skills/python-testing-patterns/SKILL.md` — Unit tests for `skill_utils.py` exclusions and `MemoryStore` heading parsing
- [ ] `.skills/bash-defensive-patterns/SKILL.md` — Safe atomic relocation and backup verification for `/opt/hermes-agent-data/skills/`
