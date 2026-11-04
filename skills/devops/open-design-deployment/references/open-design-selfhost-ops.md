<!-- Caso absorbido por F6 lote 3 el 2026-09-23 desde `devops/open-design-selfhost-ops`.
     Contenido íntegro; original en
     `data/archive/F6_lote3_20260923-155847/absorbidas/`. -->

---
name: open-design-selfhost-ops
description: "Deploy/run self-hosted OpenDesign (Docker+NPM+BYOK)."
license: Apache-2.0
metadata:
  author: "neuralcrew"
  version: "1.0"
---

# OpenDesign Self-Hosted Operations

Administer a self-hosted **OpenDesign** daemon (single Alpine image, `ghcr.io/nexu-io/od:latest`, port 7456) for a client/multi-brand design workbench. This is **server operations / deployment**, distinct from the built-in `open-design` skill which covers *using* the workbench tools as an agent.

The service pairs a code-agent CLI as its design runtime with a BYOK (Bring-Your-Own-Key) LLM provider, so it renders HTML/PDF/PPTX/MP4 artifacts from design-system-tokenized prompts.

## When to Use

Use this when a self-hosted OpenDesign daemon needs to be deployed, wired to a provider, exposed on a public subdomain, given client brand design systems, or when a run fails with a "requires OpenCode"/agent-not-found error. For simply *using* the workbench as an agent, use the built-in `open-design` skill instead.

## Activation contract

Trigger when asked to: deploy OpenDesign on a VPS; add/host it on a public subdomain; wire a provider (NaN-Builders, OpenAI, DeepSeek); create user design systems for a client brand; or debug "BYOK API runs require OpenCode / agent X".

## CRITICAL: BYOK API runs require a local code-agent CLI (OpenCode)

The single most important fact. **BYOK API runs do NOT work with a provider alone** — the daemon delegates its whole model/tool loop to a local code-agent CLI it spawns. The error:

```
BYOK API runs require OpenCode. Install OpenCode, then rescan local agents in Settings before retrying.
```

The daemon invokes `opencode run --format json` with the composed prompt on stdin, translating your BYOK provider credentials + model into OpenCode config. The official image does **not** bundle Claude/Codex/Gemini/OpenCode binaries — you must provide it.

- **Runtime auto-discovery:** the daemon PATH-scans at startup; any agent CLI visible in PATH is listed in Settings → Agents. `GET /api/agents` after a rescan shows ~27 definitions (opencode, claude, codex, byok-opencode, hermes, …).
- **BYOK profile:** `byok-opencode` / `opencode` is the API-backed OpenCode-compatible profile. Provider credentials (e.g. `https://api.nan.builders/v1`, model `deepseek-v4-flash`) are translated into OpenCode config per run.

## Mount a host OpenCode into a read_only container

The production container is `read_only: true` (good — keep it), so you mount the host binary into it rather than installing inside. Do NOT use the official `docker-compose.linux.yml`: it switches to `network_mode: host`, which breaks NPM/proxy routing. Keep the proxy network and just add mounts.

OpenCode on the prod host is a single glibc-linked ELF (`/home/hermes/.local/bin/opencode`, ~180 MB, v1.18.18). Mount the binary + host glibc libs + a writable HOME:

```yaml
environment:
  HOME: /home/opencode
  PATH: /mnt/host-opencode:/usr/local/bin:/usr/bin:/bin
volumes:
  - /opt/open-design/data:/app/.od          # persistent daemon data (bind mount)
  - /home/hermes/.local/bin:/mnt/host-opencode:ro
  - /lib/x86_64-linux-gnu:/lib/x86_64-linux-gnu:ro
  - /lib64:/lib64:ro
  - /opt/open-design/opencode-home:/home/opencode   # writable HOME for opencode
read_only: true
```

Verify before/after: run the same mounts in a throwaway `docker run --rm --entrypoint sh ghcr.io/nexu-io/od:latest -c "opencode --version"` — must print a version. `opencode run --help` should show `--format json`. `HOME` must be writable: `touch $HOME/.writetest`.

- **Ownership:** the OD container runs as uid 1001 (`open-design`), which on this host equals uid 1001 (`hermes`), so the host binary/libs are readable. After editing `docker-compose.yml`, `chown -R 1001:1001` any new data dirs, then `docker compose up -d --no-build` (recreates container; data bind mount persists).
- **Health:** `docker ps` shows `Up X (healthy)` and `docker logs open-design | grep 'listening on'` plus `readyToSend`/`schemaReady`. A transient `502` on the domain right after recreate is just the daemon still booting — wait for healthy.

## Deploy pattern (prod)

- **No host ports published.** The daemon is only reachable on the NPM docker network (`nginx-proxy-manager_proxy`). NPM + Cloudflare front it for TLS/WAF; `OPEN_DESIGN_ALLOWED_ORIGINS=https://<domain>` in `.env`. Bind host `0.0.0.0:7456` inside the container only.
- **Networks:** attach both `default` (compose) and the external `nginx-proxy-manager_proxy` so NPM can route to it.
- **Secure:** `OD_API_TOKEN=<openssl rand -hex 32>` (mandatory, auth via `Bearer`). `read_only: true`, `no-new-privileges:true`, `mem_limit: 512m`, `pids_limit: 256`, `tmpfs: /tmp`. UI browser login = username `open-design` + the token.
- **Persistence:** `/opt/open-design/data` on host → `/app/.od` in container. Contains `app.sqlite`, `design-systems/`, `artifacts/`, `brands/`, `connectors/`, `app-config.json`. Changing `read_only`/uid → may need `chown 1001:1001` on the data dir.

### Domain + HTTPS

1. **DNS** — Cloudflare A record `design` → prod public IP, proxied.
2. **NPM proxy host** — create via the *nginx-proxy-manager-api* skill (SQLite-backed, see that skill's references for the stale-password/SQLite pitfalls that two `docker exec npm-postgres psql` dead-ends). forward_host = the OD container IP on the NPM network, forward_port 7456, `forward_scheme: http`.
3. **LE cert DNS-01** — `POST /api/nginx/certificates` `provider:"letsencrypt"`, `meta.dns_challenge:true`, `dns_provider:"cloudflare"`, `dns_provider_credentials:"dns_cloudflare_api_token=<token>"`, `propagation_seconds:60`. **Pitfall:** certbot runs one at a time — a concurrent/previous issue returns `500 "Another instance of Certbot is already running."`; wait ~45 s and retry. The Cloudflare token is in the NPM letsencrypt `credentials/credentials-<n>` file on the host.
4. **Attach cert** to the proxy host via `PUT /api/nginx/proxy-hosts/{id}` with `certificate_id`, `ssl_forced:true`.
5. Verify `curl -s -o /dev/null -w "%{http_code}" https://<domain>/api/health` → 200.

## User design systems

User (per-deployment) design systems live in the daemon data dir, NOT the bundled image:

```
/app/.od/design-systems/<id>/   →  /opt/open-design/data/design-systems/<id>/
  manifest.json     # {"schemaVersion":"od-design-system-project/v1","id","name","category","description","source":{"type":"local"},"files":{"design":"DESIGN.md","tokens":"tokens.css"}}
  DESIGN.md         # ≥7 H2 sections; tokens.css provides --bg/--surface/--accent/--fg/etc.
  tokens.css
```

Create the folder on the host, scp the three files, `chown -R 1001:1001`. The daemon rescans on `/api/design-systems` (no restart needed). They appear as `user:<id>` with `status:"draft"`, listed above the bundled ones. `GET /api/design-systems` shows them.

Package naming: brand client. Local brand data in the *personajes* drive / `creative` brand skills (e.g. Golden #DDC316/#AB0F15/#1A1A1A + DM Serif Display, Lucky #8E1026/#C9A227/#F5EFE0/#121A15/#0E6B3A).

## Integration layers (how agents use it)

There are two directions, and they are NOT equivalent:

- **REST API (agents call the service):** real, `GET /api/design-systems`, `/api/projects`, `/api/skills`, `/api/design-templates`, `/api/plugins` all → 200 with `Bearer <token>`. This is how external agents (Ragnar/Bragi/Sindri/fleet) drive OD: brief + `designSystemId=user:<brand>` + BYOK runtime → artifact. Zero infra change; any Hermes profile can call it. Prefer this for pipeline integration.
- **MCP (stdio only):** `/api/mcp` → 404. OD's MCP is stdio, not HTTP, and its tools are read-only (project list/files/read, skills/plugins list) — good for catalog browsing, NOT for generating. Do not expect an HTTP MCP endpoint.
- **Agent-native mode (OD drives a CLI):** mount a code-agent CLI into the container (above) so OD *spawns* it for richer multi-file artifacts. That is the same OpenCode mount that BYOK requires — satisfying BYOK already gives you the agent-native path.

## Owner + auth

- `/api/health` → `{"ok":true,"version":"..."}`.
- `/api/agents` lists the PATH-scanned runtimes; `/api/projects` lists projects.
- Auth: every call `Authorization: Bearer <OD_API_TOKEN>`.

## Pitfalls

- **BYOK doesn't run without a local CLI** — see CRITICAL section. Surface symptoms include "BYOK API runs require OpenCode" and trace showing `agent_id: openai-api`.
- **Do not use `network_mode: host`** on the prod override (breaks NPM routing). Keep the proxy network + mounts.
- **NPM schema/DB reality:** NPM uses a host SQLite DB, not a Postgres container (`docker exec npm-postgres psql` fails). Inspect with alpine + sqlite3. See the `nginx-proxy-manager-api` skill.
- **IPv6 broken on some hosts** breaks `docker compose pull` (curl -6 → 000). Fix by adding an `/etc/hosts` IPv4 override for `ghcr.io` / `pkg-containers.githubusercontent.com`, commented and reversible.
- **UID mismatch:** if the daemon can't write the data dir after you recreate, `chown 1001:1001`. On this host uid 1001 = `hermes` which is also the opencode user — the binary is readable.

## Related skills / overlaps

- `open-design` (built-in) — *using* the workbench tools from an agent. This skill is the ops counterpart.
- `nginx-proxy-manager-api` — NPM proxy host + LE cert via API (SQLite). Overlaps the Domain+HTTPS step; reference it there.
- `creative/brand-logo-composites`, `creative/*` visuals — brand palettes to feed into design systems.

## References

- `references/prod-deploy-2026-09.md` — session-validated prod deploy trace (VPS .222): headless NPM stale-admin bcrypt rotation, SQLite proxy_host inspection, LE cert certbot-concurrency retry, cert attach, design-system package that worked. Use it to reproduce the exact steps and the two time-costly gotchas.
