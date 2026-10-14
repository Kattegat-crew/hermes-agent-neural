# 02-design: Technical Design for Semantic Project Grouping

## 1. Component Boundaries & Architecture

```
[ Hermes Gateway / RPC ]
          │
          ├──> projects_db.py (get_session_project_map, assign_session_project)
          │          │
          │          ▼
          │    projects.db (session_projects table)
          │
          ├──> server.py (_project_tree_inputs injects session['project_id'])
          │          │
          │          ▼
          └──> project_tree.py (build_tree maps explicit project_id before cwd fallback)
                     │
                     ▼
             Hermes Desktop (Native Sidebar renders projects & lanes)
```

## 2. Schema: `session_projects`
Lives in `$HERMES_HOME/projects.db`:
```sql
CREATE TABLE IF NOT EXISTS session_projects (
    session_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    profile_name TEXT NOT NULL DEFAULT 'default',
    assigned_by TEXT NOT NULL, -- 'manual', 'rule_deterministic', 'jev_batch', 'inherited_subagent'
    assigned_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_session_projects_lookup 
    ON session_projects(profile_name, project_id);
```

## 3. Data Flow & Tree Resolution Logic

1. **Input gathering (`_project_tree_inputs` in `tui_gateway/server.py`):**
   * Reads active projects from `projects.db`.
   * Queries `session_projects` for the active profile (or all if multi-profile).
   * Injects `session["project_id"] = map.get(session["id"])`.

2. **Tree builder (`build_tree` in `tui_gateway/project_tree.py`):**
   * For each session:
     ```python
     explicit_pid = session.get("project_id")
     if explicit_pid and explicit_pid in project_ids:
         by_project.setdefault(explicit_pid, []).append(session)
         continue
     owner = _project_for_session(session, folder_index, resolve)
     if owner:
         by_project.setdefault(owner["id"], []).append(session)
     else:
         unowned.append(session)
     ```

3. **Subtree Assembly for Gateway Sessions (`_build_repos` in `tui_gateway/project_tree.py`):**
   * Sessions with valid `cwd` are partitioned into git repo / branch lanes as before.
   * Sessions without `cwd` are aggregated into a synthetic group:
     * `id: "__conversations__"`
     * `label: "Conversaciones"`
     * `isMain: True`
     * Placed in `repos` so Desktop displays them seamlessly.

4. **Semantic Reassignment API (`POST /api/sessions/{session_id}/project`):**
   * Accepts `{ "project_id": str }`.
   * Invokes `projects_db.assign_session_project(...)` with `assigned_by = 'manual'`.
   * Preempts any folder-matching or automated classification.
