---
name: hermes-workspace-setup
description: "Use when installing the Hermes Workspace web UI."
tags: [hermes, workspace, vite, dashboard, instalacion, ui]
---

# Install & Integrate Hermes Workspace

Install and configure the Hermes Workspace web UI as the management interface for Hermes Agent.

## Prerequisites Check

1. **Node.js 22+ required** — workspace enforces this. If system has older Node:
   - Try `pnpm install --config.ignoreEngines=true` to bypass engine check
   - Or install Node 22 via nvm/n (requires sudo) or download binary
2. **pnpm required** — if not available:
   ```bash
   npm install -g pnpm --prefix /opt/data/home/.local
   export PATH="/opt/data/home/.local/bin:$PATH"
   ```
   Note: may need sudo for global npm install. If no sudo, use `--prefix` to install locally.

## Installation Steps

### 1. Clone the repository
```bash
cd /opt/data
git clone https://github.com/outsourc-e/hermes-workspace.git
cd hermes-workspace
```

### 2. Install dependencies
```bash
export PATH="/opt/data/home/.local/bin:$PATH"
pnpm install --config.ignoreEngines=true
```

### 3. Configure .env
Copy `.env.example` to `.env` and configure for your setup:

```bash
cp .env.example .env
```

**Two modes available:**

#### Mode A: Gateway Mode (Full Features — sessions, skills, memory, config, jobs)
Requires Hermes gateway with HTTP API server enabled (port 8642/8645):
```env
HERMES_API_URL=http://127.0.0.1:8642
# If gateway has API_SERVER_KEY set:
# HERMES_API_TOKEN=<your-secret>
```

#### Mode B: Portable Mode (Chat Only — no sessions/skills/memory)
Point directly at any OpenAI-compatible backend:
```env
HERMES_API_URL=https://api.nan.builders/v1
OPENAI_API_KEY=sk-***
```

### 4. Start services

**⚠️ CRITICAL: Always start long-running services in background.**

Never run `vite dev` or `hermes dashboard` in foreground — these are persistent servers that never exit. Running them in foreground will cause the agent to hang and timeout after ~20 min of inactivity.

**Always use `nohup ... &` or `background=true` in terminal:**

#### Start Workspace
```bash
export PATH="/opt/data/home/.local/bin:$PATH"
export NODE_OPTIONS="--max-old-space-size=2048"
cd /opt/data/hermes-workspace
nohup npx vite dev --port 3000 --host 0.0.0.0 > /opt/data/logs/workspace.log 2>&1 &
echo $! > /opt/data/run/workspace.pid
```

#### Start Dashboard (optional, for config management)
```bash
mkdir -p /opt/data/logs
/opt/hermes/.venv/bin/hermes dashboard --port 9119 --no-open --insecure > /opt/data/logs/dashboard.log 2>&1 &
```

**Dashboard binds to 127.0.0.1 (not 0.0.0.0).** Verify with `http://127.0.0.1:9119/`, not `http://localhost:9119/`.

### 5. Verify
```bash
python3 -c "import urllib.request; r = urllib.request.urlopen('http://localhost:3000/'); print(r.status)"
# Should return 200
```

## Persistent Setup

Create launcher scripts:

**`/opt/data/scripts/start-workspace.sh`:**
```bash
#!/bin/bash
export PATH="/opt/data/home/.local/bin:$PATH"
export NODE_OPTIONS="--max-old-space-size=2048"
WORKSPACE_DIR="/opt/data/hermes-workspace"
cd "$WORKSPACE_DIR"
nohup npx vite dev --port 3000 --host 0.0.0.0 > /opt/data/logs/workspace.log 2>&1 &
echo $! > /opt/data/run/workspace.pid
```

**`/opt/data/scripts/stop-workspace.sh`:**
```bash
#!/bin/bash
pkill -f "vite dev" 2>/dev/null
pkill -f "hermes dashboard" 2>/dev/null
rm -f /opt/data/run/workspace.pid
```

Make executable:
```bash
chmod +x /opt/data/scripts/start-workspace.sh /opt/data/scripts/stop-workspace.sh
mkdir -p /opt/data/logs /opt/data/run
```

## Service Management

### Quick Status Check
```bash
# Check workspace services
/opt/data/scripts/manage-workspace.sh status

# Check gateway
/opt/hermes/.venv/bin/hermes gateway status
```

### Manage All Services at Once
```bash
# Start both workspace and dashboard
/opt/data/scripts/manage-workspace.sh start

# Stop both
/opt/data/scripts/manage-workspace.sh stop

# Restart both
/opt/data/scripts/manage-workspace.sh restart
```

The `manage-workspace.sh` script handles both the Vite dev server (port 3000) and the Hermes Dashboard (port 9119) in one command. It also checks if ports are already in use before starting.

### Verify Services Are Running
**⚠️ CRITICAL: Dashboard binds to 127.0.0.1, NOT 0.0.0.0.**

When checking port availability, always test on the correct bind address:
```bash
python3 -c "
import socket
# Workspace binds to 0.0.0.0
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect(('0.0.0.0', 3000))
print('Workspace (3000): OPEN')
s.close()
# Dashboard binds to 127.0.0.1
s2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s2.connect(('127.0.0.1', 9119))
print('Dashboard (9119): OPEN')
s2.close()
"
```

Checking port 9119 on `0.0.0.0` will show it as FREE even when the dashboard is running, because it only listens on `127.0.0.1`.

## Architecture

Hermes Workspace consists of:
- **Web UI** (Vite/React/TypeScript) — runs on port 3000, binds to 0.0.0.0
- **Hermes Dashboard** (Python) — runs on port 9119, manages config/API keys/sessions, binds to 127.0.0.1
- **Hermes Gateway** (Python) — messaging platform bridge, optional HTTP API on port 8642, runs as PID 1 in container

## Troubleshooting

### pnpm install fails with EACCES
Use local prefix: `npm install -g pnpm --prefix /opt/data/home/.local`

### Node version too old
Try `--config.ignoreEngines=true`. If build scripts fail (esbuild native modules), may need Node 22.

### Workspace doesn't start (no stdout)
Vite buffers stdout. Check port instead: `python3 -c "import urllib.request; print(urllib.request.urlopen('http://localhost:3000/').status)"`

### Dashboard won't start
Check logs: `cat /opt/data/logs/dashboard.log`. Dashboard binds to `127.0.0.1:9119` (not 0.0.0.0). Verify with `http://127.0.0.1:9119/`.

### Workspace hangs / agent times out
If the agent shows "Still working... iteration X/90" and then blocks, it's because a foreground command never exited. Long-running servers (vite dev, dashboard, etc.) must ALWAYS be started with `nohup ... &` or `background=true`. Never run them in foreground.

### Build succeeds but dev server hangs
Try `npx vite build` first to verify compilation, then `npx vite dev`.

### Services running but not responding to urllib
If processes are running (`ps aux | grep vite`) but `urllib.request.urlopen()` hangs or refuses, use raw HTTP connections instead — `urllib` can timeout in some container environments:
```bash
python3 -c "
import http.client
for port, name in [(3000, 'Workspace'), (9119, 'Dashboard')]:
    conn = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
    conn.request('GET', '/')
    resp = conn.getresponse()
    print(f'{name} (:{port}): {resp.status}')
    conn.close()
"
```
Or check socket openness:
```bash
python3 -c "
import socket
for port in [3000, 9119]:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(2)
    print(f'Port {port}: {\"OPEN\" if s.connect_ex((\"127.0.0.1\", port)) == 0 else \"CLOSED\"}')
    s.close()
"
```

### Docker-in-container networking
When running inside Docker, services bind to container-internal IPs. Verify port mapping from the VPS host:
```bash
# On the VPS host (outside container):
docker ps  # Check PORTS column shows e.g. 0.0.0.0:3000->3000/tcp
```
If ports aren't mapped, add them to docker-compose.yml or `docker run -p`:
```yaml
ports:
  - "3000:3000"
  - "9119:9119"
```
For external access (Tailscale, etc.), the VPS host must have the ports published. Access via `http://<VPS-IP>:3000` from outside the container.

### Permission denied on config files
Use `hermes config set` CLI instead of direct file editing. Config files are often root-owned.

### Services show as running but port check fails
The `manage-workspace.sh` script checks port availability by trying to bind to `127.0.0.1`. If the workspace binds to `0.0.0.0` but dashboard binds to `127.0.0.1`, port checks can be inconsistent. Always verify with actual connection attempts rather than bind checks.

## Key Files
- `/opt/data/hermes-workspace/.env` — configuration
- `/opt/data/hermes-workspace/package.json` — dependencies
- `/opt/data/hermes-workspace/server-entry.js` — SSR server entry
- `/opt/data/hermes-workspace/docker-compose.yml` — Docker deployment option
- `/opt/data/hermes-workspace/install.sh` — official one-liner installer
