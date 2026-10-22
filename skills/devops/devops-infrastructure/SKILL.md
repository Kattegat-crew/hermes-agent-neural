---
name: devops-infrastructure
description: "Use when auditing servers, containers or health monitors."
tags: [devops, infraestructura, monitoreo, contenedores, oom, salud, crons, conexiones]
---
# DevOps & Infrastructure Monitoring

Use when configuring, auditing, or maintaining server-side services, containers, or automated monitoring workflows.

## Core Philosophy
- **Stability First.** High-availability (HA) and resource limits (OOM prevention) are prioritized over rapid feature deployment.
- **Observability is non-negotiable.** Every service must have a health check, and every critical job must have logs that are accessible and actionable.
- **Identity-Aware Infrastructure.** Infrastructure is managed per tenant or per user profile (e.g., `helmer-gmail`, `jonathan-canva`).

## Monitoring & Health Checks
- **The Vigía Pattern:** Regular (e.g., every 2h) automated health checks for webhooks, ActivePieces, DBs, and critical flows.
- **OOM Prevention:** Always set `mem_limit` on containers. Use the "Measure → Limit" approach: observe normal usage, then set the limit to `usage * 2` to provide a safety ceiling without causing unnecessary kills.
- **Reporting:** Use Discord/Telegram for alerts. Maintain a distinction between "System Health" (technical uptime) and "Business/Marketing QA" (content quality).

## Identity & Connection Governance
- **Multi-Tenant Management:** When managing OAuth or sensitive connections, use a naming convention `{tenant}-{service}` to prevent cross-account leakage.
- **The 5 Layers of Connection Security:**
  1. **SOUL:** Agent identity defines allowed connections.
  2. **Engram Map:** A persistent mapping of `tenant -> connection_id` used for lookup.
  3. **Project Isolation:** Use separate AP Projects/Workspaces when scaling (Premium tier).
  4. **Auditor:** Continuous monitoring of connection usage (Vigía).
  5. **Technical Enforcement (The Law):** A wrapper (e.g., `ap_call`) that validates the caller's identity against the Engram map before executing the tool call.

## Troubleshooting & Maintenance
- **Log-First approach:** Before guessing a cause, check `docker logs`, `nginx` error logs, or specialized service logs.
- **_OOMKilled_ detection:** If a service dies, check if it was an Out-Of-Memory event.
- **Permission Fixes:** When encountering `Permission denied` on config files, ensure ownership is set to the service user (e.g., `chown hermes:hermes`).
- **Verify port exposure from INSIDE the container (false-positive guard, validated 19/10/2026):** a host `-p` flag or visible docker-proxy does NOT prove exposure. If the service listens only on `127.0.0.1` inside the container, the DNAT points at the container IP where nothing listens (curl → 000). Protocol: read `/proc/net/tcp` inside the container (`0100007F` = loopback, not exposed), then curl the container IP — before declaring a surface exposed in any audit report.

## Backup Failures (restic/rclone → cloud remote, validated 20/10/2026 PROD)
- **Diagnose in this order:** (1) read the job log (e.g. `/var/log/vps-master-backup.log`) and separate dump failures from snapshot/remote failures; (2) verify the remote repo is healthy (`restic -r <repo> snapshots --latest 5` + `stats`) — the last good snapshot date tells you when the breakage started; (3) measure upload throughput with a small `rclone copy` test file (10 MB, `--stats-one-line`); (4) run the real `restic backup` manually in background with a timing wrapper and tail the log — never judge from the cron's timeout alone; (5) check remote quota (`rclone about remote:`).
- **Timeout vs slowness are different bugs:** a script-side hardcoded timeout (e.g. `proc.communicate(timeout=600)` in `vps_master_backup.py`) that fires for days can mask a slow/degraded remote rather than a full outage. Before changing the timeout, run the backup manually to measure the REAL duration — raise the timeout to ~2× the measured worst case, not an arbitrary value. Validated fix (20/10/2026 PROD): replace the hardcoded value with an env-configurable `RESTIC_BACKUP_TIMEOUT` (default 3600 s, read in the script via `int(os.environ.get(...))` or config) AND make the script run a best-effort `restic unlock` before every snapshot so stale locks from aborted runs can never block the scheduled job. Re-prueba real after the patch: snapshot `dbf8a9b365` completed in 2781 s under OneDrive throttling (~0.3-0.4 MiB/s) → full run SUCCESS in 3257 s; expect ~1 h runs while throttling persists (normal, not a failure).
- **Cloud remote 5xx degradation:** Microsoft OneDrive via rclone can return intermittent `500 Internal Server Error` on uploads (plus HTTP2 connection force-close) even with ample quota — restic retries with backoff and the run stretches 2-3×. Rule out quota first (`rclone about`), then let retries finish; the fix is headroom in the timeout, not infrastructure changes.
- **Orphaned locks hygiene:** any manually launched (and killed/aborted) restic run leaves stale locks in the repo — run `restic unlock` after manual tests and before the next scheduled backup, or the cron run fails on lock errors.
- **Never leak tokens:** restic/rclone verbose logs can print full OAuth tokens on connection errors — redact before pasting logs into chats or tickets.

## Security-Exposure Triage (CVE / CA-compromise, validated 21/10/2026)
When a new CVE or CA compromise breaks, map exposure FIRST (live, never from memory), then patch:

**1. Runtime exposure mapping:**
- Inventory every container and its runtime version: for each app container run its language binary with `-v` (`php -v`, `node -v`, `python3 -V`) inside it — a vulnerable stack may hide inside an app image (e.g. `mautic:5.2-apache` = PHP 8.2.31).
- Map public surface: `docker port` per container AND `grep -h server_name /data/nginx/proxy_host/*.conf` inside the nginx-proxy-manager container for the real internet-facing domains. Remember the SSO-gate caveat: an SSO on the admin UI does NOT protect public app endpoints (Mautic tracking/forms hit PHP directly).
- For client domains behind Cloudflare, headers hide the backend stack — check actual hosting before claiming exposure.

**2. CA trust-store compromise checklist (eMudhra-style):**
- Test with a known-bad chain endpoint (incident sites publish per-CA test hosts). Use `curl -sS` — plain `-s` hides the error and you only see HTTP 000 without the reason; error 60 = chain rejected = protected, empty output = ambiguous, re-verify.
- Hosts: `dpkg -l ca-certificates` (PROD was `20260816ubuntu0.24.04.1` = patched).
- Per-container bundles: locate `/etc/ssl/certs/ca-certificates.crt` in the container and `grep -c <RootName>` it — NPM and Mautic (Debian 12) both had 0 emSign entries.
- Python bundles are SEPARATE from the system store: get the bundle path from `python3 -c 'import certifi; print(certifi.where())'`, grep it for the root name, and check `certifi.__version__`. Upgrade with `uv pip install --python python3 --upgrade certifi` (2026.05.20 → 2026.10.19 here). After upgrading, re-grep and confirm the exact dangerous root is GONE — the fixed bundle keeps other roots of the same vendor (benign C1/C3/G1 remained; the compromised ECC Root CA - G3 and AAA Certificate Services were removed), so a vendor-name grep count greater than 0 is NOT proof of failure.
- grep -c exits 1 on zero matches: append `|| true` or the `&&`/`||` chain prints both the 0 and a fallback message, confusing the output.

## Automation & Cron Jobs
- **Cron store ownership = whole-fleet kill switch (validated 19/10/2026 PROD):** `/opt/data/cron/jobs.json` must be `10000:10000 600`. Any root-run `cp`/`hermes cron` rewrites it `root:600`; the scheduler (uid 10000) then dies on `Permission denied` and EVERY enabled job freezes with `last_run: None` — silently, no visible error. Fix (D-I-V-E): backup → `chown 10000:10000` + `chmod 600` → verify one real tick (fresh `last_status` or a claimed job). Prevention: cheap check `stat -c '%U:%G %a'` + dead-man monitor (store unwritten > 2× interval = alert). Hard rule: NEVER run the Hermes CLI as root over `/opt/data`; use `docker exec -u 10000 hermes-agent ...`. When auditing, check `last_run` staleness before assuming the fleet is running.
- **Ticket/mailbox closes do not notify humans:** an agent processing an inbox ticket writes its answer into the JSON itself (`done/`, `respuesta` field) and does not send WhatsApp on its own. If the Administrator asked "que me reporte", relay the close content to the human chat and verify delivery via send logs (`Sending response ... to <chatId>`).
- **Job Ownership:** Distinguish between *System/Maintenance Crons* (Vigía/Infra) and *User/Personal Crons* (Ragnar/Roshi).
- **Continuous Learning:** Use memory-saving crons to ensure agents maintain their context and history.
- **Error Handling:** Ensure crons are non-interactive and deliver status via designated channels.

## Reference Files
- `references/connection-governance-layers.md`: Detailed breakdown of the 5-layer security model for multi-tenant integrations.
- `references/vigia-prod-audit-checks.md`: Vigía's verified prod checks (Golden/Paradise webhooks, ActivePieces flows, nightly email `accepted` via `file.FLOW_RUN_LOG`, `ap-db` vs `nca-postgres`, Discord delivery pitfalls).
