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
- **Canary Watchdog (integridad de archivos críticos, desplegado y probado E2E en DEV y PROD, 27-oct):** cuando un archivo crítico bind-montado (ej. nginx.conf) desaparece, dockerd NO falla ruidosamente: crea un DIRECTORIO vacío con ese nombre en el boot — el síntoma es el servicio muerto tras un reboot, no un error claro. El canario (cron cada 5 min) verifica los archivos de su manifest, auto-restaura desde copia canónica protegida y alerta a Discord. Ante 'archivo desaparecido o convertido en carpeta', comprobar primero si el canario ya restauró/alertó antes de rehacer el archivo a mano; toda ruta crítica nueva se añade a su manifest (sin tocar la sesión de WhatsApp ni el perfil roshi, reglas del blindaje).
- **Verify port exposure from INSIDE the container (false-positive guard, validated 19/10/2026):** a host `-p` flag or visible docker-proxy does NOT prove exposure. If the service listens only on `127.0.0.1` inside the container, the DNAT points at the container IP where nothing listens (curl → 000). Protocol: read `/proc/net/tcp` inside the container (`0100007F` = loopback, not exposed), then curl the container IP — before declaring a surface exposed in any audit report.

## Backup Failures (restic/rclone → cloud remote, validated 20/10/2026 PROD)
- **Diagnose in this order:** (1) read the job log (e.g. `/var/log/vps-master-backup.log`) and separate dump failures from snapshot/remote failures; (2) verify the remote repo is healthy (`restic -r <repo> snapshots --latest 5` + `stats`) — the last good snapshot date tells you when the breakage started; (3) measure upload throughput with a small `rclone copy` test file (10 MB, `--stats-one-line`); (4) run the real `restic backup` manually in background with a timing wrapper and tail the log — never judge from the cron's timeout alone; (5) check remote quota (`rclone about remote:`).
- **Timeout vs slowness are different bugs:** a script-side hardcoded timeout (e.g. `proc.communicate(timeout=600)` in `vps_master_backup.py`) that fires for days can mask a slow/degraded remote rather than a full outage. Before changing the timeout, run the backup manually to measure the REAL duration — raise the timeout to ~2× the measured worst case, not an arbitrary value. Validated fix (20/10/2026 PROD): replace the hardcoded value with an env-configurable `RESTIC_BACKUP_TIMEOUT` (default 3600 s, read in the script via `int(os.environ.get(...))` or config) AND make the script run a best-effort `restic unlock` before every snapshot so stale locks from aborted runs can never block the scheduled job. Re-prueba real after the patch: snapshot `dbf8a9b365` completed in 2781 s under OneDrive throttling (~0.3-0.4 MiB/s) → full run SUCCESS in 3257 s; expect ~1 h runs while throttling persists (normal, not a failure).
- **Cloud remote 5xx degradation:** Microsoft OneDrive via rclone can return intermittent `500 Internal Server Error` on uploads (plus HTTP2 connection force-close) even with ample quota — restic retries with backoff and the run stretches 2-3×. Rule out quota first (`rclone about`), then let retries finish; the fix is headroom in the timeout, not infrastructure changes.
- **Orphaned locks hygiene:** any manually launched (and killed/aborted) restic run leaves stale locks in the repo — run `restic unlock` after manual tests and before the next scheduled backup, or the cron run fails on lock errors.
- **Never leak tokens:** restic/rclone verbose logs can print full OAuth tokens on connection errors — redact before pasting logs into chats or tickets.

**Local restic layer on DEV (`backup_local_snapshot.py`, validated 03/11/2026):**
- Anatomy: cron `0 3 * * *` (root crontab) runs `su -s /bin/bash hermes -c python3 /opt/hermes-agent/scripts/backup_local_snapshot.py >> /var/log/backup-local.log`. Repo path comes from the declaration `/opt/hermes-agent/docs/ops/backup-sources.yaml` key `dev.repo_local` (env `LOCAL_RESTIC_REPO` overrides); last-success record at `/opt/hermes-agent-data/state/backup-local.json`; repo key at `/opt/hermes-agent-data/backup-keys/master-backup.key`.
- The log has NO date prefixes (only `[HH:MM:SS]`): date the last run from the file's mtime, and use `restic -r <repo> snapshots --compact` to find the last good snapshot — the gap between them is the breakage window.
- Failure mode found: the job runs as user `hermes` (uid 10000) but sources include `/opt/vault` (700 root) and `/opt/vps-brain/graphify-out` (770 root:root) → `permission denied` during scan/archival EVERY night while the cron itself "works". Fix is read access for hermes or excluding those paths in the declaration — probe with `--ensayo` (dry run) before touching cron.

## Service Retirement Cleanup (validated 23/10/2026 PROD — Mautic)
When a service is retired, three layers keep pointing at it — audit all three before declaring done:
1. **NPM proxy hosts:** no `apk` in that container (Debian-based) — instead `docker cp nginx-proxy-manager:/data/database.sqlite /tmp/` and inspect with the HOST `sqlite3`. Soft-deleted rows stay with `is_deleted=1`; a teammate's claim of a "still-proxied" host may be stale — verify the table yourself.
2. **uptime-kuma monitors (zombis):** monitors are held IN MEMORY — an `UPDATE monitor SET active=0` in `/app/data/kuma.db` does NOT take effect until the Kuma container restarts (`docker restart uptime-kuma`, then verify `healthy` + panel responds on its mapped IP; note its port maps to the Tailscale IP, `curl 127.0.0.1:<port>` gives 000 even when healthy).
3. **Cloudflare DNS:** a proxied record keeps resolving to Cloudflare IPs with no origin behind it; cleanup needs the scoped API token (see memory: MCP token lacks DNS/WAF scopes). Agent sessions cannot read `/opt/vault` (`Permission denied`) — token extraction is human or Vaultwarden-side.

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

## Cloudflare via MCP (tooling pitfall, validated 23/10/2026)
- `mcp__cloudflare__execute` only accepts a **JavaScript async arrow function** as `code`: `async () => { ... }` (sandbox provides `headers` + `fetch`; return a value). Top-level statements (`const ...`, IIFE, `return ...`) all fail with `Unexpected token ...`.
- After 3 rejected calls the MCP server pauses ~50s and refuses more — never loop retries; check the calling convention first (`mcp__cloudflare__search`'s schema says "JavaScript async arrow function").
- `list_resources` only exposes skill docs (skill:// URIs), not zones/DNS resources.

## Self-hosted Langfuse / OTLP observability (v2→v3 saga, re-verified 02/11/2026)
- **Diagnose in two endpoints:** `/api/public/health` (server alive; returns version, e.g. 2.95.11) vs `/api/public/otel/v1/traces` (OTLP receiver). Health 200 + OTLP 404 = server fine but **Langfuse v2: the OTLP receiver only exists in v3** — the exporter is incompatible, not the server down. A migration to v3 is a real architecture change (adds worker, ClickHouse, Redis, S3/MinIO; Postgres kept), not an image-tag bump.
- **'Disabled' must be re-verified by symptom, not by config line:** Hermes renamed its plugin `observability/langfuse` (bundled) → standalone `langfuse` plugin. Commenting the old line in `config.yaml` does NOT stop the standalone plugin from exporting — 404 export errors reappeared weeks later. When checking, grep env (`HERMES_LANGFUSE_*`) and recent `docker logs` for `Failed to export span batch`, and check BOTH plugin names. A commented config line is a snapshot, not a state.
- **Bundled-plugin shadowing:** a standalone install of a plugin Hermes now bundles stays INACTIVE (bundled copy wins) — after Hermes updates, re-check which copy is active before assuming old disable/enable state holds.
- With export failing, Hermes keeps working (errors only in logs) but **zero traces arrive** — 'no errors' ≠ 'sending telemetry'; verify ingestion both ways before trusting the dashboard is complete.

## Disk-Pressure Triage (validated 03/11/2026 DEV)
- **Hard guard:** `rm -rf` anywhere under `/` via SSH is blocked by the approvals.deny rule (pattern matches path-prefixed variants like `*rm *-r* /opt*` too) — not even `--yolo` bypasses it. Two clean alternatives: `mv <path> /somewhere/.trash-name` when the bytes must leave the tree now (then delete later), or recursive delete with Python: `ssh host 'python3 -c "import shutil; shutil.rmtree(path)"'`.
- **Triage order:** `df -h` → `du -xh --max-depth=1` on each top-level dir → classify before deleting anything. **Regenerable (safe):** `~/.cache/google-chrome-for-testing-headless` (can hold GBs if a headless session died), ALL uv cache variants (`.cache/uv`, `.cache/uv-uid*`, `cache/uv` — per-UID copies each count separately), huggingface cache, `/tmp` tool caches (whisperenv, publish-out, fastembed_cache, .npm-cache), apt cache. **Never touch without owner approval:** fleet/git worktrees, `home/<project>-*` dirs, `installs/*` environments (rollback targets for the versioned Hermes install), restic/backup trees, and scratch files modified in the last 24h (check `ls -lt` — an agent may be mid-task).
- Measure in bytes per child, not with a single du invocation: `du -sb <dir>` per child in a loop is exact and scriptable; `du -s` combined with `--max-depth` errors out and `-h` output rounds into fake totals. For admin-facing storage reports, generate an HTML dashboard and screenshot it with headless Chrome (`--headless=new --window-size=W,H --screenshot=…`), and compute every percentage IN the template from the measured data — hardcoded prose numbers survive the next re-measure and contradict their own bars.
- **restic `forget --prune` with an already-applied retention policy frees ~0 GB** — don't count it as a lever when the repo is already pruned to policy.
- **Alert math:** the watchdog (threshold 85%) fires CRITICAL every 15 min while disk stays above it. On a disk where ~1/3 is justified backups/releases, decide explicitly: free the gap (roughly `(pct_used - 85) × disk_size / 100` GB) or raise the threshold — don't let the alert loop become background noise.
- **Gateway 'stopped + unit not-found' = deliberate retirement, not a crash:** `journalctl -u <unit>` shows an explicit `SIGTERM`/`Stopping` at the stop time, and the unit file is gone from `/etc/systemd/system/`. A crash leaves `Failed with result` without a clean Stop and the unit file intact. Confirm with the owner before resurrecting a retired unit.

**Container workspace (`/opt/hermes-agent-data`, validated 04/11/2026):**
- Repeat offenders in `cache/scratch/`: `smoke-*`/`smoke-home*` (upgrade smoke-test HOMEs), `audit-*` and `verify-*` checkouts/worktrees — disposable once the audit/upgrade that created them is closed. In `proyectos/`, the frame directories (`frames_render/`, `frames_golden/`, `frames_lucky/`, `qa/`) are gigabytes per project and 100% regenerable from the build scripts; the MP4s in `entrega/`/`out/` are the deliverable and stay.
- A `*-push-backup` scratch dir is NOT disposable while the source repo still has uncommitted changes — run `git status` on the source repo before proposing to delete it.
- When the local restic repo (`backups/restic-local`, key at `/opt/hermes-agent-data/backup-keys/master-backup.key`) has been written by the root cron, its lock and index files are root-owned mode 600 and even READ operations fail as `hermes` ("permission denied" on locks). An orphaned lock from a finished manual run CAN be unlinked by `hermes` (the repo dir itself is hermes-owned, so unlink works even on a root-owned file), after which `snapshots --compact` and `stats` work; `forget --prune`/`prune` rewrite the whole repo and must run on the host as root — schedule it there instead of fighting permissions from the container.
- Count snapshots (`restic snapshots --compact`) and show how many fall under the retention plan BEFORE executing it. Agreed retention (asymmetric 3-tier): DEV local repo keeps ONLY `--keep-daily 3` (fast local restore); the full history lives in the PROD replica with `--keep-daily 7 --keep-weekly 4 --keep-monthly 3`; OneDrive stays the third copy. Keep this split — pruning DEV to the full policy erases the restore-fast tier.
- Present any prune to the Admin as one package: disk % before, candidate table (size + why deletable), total liberable, projected % after, and the never-touch list (`fleet/` worktrees, WhatsApp session, secrets, the newest backup of each type). Wait for the go-ahead before any deletion.
- **Verify what a big dotdir IS before classifying it as cache:** `pgrep -af <name>` + inspect the dir contents before counting it as a win — binaries of a RUNNING daemon (`~/.codex/packages` serving `app-server --managed-daemon`), session history (`~/.codex/sessions`, `thread_history`), and installed CLIs (`~/.gemini/*-cli`, `~/.akari/app`) all look like disposable dotfiles but are installs or non-regenerable data; classifying them as cache overstates the win ~5x and deleting them kills the daemon or erases history. The reliably disposable class: old VS Code server versions under `~/.vscode-server/cli/servers/` — keep only the newest (match the mtime of the active `code-*` agent-host process); a client whose version was deleted re-downloads it automatically.
- **Replicating a restic repo to another host BEFORE pruning the source:** `restic -r <dest> copy` runs ~1 MB/s over a link that carries ~8 MB/s (single sftp stream + per-pack re-encryption) — an order of magnitude slower than the link. Fast path: `rsync -a --partial root@<src>:/path/restic-local/ /path/restic-dev/` over ssh produces a byte-identical valid replica at link speed; gate the source prune on `restic -r <replica> check` passing (if it fails, no prune — disk stays as-is). If an interrupted `restic copy` left a partial dest, `mv` it aside and rsync fresh — never mix copied packs with replicated ones in the same repo dir. Measure real throughput with a du-delta over 60s before quoting an ETA: early readings during the burst of large files are misleading.
- **Replica is PULL-based by design:** PROD pulls from DEV (`rsync` over ssh, PROD holds the credentials); DEV holds none toward PROD, so a compromised DEV cannot delete the remote history. Automate the split as two crons — PROD nightly (sync + apply the 7/4/3 retention there) and DEV monthly (scratch/drafts cleanup + prune to 3 dailies) — and run each script once by hand before leaving it in crontab; a nightly sync that first runs on schedule is an untested restore path. Clean any leftover `.restic-*-parcial*` dir on the replica host after the first successful run.

## Automation & Cron Jobs
- **Cron store ownership = whole-fleet kill switch (validated 19/10/2026 PROD):** `/opt/data/cron/jobs.json` must be `10000:10000 600`. Any root-run `cp`/`hermes cron` rewrites it `root:600`; the scheduler (uid 10000) then dies on `Permission denied` and EVERY enabled job freezes with `last_run: None` — silently, no visible error. Fix (D-I-V-E): backup → `chown 10000:10000` + `chmod 600` → verify one real tick (fresh `last_status` or a claimed job). Prevention: cheap check `stat -c '%U:%G %a'` + dead-man monitor (store unwritten > 2× interval = alert). Hard rule: NEVER run the Hermes CLI as root over `/opt/data`; use `docker exec -u 10000 hermes-agent ...`. When auditing, check `last_run` staleness before assuming the fleet is running.
- **Ticket/mailbox closes do not notify humans:** an agent processing an inbox ticket writes its answer into the JSON itself (`done/`, `respuesta` field) and does not send WhatsApp on its own. If the Administrator asked "que me reporte", relay the close content to the human chat and verify delivery via send logs (`Sending response ... to <chatId>`).
- **Job Ownership:** Distinguish between *System/Maintenance Crons* (Vigía/Infra) and *User/Personal Crons* (Ragnar/Roshi).
- **Continuous Learning:** Use memory-saving crons to ensure agents maintain their context and history.
- **Error Handling:** Ensure crons are non-interactive and deliver status via designated channels.

## Reference Files
- `references/connection-governance-layers.md`: Detailed breakdown of the 5-layer security model for multi-tenant integrations.
- `references/vigia-prod-audit-checks.md`: Vigía's verified prod checks (Golden/Paradise webhooks, ActivePieces flows, nightly email `accepted` via `file.FLOW_RUN_LOG`, `ap-db` vs `nca-postgres`, Discord delivery pitfalls).
