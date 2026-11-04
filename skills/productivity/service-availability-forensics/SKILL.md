---
name: service-availability-forensics
description: "Use when a service flakes or a watchdog fix looks false."
tags: [docker, watchdog, monitoring, false-green, deploy, forensics, logs]
version: "1.0.0"
author: ragnar
metadata:
  hermes:
    tags: [docker, watchdog, monitoring, false-green, deploy, forensics]
    related_skills: [cron-watchdog-scripts, vps-ops]
---

# Service Availability Forensics

## When to use
- A user reports a service "se cae de vez en cuando" (intermittent outages).
- A watchdog/monitor bot claims `[FALLO] X -> arreglado (re-check OK)` and you must
  audit whether the fix was real.
- A health probe result contradicts what users experience (monitor says OK, users
  see failures, or the reverse).
- You must distinguish real crashes from deploy-window micro-outages.

Goal: find the real cause and decide whether the monitor's "fix" was real, a
coincidence, or a false green.

## Golden rule
A monitor's claim of "fixed" is a hypothesis, not evidence. Verify with
container state and logs before accepting or repeating it.

## Forensic sequence (ordered, cheap → deep)

1. **Container lifecycle first** — one `docker inspect` answers the biggest question:
   ```bash
   docker inspect <c> --format 'RestartCount={{.RestartCount}} OOMKilled={{.State.OOMKilled}} Created={{.Created}} Started={{.State.StartedAt}}'
   ```
   - `Created == Started`, `RestartCount > 0` → process died, auto-restart (crash/OOM path).
   - `Created != Started`, `RestartCount == 0` → container was RECREATED externally (deploy).
   - Neither differs and error 000/timeouts persist → network/DNS/port-bind path, not the container.
2. **Timeline from logs, not from memory**: `docker logs -t <c> --since 48h` and count
   "server running / listening" lines — each is a boot. Grep for real process errors.
   Zero errors + multiple boots = external lifecycle events, not crashes.
3. **Correlate deploys with boots**: `ls -la --time-style='+%m-%d %H:%M'` on the app dir;
   mtimes of config/code files that fall seconds before a boot identify what/who deployed.
4. **Identify the actor**: `last`, `grep Accepted /var/log/auth.log`, `crontab -l` on the
   host, `docker ps -a | grep -iE 'watchtower|coolify'` (auto-recreators).
5. **Re-run the monitor's own probe yourself** and read its state files
   (snapshot of last scan + per-run output records). Note the monitor's cadence: with a
   change-gated watchdog, a failure can stay invisible for a whole cycle and the
   "fix history" has gaps.
6. **Clock sanity**: when comparing remote logs vs local monitor runs, check the remote
   server's timezone first — offset mistakes silently break every correlation.

## False-green patterns (recognize, don't trust)
- **Recovery coincidence**: probe's FAIL lands inside a known outage window; by the
  monitor's next tick the service already self-recovered (deploy finished, Docker
  restart policy fired). The monitor logs "arreglado" without doing anything.
- **Suppressed monitor runs**: change-gated watchdogs that only wake the agent on diff
  mean `no_change` runs leave failures unreported between ticks — read the monitor's raw
  per-run output, not just delivered chat messages.
- **Probe-scale blindness**: a 2h-cron probe samples ~0.01% of the time; 30s outages
  appear "rare" to it and "constant" to users. Both are right; compute the outage
  window from boots/deploy times instead of arguing.

## Classic cause: deploy-window micro-outages
Compose entries like `command: npm install && node server.js` (or any install/build step
in the boot path) keep ports closed for the whole install on every recreate. Symptoms:
intermittent `000`/timeout on health checks and public endpoints, matching deploys,
no process errors. Fix (requires owner approval on prod): remove install from the boot
path (pre-install the volume or bake an image) → restart drops to ~2s and phantom
FAILs disappear.

## Decision table
| Evidence | Verdict | Action |
|---|---|---|
| RestartCount>0 + process errors | Real crash | Debug app; restart policy is masking frequency |
| RestartCount=0, Created≠Started, no errors | External recreate/deploy | Correlate actor+mtimes; shrink boot window |
| 000/timeouts, container healthy all along | Network/DNS/bind | Check resolver, firewall, port bindings, upstream |
| Monitor "fixed" + service already up before its re-check | False green | Recompute what actually recovered it |

## Pitfalls
- `docker events` without `--until` streams forever — always wrap in `timeout`.
- Public DNS on the agent host may not resolve client domains (and a domain can be
  mis-pointed at the DNS registry level): resolve via `https://dns.google/resolve?name=...&type=A`
  before declaring a site "down".
- A local `curl` failure to a customer domain may be your own resolver, not the site.
- Minimal containers often lack `ip`/`ss`: use `hostname -I`, `/proc/net/route`, `docker inspect`.
- Watchdog liveness checks that match process names (`pgrep -f <launcher>`) go stale when the launcher binary/path changes — they report the whole fleet DOWN while every unit is active. Detect via systemd instead: `systemctl is-active <unit>` per profile gateway (validated 03/11/2026 DEV: replaced legacy pgrep in `vps_health_watchdog.py`; recurring false CRITICALs stopped).
- The systemd check itself goes stale one step later: after a profile is folded into the central multiplexer its unit is deliberately RETIRED (`systemctl is-active` → inactive, `is-enabled` → not-found), and a per-unit watchdog flags it `stopped` forever — a new class of false CRITICAL. Fix: a profile listed in `gateway_state.json` → `served_profiles` with no own unit is HEALTHY by definition (served by the shared `hermes-agent.service`); treat unit-missing + in-served_profiles as a distinct "servido por multiplexor" state, not a failure. Read the set at every run (cheap JSON read), and only the watchdog's per-profile entries that carry a `profile` key need it (validated 03/11/2026 DEV: `vps_health_watchdog.py` dry-run went CRITICAL → WARNING with no other change).
- "Folded into the central multiplexer" must be verified at runtime, never accepted from a task checkbox: a gateway that boots STANDALONE logs `Profiles NOT served (their bots stay silent): ...` — disabling the old per-profile unit then leaves that bot MUTE with zero errors anywhere. After any profile-consolidation change, grep the gateway log for that line and ping the profile before declaring done (validated 03/11/2026 DEV: Vigía orphaned this way by spec task 4.4; `journalctl -u <unit>` showed a clean SIGTERM stop = deliberate retirement).

## References
- `references/2026-08-31-golden-webhook-false-green.md` — full case: Vigía 2h probe vs
  prod webhook-gateway deploy windows, evidence trail, host/service map of prod node
  169.58.189.222, false-green confirmed by timeline correlation.
