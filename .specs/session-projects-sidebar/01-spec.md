# 01-spec: Semantic Project Grouping for Hermes Desktop

## 1. Problem Statement
Hermes Desktop historically grouped sessions by matching `session.cwd` against project folders. Gateway sessions (Telegram, Discord, WhatsApp) and cron jobs originate without a dedicated working directory (`cwd` is empty or null). Consequently, over 800-1000 sessions appeared as loose / unorganized in the sidebar, while only 1 explicit project was rendered.

## 2. Business Intent & Goals
1. Allow any session to belong to an explicit business project semantically, without requiring physical folder structures or altering `cwd`.
2. Group sessions inside Hermes Desktop's native sidebar by their assigned project.
3. Provide a deterministic and assisted mechanism to assign past and future sessions to the approved taxonomy:
   - `ads-factory`
   - `golden-game`
   - `lucky-brothers`
   - `bendabal`
   - `reportes`
   - `automatizaciones`
   - `finanzas`
   - `neuralops`
   - `content-factory`
   - `product-factory`
   - `ventas-leads`
   - `knowledge`
4. Guarantee that manual user assignments take absolute precedence over automated classifiers.
5. Provide a safe "Home" (`__no_project__`) container for transient/unclassified conversations.

## 3. Explicit Non-Goals
1. **No title mutations:** No prepending `[Proyecto]` or modifying `session.title` in `state.db`. Project membership is purely relational metadata.
2. **No filesystem / Git mutations:** "Move to project" must never call `session.workspace.move` or alter filesystem paths for gateway/cwd-less sessions.
3. **No duplicate sidebar plugins:** All grouping is native to Hermes Desktop's project tree.

## 4. Acceptance Criteria
- **AC-1 (Persistence):** Table `session_projects` in `projects.db` stores `(session_id, project_id, profile_name, assigned_by, assigned_at)`.
- **AC-2 (Tree Builder):** When `projects.tree` or `GET /api/profiles/projects/tree` is called, sessions associated via `session_projects` appear under their respective project node.
- **AC-3 (Non-CWD Lanes):** Gateway sessions assigned to a project render in a clean "Conversaciones" group if the project has no matching git folder.
- **AC-4 (Reversibility):** Deleting `session_projects` reverts the system to folder-only matching with zero side effects.
