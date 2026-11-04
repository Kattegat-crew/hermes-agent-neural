# VPS & FHS Operating Guardrails

## Operating Environment
* **Host**: DEV (`147.93.3.250` / Tailscale `100.86.8.81`) — Ubuntu 24.04 LTS.
* **Target Audience**: All autonomous agents (`agy`, `codex`, `opencode2`, `hermes`) and human contributors.

---

## Strict Invariants

### 1. Filesystem Hierarchy & Boundary Rules
* **Code Location Exclusivity**: All projects, tools, frameworks, and agent workspaces reside strictly under `/opt/`.
* **Prohibited Directories**:
  * NEVER initialize, clone, or scaffold repositories inside `/root/`.
  * `/root/` is exclusively reserved for personal shell configurations (`.bashrc`), global system keys, and global manifests.
  * Do not leave untracked scratch files, ad-hoc python scripts, or log dumps in the project root or `/tmp/`. Clean up temporary files immediately.

### 2. Zero Secrets Policy
* **Vaultwarden SSOT**: Real secrets, API keys, database credentials, and tokens reside solely in Vaultwarden and local `.env` files protected with `chmod 0600`.
* **Prohibited in Git / Markdown**:
  * NEVER commit `.env`, token strings, private keys, or passwords.
  * Sanitize test fixtures and logs to prevent credential leakage.

### 3. Process & System State Hygiene
* **Daemon Management**: Never spawn unmonitored background daemons or detached tmux sessions that consume VPS resources indefinitely.
* **Service Verifications**: Before claiming a task is done, verify systemd service statuses (`systemctl status <unit>`) and container states (`docker compose ps`).
* **Port Etiquette**: Never bind to production ports or collide with known DEV daemons (e.g., AKARI `:8090`, Orca `:6768`, WhatsApp bridge `:3000`).

### 4. Git & Commit Governance
* **Conventional Commits**: All commit messages must follow standard conventional formats (`feat:`, `fix:`, `refactor:`, `test:`, `chore:`).
* **Zero AI Attribution**: NEVER append `Co-Authored-By` or any machine/AI attribution strings to commits or pull requests.
* **No Unapproved Push**: Pushing directly to remote repositories requires explicit user approval.
