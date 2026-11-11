# Cross-host write attribution (PROD writes executed from DEV over ssh)

Question class: "alguien escribió <archivo> en PROD y ninguna sesión de agente de PROD lo explica — ¿quién fue?". When a multi-agent fleet shares ssh keys between hosts, agents mutate remote hosts from their own host; the target host's session DB shows nothing and only auth.log + the authoring host's state.db close the case. Verified end-to-end 2026-11-03 (buzón-bob / ncl-diario cleanup audit).

## Case shape (when to reach for this)

- File on host A changed (mtime/hash matches a claimed timestamp), but host A's agent sessions/state.db contain no session writing it.
- Suspected third actor. Before theorizing, run the join below — in the verified case every "unexplained" write resolved to a DEV (`default`/Ragnar) session over `ssh prod`.

## Step 1 — Host A: bracket the writes with auth.log

```bash
grep -a 'Accepted' /var/log/auth.log | grep '<window>'
```

- Take each mtime (e.g. `20:58:01.7`) and look for `Accepted publickey for root from <IP>` lines within ±1 s. Every ssh tool call opens a fresh connection → one `Accepted` line per write command; the correlation is tight enough to pin command-level authorship.
- **Timezone caveat:** auth.log is in host-local time; if the artifact timestamps under audit are UTC (Z), convert before comparing (COT = UTC-5). State the conversion in the report.

## Step 2 — Map source IPs to hosts before attributing

- Container Tailscale IP + its public IP are BOTH valid sources: e.g. `100.86.8.81` (DEV container Tailscale) and `147.93.3.250` (DEV public) both mean DEV. Confirm from host B (`tailscale ip`, `curl -s ifconfig.me`) rather than assuming.
- **Noise to dismiss, never misattribute:** the internal docker poller (e.g. `10.0.1.8`) floods auth.log with thousands of `Accepted` lines (order 10³–10⁴ vs single digits for real authors). High volume = poller heartbeat, not a writer; check whether that IP correlates with any mtime within ±1 s before mentioning it at all.
- Record the mapping table (IP → host → role) in the report; attribution claims must cite IP + timestamp, never "it must have been us".

## Step 3 — Host B: pin the exact session + command in state.db

Use the state.db recipe (`references/agent-activity-state-db.md`): assistant rows' `tool_calls` are the only place the `ssh <A> '...'` command text lives.

```python
# messages.tool_calls LIKE '%<unique path or filename>%'
# window: timestamp BETWEEN epoch(mtime)-60 AND epoch(mtime)+60
```

- Match on a unique token of the artifact (path/filename) inside `tool_calls`, then read the full command: it shows `mkdir`, `mv`, `os.replace`, `chown/chmod 10000:10000` — i.e. exactly what landed on host A and in which session (join `session_id` → `sessions.title` for the narrative).
- Timing: the tool_call row is logged seconds BEFORE the mtime (dispatch → execution); allow the ±60 s window and report dispatch vs execution times separately.

## Step 4 — Prove scope with a diff, not memory

If a pre-change backup exists (good agents leave one, e.g. `cache/<cleanup>/doc/SSOT-prev-<hash>.md`), `diff` current vs backup:

```bash
diff --unchanged-line-format="" --old-line-format="OLD %dn" --new-line-format="NEW %dn" prev.md current.md
```

This converts "I only touched my row" into "1 line changed, NEW 199" — the strongest closing evidence. While diffing, enumerate intermediate hashes seen live (documents can pass through 2–4 states in seconds during write→verify→correct cycles); report each with size + timestamp so the auditor's timeline can be corrected, and check the FINAL state carries the corrected values.

## Report shape (reply to the auditor)

1. Authorship verdict per mark: table of (timestamp, auth.log evidence with IP, emitting session id) — or explicit "no matching session, author unattributed".
2. Timeline correction if the auditor's version missed intermediate states (they only see what they sampled).
3. Points where the auditor was right — concede them plainly; the goal is one shared true timeline, not winning.
4. Independent re-verification of the auditor's current-state numbers (ls/sha256/stat) so both sides agree on the frozen end-state.
5. Close: cero escrituras ajenas / N pendientes, fase congelada — no promises of future work.