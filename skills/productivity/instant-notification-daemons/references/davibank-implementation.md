# DaviBank Purchase Alert — concrete implementation (Ragnar, Aug 2026)

Working instance of the 5 guarantees in `SKILL.md`. Stack: Gmail IMAP IDLE push → Python stdlib daemon → WhatsApp send → JSON state file → cron watchdog.

## Files (all in /opt/data/scripts/ on the agent VPS)

- `davibank_imap_daemon.py` (v2.2) — main daemon
- `davibank_supervisor.py` — watchdog script (cron, no_agent)
- `davibank_creds.json` — OAuth token, chmod 600, auto-refresh
- `davibank_state.json` — pointer state (`last_uid`)
- `davibank_daemon.log` / `davibank_daemon.lock` (flock prevents double-start)
- `README-davibank.md` — operational doc incl. incident postmortems

## Flow

1. IMAP login (OAuth2 XOAUTH2) to the user's Gmail, search `FROM DAVIbankInforma@davibank.com`.
2. Baseline on startup: `max(stored_last_uid, max UID in mailbox)` → no replay of old mail on restart.
3. Issue IDLE; on push (drain with `select.select()` + `M.sock.settimeout(30)`), fetch new UIDs > `last_uid`.
4. Parse merchant / amount / date / time from the HTML body (bank sends HTML-only; parse `text/html` part). Validate: amount and date non-empty, else raise → retry later (guarantee 3: no corrupted alerts).
5. **Pointer advances ONLY after WhatsApp send returns success** (`POST 127.0.0.1:3000/send` with chatId + message). Failure = pointer stays = retry next cycle (guarantees 1-2).
6. Ignore mail older than 24h (stale-arrival blindaje).

## v2.1 → v2.2 postmortem (3 chained failures, one missed purchase)

- v2.1 used `select.select()` without `import select` → every Gmail push crashed the daemon with NameError → silent crash-loop every ~20s, looked alive to naive checks. (Guarantee 5.)
- Pointer advanced at *processing* time, not *delivery* time → on reconnect it skipped the real purchase (BOLD $57.000, Visa Platinum) without ever notifying. (Guarantees 1-2.)
- The 5PM fix of that day was half-applied; the watchdog kept relaunching the broken code, masking the crash-loop. (Ops rule: kill everything, start fixed version once, verify PID + log through first event.)
- 30s socket timeout was shorter than the IDLE drain cycle → connection died exactly when mail arrived. (Guarantee 4: 180s connection / 30s drain.)

## Recovery pattern (validated)

Rewind `last_uid` in `davibank_state.json` to the UID *before* the missed event → restart daemon → it re-detects the real event and delivers the alert. Log line `AVISO enviado uid=44820` confirms. This is both the repair AND the end-to-end test (no synthetic events needed).

## Watchdog

Cron `davibank-daemon-watchdog`, schedule `*/10 * * * *`, `no_agent`, runs `davibank_supervisor.py`: restarts daemon if dead; checks lock (flock) to avoid duplicates. Daemon is independent of the Hermes gateway process — gateway restarts don't touch it.

## Endpoint notes

- WhatsApp send: `POST http://127.0.0.1:3000/send` `{"chatId": "<chat>@lid", "message": "..."}` (bridge on same host).
- Gmail push via IMAP IDLE needs the extended Gmail IMAP scope; plain readonly is NOT sufficient for IDLE.
