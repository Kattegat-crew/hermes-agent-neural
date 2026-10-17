---
name: vps-agent-deployer
description: "Zero-friction, fully automated provisioning and deployment skill for multi-agent Docker architectures on clean Linux VPS servers. Sets up Docker, Hermes Agent, shared Engram memory, Gentle AI, OpenCode, NaN-Builders model routing, WhatsApp bridges, and Gmail MCP."
---

# VPS Agent Deployer & Multi-Container Docker Skill

## Overview
Use this skill when provisioning a clean VPS (Ubuntu/Debian) to deploy the complete **NeuralCrew / Hermes Agent production stack** with zero manual friction.

This skill automates:
1. **Base OS Hardening & Dependencies**: Docker, Docker Compose, Node.js 22+, Python 3.11+, Linuxbrew.
2. **Gentleman AI Suite**: `engram` (v1.20.0), `gentle-ai` (v2.3.0), `gga` (v2.10.1).
3. **Engram Shared Persistent Memory Store**: Cross-container SQLite WAL mode database mounted at `/root/.engram` with `777/666` permissions and automatic cross-project search (`all_projects=True`).
4. **Hermes Agent (v0.20.0 / The Herald Release)**:
   - 1M token context window with ~500k compaction threshold.
   - NaN-Builders model matrix: `deepseek-v4-flash` (primary), `qwen3.6` (smart routing <1.5s), `mimo-v2.5` (web extraction), `whisper` & `kokoro` (voice).
   - Pre-configured MCP tools: Engram (18 tools) + Gmail / Google Workspace (19 tools).
   - Balanced messaging UX: Live self-cleaning bubbles on Telegram (`cleanup_progress: true`) and silent typing on WhatsApp.
5. **OpenCode Configuration**: Multi-agent team (`lead`, `developer`, `evaluator`, `designer`, `debugger`) configured with `mimo-v2.5`, `qwen3.6`, and `gemma4`.

---

## Quick Start (Automated Script)

Run the end-to-end provisioning script:
```bash
bash /root/.config/opencode/skills/vps-agent-deployer/scripts/provision_vps_stack.sh
```

---

## Architecture Blueprint

```
┌────────────────────────────────────────────────────────────────────────┐
│                        HOST VPS (Ubuntu / Debian)                      │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  🧠 Shared Engram Store (/root/.engram/engram.db — SQLite WAL)         │
│  ├─ Shared with Antigravity, OpenCode, and all Docker containers       │
│  └─ Permissions: 777 directory / 666 db files                          │
│                                                                        │
│  🐳 Docker Multi-Agent Network                                         │
│  ┌───────────────────────────────┐   ┌───────────────────────────────┐ │
│  │ hermes-agent (Ragnar / Main)  │   │ hermes-casino-golden (Client) │ │
│  │ ├─ Model: deepseek-v4-flash   │   │ ├─ Model: deepseek-v4-flash   │ │
│  │ ├─ Routing: qwen3.6 (<1.5s)   │   │ ├─ Routing: qwen3.6 (<1.5s)   │ │
│  │ ├─ Context: 1,048,576 tokens  │   │ ├─ Context: 1,048,576 tokens  │ │
│  │ ├─ MCP: Engram + Gmail        │   │ ├─ MCP: Engram + Twenty CRM   │ │
│  │ └─ Volume: /root/.engram      │   │ └─ Volume: /root/.engram      │ │
│  └───────────────────────────────┘   └───────────────────────────────┘ │
│                                                                        │
│  📊 Complementary Microservices                                        │
│  ├─ Twenty CRM (Multi-tenant CRM)                                      │
│  ├─ ActivePieces (Automation workflows)                                │
│  └─ Formbricks (Surveys & Forms)                                       │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

---

## Step-by-Step Manual Provisioning Guide

### Step 1: Base Packages & Docker Installation
```bash
apt-get update && apt-get install -y curl wget git jq build-essential htop tmux
curl -fsSL https://get.docker.com | sh
systemctl enable --now docker
```

### Step 2: Install Gentleman AI & Engram (Host)
```bash
# Install Homebrew / Linuxbrew
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
eval "$(/home/linuxbrew/.linuxbrew/bin/brew shellenv)"
brew tap gentleman-programming/tap
brew install engram gentle-ai gga

# Create host engram directory with open permissions for containers
mkdir -p /root/.engram
chmod 777 /root/.engram
```

### Step 3: Configure OpenCode
Write `/root/.config/opencode/opencode.jsonc`:
```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "models": {
    "global": "nan-builders/mimo-v2.5"
  },
  "agents": {
    "lead": { "model": "nan-builders/mimo-v2.5" },
    "developer": { "model": "nan-builders/mimo-v2.5" },
    "evaluator": { "model": "nan-builders/qwen3.6" },
    "designer": { "model": "nan-builders/mimo-v2.5" },
    "debugger": { "model": "nan-builders/gemma4" }
  },
  "mcp": {
    "engram": {
      "command": "/home/linuxbrew/.linuxbrew/bin/engram",
      "args": ["mcp", "--tools=agent"]
    }
  }
}
```

### Step 4: Configure Hermes Agent (Docker)
Create `/root/hermes-agent/docker-compose.yml`:
```yaml
services:
  hermes:
    image: hermes-agent-hermes
    container_name: hermes-agent
    ports:
      - "3000:3000"
      - "9119:9119"
    environment:
      - HOME=/opt/data/home
      - HERMES_UID=10000
      - HERMES_GID=10000
      - ENGRAM_DATA_DIR=/opt/data/home/.engram
    volumes:
      - ./data:/opt/data
      - /root/.engram:/opt/data/home/.engram
      - /root/.engram:/root/.engram
      - /home/linuxbrew/.linuxbrew/Cellar/engram/1.20.0/bin/engram:/usr/local/bin/engram:ro
      - /home/linuxbrew/.linuxbrew/Cellar/gentle-ai/2.3.0/bin/gentle-ai:/usr/local/bin/gentle-ai:ro
      - ./tools/mcp_tool.py:/opt/hermes/tools/mcp_tool.py:ro
    restart: unless-stopped
```

### Step 5: Golden Rules & Gotchas
1. **Never pass `--project=*`**: Engram treats `*` as a literal string name. Global multi-project recall is achieved by omitting `--project` and passing `all_projects=True`.
2. **Always ensure `777` permissions on `/root/.engram`**: The container runs as UID `10000` (`hermes`), while host tools run as `root`. Open directory permissions allow both to write SQLite WAL locks concurrently.
3. **Always set `context_length: 1048576`**: Setting this ensures the preflight context compaction threshold stays at ~500k tokens instead of triggering prematurely at 53k.
4. **Always mount `~/.gmail-mcp/`**: Gmail MCP requires `gcp-oauth.keys.json` to exist in `/opt/data/home/.gmail-mcp/`.
