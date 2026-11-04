---
name: open-design-deployment
description: "Use when deploying or operating OpenDesign (OD)."
tags: [open-design, docker, byok, opencode, npm, deploy]
license: Apache-2.0
metadata:
  author: "neuralcrew"
  version: "1.0"
---

# OpenDesign Deployment & Operation

## Activation Contract

Use when deploying or operating **OpenDesign** (`nexu-io/open-design`, Apache-2.0, ~94k stars). It is the open-source Claude-Design alternative: a local-first dev tool/daemon that turns a coding-agent CLI into a design engine (prototypes, landings, dashboards, decks, docs, image/video → real HTML/PDF/PPTX/MP4). Use it for **client landings, decks, docs, dashboards** — NOT for character posters / AI reels (those stay on fal/Seedance/ElevenLabs).

## How OpenDesign works

- Not an LLM. A **daemon (Node, Express) + web UI (Next.js)** that spawns a coding-agent CLI as the design engine, feeds it a brief + `SKILL.md` + working dir, and streams output into a sandboxed iframe.
- Catalogues: **functional skills**, **design-templates** (prototype/deck/doc/HyperFrame), and **design systems** (`DESIGN.md` packages).
- Engine is BYOK (any OpenAI-compatible endpoint) or a local CLI (Claude Code / OpenCode / Hermes, 26 supported — Hermes has a native ACP adapter).
- Exposes a **stdio MCP server** (read-only) so agents can read live project files (`od project list`, `od files read <id> <path>`).
- UI login: username `open-design`, password = the generated `OD_API_TOKEN`.

## Deployment (Docker compose on prod .222 VPS)

1. **Create `/opt/open-design/`** with `data/` subdir (persistence bind-mount).
2. **`.env`**: `OPEN_DESIGN_IMAGE=ghcr.io/nexu-io/od:latest`, `OPEN_DESIGN_PORT=7456`, `OPEN_DESIGN_MEM_LIMIT=512m`, `OPEN_DESIGN_ALLOWED_ORIGINS=https://design.<domain>`, `OD_API_TOKEN=$(openssl rand -hex 32)`. `chmod 600`.
3. **`docker-compose.yml`** (see `templates/docker-compose.yml`): base official file but with these diffs — **no `ports:` mapping** (only NPM reaches it), **`OD_BIND_HOST: 0.0.0.0`** (listen inside container), **bind-mount `data:/app/.od`**, `read_only:true`, `no-new-privileges:true`, mem cap, `restart: unless-stopped`, join the external NPM network (`nginx-proxy-manager_proxy`).
4. `docker compose pull && docker compose up -d --no-build`.
5. Verify: `docker inspect --format '{{.State.Health.Status}}' open-design` → `healthy`; `docker exec open-design node -e "fetch('http://127.0.0.1:7456/api/health').then(r=>r.text()).then(console.log)"` → `{"ok":true,"version":...}` (the daemon listens inside the container; **curl to host `127.0.0.1:7456` will NOT answer** because there is no host port mapping).

### PITFALL: ghcr pull fails on IPv6-broken hosts

This VPS has a global IPv6 address but the route is broken (`curl -6` → 000), so `docker pull` via ghcr.io hangs/fails with `read: connection reset by peer`. Fix: pin IPv4 for ghcr + layer hosts in `/etc/hosts`:

```
140.82.121.33 ghcr.io
185.199.108.154 pkg-containers.githubusercontent.com   # (also 109/110/111)
```
Then `docker pull` works. Verify whether the host can even reach the registry with `curl -4 -s -o /dev/null -w "%{http_code}" https://ghcr.io/v2/` (401 = reachable).

### NPM proxy host + Let's Encrypt cert

The NPM instance on prod uses **SQLite** (`/opt/docker/nginx-proxy-manager/data/database.sqlite`), NOT postgres/mysql. Two routes to configure a proxy host: the REST API (preferred) or direct SQLite. See `references/npm-proxy-and-cert.md` for the exact API flow, the password-rotation recipe, and gotchas. High-level:
- `POST /api/tokens` with `{identity, secret}` → JWT.
- `POST /api/nginx/proxy-hosts` with `domain_names`, `forward_host`, `forward_port`.
- `POST /api/nginx/certificates` with `provider:"letsencrypt"` (DNS-01 + cloudflare) then `PUT` proxy host to attach `certificate_id`.
- **`forward_host`**: use the container's IP on the NPM docker network (e.g. `172.19.0.7`), NOT `127.0.0.1`. (The `172.19.0.1` host-gateway IP also works for host-network services — reels used it.) It must be reachable from the NPM container.

### DNS (Cloudflare)

Create the A record via CF API (token is in NPM's `/opt/docker/nginx-proxy-manager/letsencrypt/credentials/credentials-*`): `curl -X POST .../zones/<zone_id>/dns_records` with `{"type":"A","name":"design","content":"<vps_ip>","proxied":true}`. Provisioning the record BEFORE emitting the cert lets DNS-01 validate.

## Design systems (brand packages)

Drop brand packages under `/app/.od/design-systems/<slug>/` (host: `/opt/open-design/data/design-systems/<slug>/`) then `chown -R 1001:1001` (user `open-design`). The daemon scans on `/api/design-systems` request — a daemon restart is NOT required, just refresh the picker. Each package has 3 files:

- `manifest.json` — `schemaVersion: "od-design-system-project/v1"`, `id` (= folder slug, ASCII), `name`, `category`, `description`, `source`, `files: {design:"DESIGN.md", tokens:"tokens.css"}`.
- `DESIGN.md` — **at least 7 substantive H2 sections** (theme, color roles, typography, spacing, components, motion, accessibility, anti-patterns, agent prompt guide). No fixed 9-section template. Keep prose and `tokens.css` in sync.
- `tokens.css` — `:root { --bg; --surface; --accent; --accent-2; --fg; --fg-muted; --border; --font-display; --font-body; --radius; --radius-pill; --ease-standard; --motion-enter; --motion-exit; }`.

Verified packages for the clients exist in this repo: `golden-game` (dark #1A1A1A / #DDC316 gold / #AB0F15 crimson / neon #9400D3, DM Serif Display + DM Sans, Goldie mascot) and `lucky-brothers` (ivory #F5EFE0 / #8E1026 crimson / #C9A227 gold / #121A15 midnight / #0E6B3A green, DM Serif Display + DM Sans, Lucky clover). Authoring source-of-truth lives in `docs/design-systems.md` and `design-systems/README.md` of the repo.

## CRITICAL: BYOK API runs REQUIRE OpenCode mounted in the container

The BYOK provider is NOT a plain API call. For BYOK runs the daemon **spawns** `opencode run --format json` as the model/tool loop (`byok-opencode` profile, §5.2 of agent-adapters). The daemon PATH-scans for agent CLIs **at startup**. If OpenCode is not visible in PATH, the run fails with `BYOK API runs require OpenCode. Install OpenCode, then rescan local agents in Settings before retrying.`

Host has OpenCode at `/home/hermes/.local/bin/opencode` (ELF glibc binary, v1.18.18; `opencode run --help` shows `--format json`). The OD image is Alpine/musl and `read_only`, and does NOT bundle CLIs. **Do NOT use the official `docker-compose.linux.yml` override** — it sets `network_mode: host`, which breaks routing via the NPM network (the container must stay on `nginx-proxy-manager_proxy`). Instead keep the base network and add read-only mounts + PATH + HOME:

```yaml
environment:
  HOME: /home/opencode
  PATH: /mnt/host-opencode:/usr/local/bin:/usr/bin:/bin
volumes:
  - /home/hermes/.local/bin:/mnt/host-opencode:ro
  - /lib/x86_64-linux-gnu:/lib/x86_64-linux-gnu:ro
  - /lib64:/lib64:ro
  - /opt/open-design/opencode-home:/home/opencode
```

`/lib64` + `/lib/x86_64-linux-gnu` provide full glibc so the host glibc-linked OpenCode binary runs on Alpine. Create `/opt/open-design/opencode-home` and `chown -R 1001:1001` (user `open-design`, which == host uid 1001/hermes). After `up -d`, confirm opencode is visible: `docker exec open-design sh -c "opencode --version"`. Restart so the daemon re-scans PATH, then in the UI re-run and (if asked) hit **Rescan agents**. Verify with `GET /api/agents` — should list `opencode` and `byok-opencode` (`count: 27` together).

### mem_limit: MUST be >= 1536m (512m → OOM SIGKILL)

`opencode run` arranca un Node completo (~300-400MB heap) además del daemon. Con `mem_limit: 512m` el kernel mata al proceso con **SIGKILL** → el run falla con `agent exited with signal SIGKILL` y `docker inspect ... .State.OOMKilled` = `true`. Set `OPEN_DESIGN_MEM_LIMIT=1536m` en `.env` (prod .222 tiene 23GiB RAM, sobra).

PITFALL: `OPEN_DESIGN_MEM_LIMIT` en `.env` **sobreescribe** el default del compose. Por eso `docker compose up -d` seguía dejando 512m: había que editar el `.env` (no solo el compose). Y `docker compose up -d` NO recrea si el compose cambió — forzar con `docker compose up -d --force-recreate`. Verificar: `docker inspect --format '{{.HostConfig.Memory}}' open-design` → 1610612736 (1536m).

## BYOK provider (use your own key)

In the **Home** screen pick **"Usa tu propia clave"** (BYOK) — do NOT press the big black "Inicia sesión en OpenDesign" (that's the cloud account, not applicable self-hosted). Provide:
- Base URL: `https://api.nan.builders/v1`
- API Key: from the VPS config (`grep -A3 "NaN-Builders:" <hermes config> | grep api_key | sed 's/api_key: //'`) — keys are masked in agent output, fetch the raw value server-side.
- Model: `deepseek-v4-flash` (drafts) / `qwen3.6` (cheap iteration).
- In BYOK / agent picker choose **BYOK OpenCode** (or `opencode`); it resolves the model and runs `opencode run --format json`.

Also update the compose template: change `OPEN_DESIGN_MEM_LIMIT` default to `1536m` (see `templates/docker-compose.yml`).

## Driving OD via API (headless run, no UI)

Any agent can create a project + run it via the daemon REST API (Bearer `OD_API_TOKEN`; daemon only listens inside the container, so call from `docker exec ... node -e fetch(...)` or via the NPM domain). Gotchas that cost real debugging time:

### 1. `POST /api/projects` REQUIRES an `id` in the body

The create endpoint validates `id` (`isSafeId`) and rejects with `invalid project id` (HTTP 400) if absent. The daemon does NOT generate it. Pass a UUID: `body = { id: randomUUID(), name, designSystemId, skillId: null, pendingPrompt: BRIEF, skipDiscoveryBrief: true, metadata: { kind: 'prototype', platform: 'responsive' } }`. A plain slug (`neuralcrew-landing-001`) also passes.

### 2. User design systems must be PUBLISHED before use

User design systems are created as `status: draft` — `POST /api/projects` refuses them with `DESIGN_SYSTEM_NOT_PUBLISHED: draft design systems cannot be used by projects`. Publish via `PATCH /api/design-systems/<id>` with `{published: true}` (body `{ status: 'published' }` also returns 200; the effective field is `published`). Test with `GET /api/design-systems` → filter for your slugs → `status: published`. Remember `user:` prefix (e.g. `user:neuralcrew-labs`).

### 3. Run is `POST /api/chat` (SSE event-stream), not a project endpoint

There is NO `/api/projects/:id/run`. The run endpoint is `POST /api/chat` returning `text/event-stream`. Payload: `{ agentId: 'opencode', message: BRIEF, projectId, designSystemId, sessionMode: 'design', byokProvider: { protocol: 'openai', apiKey, baseUrl: 'https://api.nan.builders/v1', model: 'deepseek-v4-flash' }, locale: 'es' }`. Success = a `{type:'runtime_close', status:'succeeded'}` event with `artifactPaths` (e.g. `["neuralcrew-landing.html"]`); watch for `costUsd` (NaN = $0) and `agentId` must be `opencode` (not `openai-api`, which is the broken default). Artifact lives at `/app/.od/projects/<projectId>/<artifactPaths[0]>` — copy it out with `docker exec open-design cat <path>` (the container is read_only; `docker cp` fails).

Port the working reference script to `scripts/od_run.js` under this skill.

## MCP / agent runtime (later)

Optional phase 2: `od mcp install hermes` wires OD's MCP into Hermes so OD passes briefs to our bots (Sindri/Bragi/Brokkr) as the design engine. The Hermes adapter is native (`acp-json-rpc` stream). Pilot after the UI is in active use.

## Related

- `nginx-proxy-manager-api` — the NPM REST API and cert flow.
- `reel-gallery-deploy`, `static-portal-generator` — related VPS/portal deployment.
- `vps-web-deployment` — general static deploy + NPM.

## Referencias absorbidas

- `references/open-design-selfhost-ops.md` — absorbida desde `devops/open-design-selfhost-ops` el 2026-09-23 (F6 lote 3, R15: condensar sin borrar).
