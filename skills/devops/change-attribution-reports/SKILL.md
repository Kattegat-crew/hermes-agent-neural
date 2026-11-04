---
name: change-attribution-reports
description: "Use when asked who changed what in a project or repo."
tags: [atribucion, git, reportes, auditoria, commits, mtimes, autores, state-db]
---

# Change-Attribution Reports (Hermes prod host)

Task class: "dame el reporte de los cambios hechos por <persona> en <proyecto> en las últimas N horas". The deliverable is an **attributed** report — every change tied to an author with evidence, and honest zero-findings stated as such. Never pad a thin git story with speculation dressed as attribution.

## Evidence sources (check in this order)

1. **Local git** — `git -C <repo> log --since="48 hours ago" --all --pretty=format:'%h|%an|%ae|%ad|%s' --date=iso`. Enumerate candidate repos first: `find /opt -maxdepth 3 -name .git -type d`.
2. **Sync/deploy logs** — on this host, Hermes is deployed from a fork synced by `/opt/hermes/scripts/sync-upstream.sh`, whose log `/opt/hermes/scripts/sync-upstream.log` records each daily sync: commits pulled, rebase result, build, health-check outcomes, push success/failure, backup tags, version. Parse with `grep -E '^\[<date>' <log> | awk '!seen[$0]++'` — **the log duplicates every line**; dedupe or the report double-counts. This log is the ground truth for "what entered the deployment", independent of git.
3. **File mtimes on the host** — `find <dir> -newermt "<cutoff>" -type f`, excluding `sessions|logs|cache|__pycache__|node_modules|.git/`. Good for spotting hand-edited scripts/configs/cron jobs, but mtimes carry **no author** — report as "touched, author unverifiable" rather than attributing.
4. **Upstream GitHub API** — see `references/github-api-attribution.md` for the working recipe (the naive query fails; details matter).
5. **Agent authorship (Ragnar, Vigía, any bot)** — agents don't commit to git; their footprint is in `/opt/data/state.db` (`sessions` + `messages.tool_calls`). Full recipe, schema gotchas and cron/skill/memory mining in `references/agent-activity-state-db.md`. Use this whenever the asked-about author is an agent, or to attribute "hand-edited script" mtimes that have no VCS owner — they usually resolve to an agent session.
6. **Cross-host ssh attribution (writes landed on host A, executed from host B)** — when host A has mtimes/hashes but NO matching agent session, the author was an agent on host B running `ssh <A>`. Prove it by joining A's `/var/log/auth.log` `Accepted publickey ... from <IP>` lines (±1 s of each mtime) with B's `state.db` `messages.tool_calls` (`ssh <A> '...'` command args). Full recipe: `references/cross-host-write-attribution.md`.
7. **Webhook fan-out: concurrent duplicate sessions of the SAME agent** — before declaring an author "unknown", enumerate the authoring agent's own sessions: one webhook platform can spawn a NEW session per delivery (distinct `chat_id` hash → distinct session_key), so several sessions of one profile run in PARALLEL over the same paths. Verified 3-nov-2026: the `buzon-bob` webhook opened 6 concurrent Ragnar (`default`) sessions in one night (`20261103_205353…` → `20261103_210200…`), each writing to the same dirs. Enumerate with `select id,source,user_id,chat_id from sessions where id like '<yyyymmdd>_%'` and compare `user_id`/platform across the candidates — same `user_id: webhook:<canal>` across distinct session ids proves fan-out, not a third party. The structural fix (stable session_key per ticket, or a per-ticket lock) is a webhook-routing config change → propose it, needs human approval; meanwhile treat overlapping buzon deliveries as a real race risk.

## Host-specific facts (this machine)

- `/opt/hermes` is a deploy tree with **no `.git`** — the real fork repo lives at `/root/hermes-agent-legacy-docker`, which the sandbox user (`hermes`) **cannot read** (permission denied, no sudo). Don't burn turns trying; go straight to the sync log + upstream API.
- Contributor→email mapping (for alias disambiguation): `/opt/hermes/contributors/emails/<email>` files contain the login; grep them to verify whether a display name is a given person (e.g. near-miss nicknames are NOT the person until an email match proves it).
- `docker ps` / `docker images` timestamps corroborate deploys: image creation time should match a "Docker image built successfully" log entry.
- Cron job definitions churn is visible in `/opt/data/cron/jobs.json` + per-profile `cron/jobs.json` mtimes; the per-job `created_at` ISO fields give definitive creation dates (used to pin new crons to a specific agent session within the minute).
- Profile→agent map: Ragnar = `default` profile (data root `/opt/data`, NOT `/opt/data/profiles/ragnar/` — that dir doesn't exist); all other bots are rows/dirs under `/opt/data/profiles/<name>/`.

## Attribution discipline (the report's core)

- Match authors against known identities by **email**, not display name; record the negative finding explicitly ("revisé el mapa de contribuidores: 990 entradas, cero coincidencias con su correo").
- Separate the report into: (a) changes signed by the person, (b) changes made by their automation (cron syncs, fleet scripts), (c) host activity attributable to nobody (mtimes without VCS). A user asking "qué hizo Jonathan" cares about (b) too — his automation is his footprint.
- Flag degraded automation states found en route (failed pushes, health-check failures, a sync day with no log entry) — these are actionable and the user (Chucho/Jonathan) wants them surfaced.

## Report format (WhatsApp/Telegram, Spanish, Roshi voice)

- Window stated with timezone at top. Bold section headers, bullets, no tables.
- Counts with evidence ("370 commits → v0.21.0, push fallido, tag pre-sync-…"). Close with a 2-3 line resumen del sensei + next-step suggestion.
- Verify before finalizing: enumerate each source consulted and whether it returned data; an "I found nothing" must say *where* you looked.
