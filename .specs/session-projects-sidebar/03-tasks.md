# 03-tasks: Implementation Tasks & Verification

## Checklist

- [x] **Task 1: Database Migration & Taxonomy Population**
  - Create table `session_projects` in `/opt/hermes-agent-data/projects.db`.
  - Populate the 12 approved projects (`ads-factory`, `golden-game`, `lucky-brothers`, `bendabal`, `reportes`, `automatizaciones`, `finanzas`, `neuralops`, `content-factory`, `product-factory`, `ventas-leads`, `knowledge`).
  - *Verification:* `sqlite3 /opt/hermes-agent-data/projects.db "SELECT count(*) FROM projects"` >= 12.

- [x] **Task 2: Deterministic Routing Engine (Crons & CLI)**
  - Map 480 crons deterministically via `cron/jobs.json`.
  - Map 24 CLI sessions based on workspace `cwd`.
  - *Verification:* `sqlite3 /opt/hermes-agent-data/projects.db "SELECT count(*) FROM session_projects WHERE assigned_by = 'rule_deterministic'"` == 504.

- [x] **Task 3: Historical Gateway Batch Classification & Subagent Inheritance**
  - Run Jev batch classification script for remaining human gateway sessions.
  - Run subagent inheritance pass linking subagents to parent project.
  - *Verification:* `sqlite3 /opt/hermes-agent-data/projects.db "SELECT count(*) FROM session_projects"` == 841.

- [x] **Task 4: Engram Central Memory Taxonomy Alignment**
  - Backup `/opt/engram/engram.db`.
  - Align project names across `observations`, `sessions`, `user_prompts`, `sync_mutations`.
  - *Verification:* `engram projects list` displays unified taxonomy and `engram doctor --json` succeeds.

- [x] **Task 5: Native Codebase Integration**
  - Add helper functions `get_session_project_map` and `assign_session_project` in `hermes_cli/projects_db.py`.
  - Update `tui_gateway/project_tree.py` (`build_tree` and `_build_repos`) to honor `session["project_id"]` and support non-cwd conversations lane.
  - Update `tui_gateway/server.py` (`_project_tree_inputs`) to load `session_project_map`.
  - Add semantic project assignment route `POST /api/profiles/sessions/{session_id}/project`.
  - *Verification:* `python3 -m pytest tests/tui_gateway/test_project_tree.py tests/hermes_cli/test_projects_db.py` (42/42 passed).
