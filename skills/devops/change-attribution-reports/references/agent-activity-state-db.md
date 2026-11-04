# Agent activity attribution via state.db

Question class: "revisa todos los cambios hechos por <agente> (Ragnar, Vigía, Bragi…) en los últimos N días". Agents don't commit to git — their footprint is in the Hermes state DB. This is the ground truth for *agent* authorship and also cross-validates mtime findings ("touched, author unverifiable" often resolves to an agent here).

## Where to look

- Central DB: `/opt/data/state.db` (SQLite ~400MB — open read-only: `sqlite3.connect('file:/opt/data/state.db?mode=ro', uri=True)`).
- Profile→agent map on this host: **Ragnar = the `default` profile** (`profile_name IS NULL OR '' OR 'default'`); every other bot has its own row/dir (`bragi, brokkr, freyja, heimdall, hermodr, roshi, sindri, ullr, vigia, vili, comms`) under `/opt/data/profiles/<name>/`. Each profile's own sessions live in the same central DB, tagged with `profile_name`.
- Session transcripts (jsonl) under `/opt/data/sessions/` are sparse/rotated — do NOT rely on them; the DB is the complete record.

## Schema that matters

`sessions`: `id, profile_name, source (desktop|telegram|whatsapp|discord|subagent|cron_...), title, started_at, last_activity_at (epoch REAL), message_count, tool_call_count`.
`messages`: `session_id, role, content, tool_name, tool_calls, timestamp`.

## Pitfalls that cost turns

- `tool_name` is populated on `role='tool'` rows (the RESULTS), not on `role='assistant'` rows. Querying assistant+tool_name returns empty. The **arguments** (paths! selectors! commands!) live in `role='assistant' .tool_calls` — a JSON string: `[{"function": {"name": "write_file", "arguments": "{\"path\":...}"}}, ...]`. Parse assistant `tool_calls`, not the tool rows.
- Timestamps are epoch (UTC) — build cutoff with `datetime.now(timezone.utc) - timedelta(days=N)` and compare against `m.timestamp`.
- `cron_*` session ids are scheduled-job runs, not interactive work — keep them in usage stats, exclude from "what did X build" narratives unless asked.

## The working recipe

```python
import sqlite3, json, datetime
from collections import Counter, defaultdict
con = sqlite3.connect('file:/opt/data/state.db?mode=ro', uri=True)
cutoff = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=3)).timestamp()
rows = con.execute("""SELECT m.session_id, m.timestamp, m.tool_calls FROM messages m
  JOIN sessions s ON s.id = m.session_id
  WHERE m.timestamp >= ? AND m.role='assistant'
    AND m.tool_calls IS NOT NULL AND m.tool_calls != ''
    AND (s.profile_name IS NULL OR s.profile_name='' OR s.profile_name='default')""", (cutoff,)).fetchall()
cnt = Counter(); edits = defaultdict(lambda: {'files': set(), 'first': 9e18, 'last': 0, 'n': 0})
for sid, ts, tc in rows:
    for c in json.loads(tc or '[]'):
        fn = c.get('function') or {}
        name = fn.get('name', '?'); cnt[name] += 1
        args = json.loads(fn.get('arguments') or '{}')
        if name in ('write_file', 'patch'):
            e = edits[sid]; e['files'].add(args.get('path','?')); e['n'] += 1
            e['first'] = min(e['first'], ts); e['last'] = max(e['last'], ts)
# join edits[sid] with sessions.title/display_name for the narrative per session
```

## What to mine out of the tool_calls

- **File edits** grouped by session+title → per-workstream story (which files, how many revisions, when active).
- `skill_manage` ops → which skills the agent patched (count per op name).
- `memory` ops → add/replace/remove counts (aggressive re-org shows as ~40 replaces).
- `terminal` args → grep for `hermes cron create`, `crontab`, `jobs.json` → cron jobs the agent created. Cross-check with `created_at` fields in `/opt/data/cron/jobs.json` (per-job ISO timestamps — the definitive creation dates).
- `source='subagent'` sessions with bulk writes → parallel delegation (e.g. one agent spawning 5 subagents to fill wiki pages) — count them as the parent agent's work.

## Report shape

Total counts first (edits/terminal/code runs), then numbered workstreams with session title + time range + file evidence, then config mutations (`diff` the `*.bak*` timestamps found near the window against the live file — config.yaml model/timeout changes show up this way), closing with a 2-3 line lectura del sensei linking it back to host-mtime findings from the previous report.
