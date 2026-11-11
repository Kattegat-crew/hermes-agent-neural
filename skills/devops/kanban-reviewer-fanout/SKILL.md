---
name: kanban-reviewer-fanout
description: Use when a project phase needs an independent reviewer card.
version: 1.0.0
author: Ragnar (NeuralCrew Labs)
platforms: [linux]
license: MIT
metadata:
  hermes:
    tags: [kanban, review, orchestration, discord, evidence]
    category: devops
---

# Kanban Reviewer Fan-out (orchestrator side)

## When to Use

- A multi-phase project reached the close of a phase and requires an independent reviewer (profile distinct from the implementer, cheap pinned model).
- A phase's work products must be archived in its Discord ticket thread with verifiable message ids.

Do NOT use for the reviewer's own role once spawned — that is `sdlc-review`, which explicitly excludes downstream review cards.

Spawn an independent review card on the kanban, verify the reviewer's verdict live, and archive the phase's evidence in its Discord ticket. This is the ORCHESTRATOR side. The reviewer's own role and verdict rules live in `sdlc-review`; that skill explicitly excludes downstream review cards, so do not load it for this workflow.

## Standing rule this implements
Multi-phase projects require an independent reviewer at the close of EACH phase, with a profile DISTINCT from the implementer, pinned to a cheap fast model (`glm5.3-flash` + `provider_override: nan-builders` in this fleet). Work products must be archived in the corresponding Discord ticket with a verifiable link — the ticket is the home of the work, chat is only the notice.

## 1. Create the review card

```bash
cd /opt/data
hermes kanban create "<FASE>-R · Review independiente de <área> (solo lectura)" \
  --assignee <perfil-distinto-al-implementador> --priority 90 \
  --model glm5.3-flash --provider nan-builders \
  --max-runtime 600 --max-retries 1 \
  --tenant <tenant-del-plan> \
  --idempotency-key <fase>-review-<área>-<fecha> \
  --body-file /opt/hermes-agent-data/cache/scratch/<fase>-review-body.md --json
```

- `--body-file` is mandatory for review bodies: they contain flag-like lines and newlines that die in shell quoting.
- The body must list each item to verify as a CONCRETE COMMAND with its expected output (never "check that X looks right"), the evidence paths, and the constraints: solo lectura, no edits, no restarts, ≤10 min.
- `--idempotency-key` makes re-runs safe.
- Get the task id from `hermes kanban list --tenant <tenant> --json` (the create JSON does not surface it clearly).

## 2. Dispatch and wait

```bash
hermes kanban dispatch --max 1
```

Dispatch succeeds cleanly when the owning gateway is idle: the task events show `claimed → spawned → owner_admitted` within the same second. The `owner silent` failure mode is NOT constant — it correlates with the gateway restarting or being busy in a long turn. If it fails, retry after the current turn/gateway cycle rather than changing profiles or configs.

## 3. Poll the verdict — the right columns

PITFALL: the `tasks` table has NO `outcome` column. Polling `select status, outcome from tasks` throws `sqlite3.OperationalError` on every iteration and silently wastes the whole polling window (verified 280 s lost).

```bash
# correct poll
python3 -c "import sqlite3;c=sqlite3.connect('/opt/data/kanban.db')
print(c.execute(\"select status,coalesce(substr(result,1,220),'') from tasks where id='<ID>'\").fetchone())"
```

When status is `done`, read the verdict from `task_runs` (`summary`, `metadata` has per-check findings and `artifacts` paths) and `hermes kanban show <ID>`:

```bash
python3 -c "import sqlite3;c=sqlite3.connect('/opt/data/kanban.db');c.row_factory=sqlite3.Row
for r in c.execute(\"select status,outcome,summary,metadata from task_runs where task_id='<ID>'\"): print(dict(r))"
```

The reviewer's evidence file lands under `/opt/hermes-agent-data/kanban/attachments/<ID>/` — confirm it exists and skim it before trusting the summary.

## 4. Publish evidence to the Discord ticket thread

Post as the NCA bot, then READ BACK to verify (a 200 POST is not proof of content):

```python
import json, urllib.request
tok = open('/opt/data/secrets/discord-nca-bot.token').read().strip()
H = {'Authorization': 'Bot ' + tok, 'Content-Type': 'application/json', 'User-Agent': 'DiscordBot (ncl,1.0)'}
req = urllib.request.Request('https://discord.com/api/v10/channels/<THREAD_ID>/messages',
    data=json.dumps({'content': msg[:1990]}).encode(), headers=H)
d = json.load(urllib.request.urlopen(req, timeout=20))
v = json.load(urllib.request.urlopen(urllib.request.Request(
    'https://discord.com/api/v10/channels/<THREAD_ID>/messages/' + d['id'], headers=H), timeout=15))
print(v['id'], len(v['content']))
```

Message format for a phase close: verdict of the reviewer (with card id, profile, model, duration) · N/N checks passed with one line each · non-blocking observations routed to future cards · new facts that correct the plan's diagnosis · artifact path.

## Pitfalls

- Reviewer profile must differ from the implementer — same-profile review is not independent.
- Never let the reviewer edit configs or restart anything; its card says solo lectura and its verdict quotes commands + output.
- Non-blocking observations found by the reviewer become candidate follow-up cards; do not fold them into the already-reviewed phase.
- A clean reviewer run is also diagnostic data: e.g. a dispatch with `owner_admitted` in the same second while the gateway is idle proves a race is conditional, which changes what the fix should be.
