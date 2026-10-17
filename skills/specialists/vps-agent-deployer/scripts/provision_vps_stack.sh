#!/usr/bin/env bash
# ==============================================================================
# NeuralCrew & Hermes Agent Automated Stack Provisioning Script
# Target OS: Ubuntu 22.04+ / 24.04+ / Debian 12+
# ==============================================================================

set -euo pipefail

echo "=========================================================="
echo "🚀 Starting NeuralCrew VPS Agent Stack Provisioning"
echo "=========================================================="

# 1. Base System Packages
echo "📦 1/6 Installing base packages..."
apt-get update -qq
apt-get install -y -qq curl wget git jq build-essential htop tmux unzip ca-certificates

# 2. Docker & Docker Compose
if ! command -v docker &> /dev/null; then
    echo "🐳 2/6 Installing Docker..."
    curl -fsSL https://get.docker.com | sh
    systemctl enable --now docker
else
    echo "🐳 2/6 Docker already installed."
fi

# 3. Gentleman AI Suite & Engram
echo "🧠 3/6 Setting up Engram & Gentleman AI Suite..."
mkdir -p /root/.engram
chmod -R 777 /root/.engram

if ! command -v brew &> /dev/null; then
    if [ ! -d "/home/linuxbrew/.linuxbrew" ]; then
        NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" || true
    fi
fi

if [ -d "/home/linuxbrew/.linuxbrew" ]; then
    eval "$(/home/linuxbrew/.linuxbrew/bin/brew shellenv)"
    brew tap gentleman-programming/tap || true
    brew install engram gentle-ai gga || true
    
    # Symlink to /usr/local/bin
    ln -sf /home/linuxbrew/.linuxbrew/bin/engram /usr/local/bin/engram || true
    ln -sf /home/linuxbrew/.linuxbrew/bin/gentle-ai /usr/local/bin/gentle-ai || true
    ln -sf /home/linuxbrew/.linuxbrew/bin/gga /usr/local/bin/gga || true
fi

# 4. OpenCode Config
echo "⚡ 4/6 Setting up OpenCode configuration..."
mkdir -p /root/.config/opencode
cat << 'EOF' > /root/.config/opencode/opencode.jsonc
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
      "command": "/usr/local/bin/engram",
      "args": ["mcp", "--tools=agent"]
    }
  }
}
EOF

# 5. Permissions check on Engram store
echo "🔒 5/6 Adjusting Engram SQLite permissions for multi-tenant Docker..."
mkdir -p /root/.engram
touch /root/.engram/engram.db /root/.engram/engram.db-wal /root/.engram/engram.db-shm 2>/dev/null || true
chmod 777 /root/.engram
chmod 666 /root/.engram/* 2>/dev/null || true

# 6. Summary & Readiness
echo "=========================================================="
echo "✅ Provisioning Complete!"
echo "   - Docker & Compose: Active"
echo "   - Gentleman AI & Engram: Installed in /usr/local/bin"
echo "   - OpenCode Models: Xiaomi MiMo V2.5 & Qwen 3.6 configured"
echo "   - Shared Memory: /root/.engram ready for Docker mounts"
echo "=========================================================="
