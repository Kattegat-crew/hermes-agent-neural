---
name: system-onboarding
description: >-
  Use when onboarding a new AI agent environment Process for onboarding Ragnar (the AI orchestrator) into a new environment. Covers identity setup, tool installation, credential configuration, ROSTER definition, and initial project setup. Use when setting up the AI agent for a new company or project. hermes: tags: [onboarding, setup, configuration, identity, tools]
tags: [onboarding, setup, bootstrap, credenciales, pip, gh-cli, ambiente]
version: 1.0.0
author: dominus
license: MIT
metadata:---

# System Onboarding

Process for onboarding Ragnar into a new operational environment.

## Prerequisites

- Python 3.13+ available
- No pip initially (need to bootstrap with `python3 -c "import urllib.request; urllib.request.urlretrieve('https://bootstrap.pypa.io/get-pip.py', '/tmp/get-pip.py'); exec(open('/tmp/get-pip.py').read())"`)
- No curl/wget available (use Python urllib as fallback)
- No sudo (run as non-root user, install to ~/.local/bin)

## Setup Steps

### 1. Install pip
```python
python3 -c "
import urllib.request
urllib.request.urlretrieve('https://bootstrap.pypa.io/get-pip.py', '/tmp/get-pip.py')
exec(open('/tmp/get-pip.py').read())
"
```
If pip installs to a non-PATH directory, add it: `export PATH="$HOME/.local/bin:$PATH"`

### 2. Install Python packages
```bash
pip install --break-system-packages python-docx openpyxl pandas PyPDF2 pdfplumber mammoth Pillow
```

### 3. Install CLI tools (no curl fallback)
For gh CLI:
```python
python3 -c "
import urllib.request, tarfile, shutil
urllib.request.urlretrieve('https://github.com/cli/cli/releases/download/v2.67.0/gh_2.67.0_linux_amd64.tar.gz', '/tmp/gh.tar.gz')
with tarfile.open('/tmp/gh.tar.gz') as t: t.extractall('/tmp/')
shutil.copy('/tmp/gh_2.67.0_linux_amd64/bin/gh', '/opt/data/home/.local/bin/gh')
"
```

### 4. Configure GitHub
```bash
echo "ghp_xxx" | gh auth login --with-token --hostname github.com --git-protocol https
```

## Onboarding Questions (ask one at a time)

1. **Team roster** — Discord IDs and roles (Admin/Team/External)
2. **Database** — Is PostgreSQL available now or future?
3. **Vector DB** — Qdrant available or future?
4. **Redis** — Available or future?
5. **Modules status** — Which of the 7 Nexa modules are active vs pending?
6. **GitHub repo** — Where will the project live?
7. **Architecture doc** — Where is it? Read it first.
8. **First project** — What's the priority?
9. **Notion** — Integration token and workspace page
10. **Email** — IMAP/SMTP credentials
11. **Social media** — Which platforms, tokens?
12. **Google Workspace** — Gmail, Drive, Sheets, Docs setup
13. **Telegram** — Bot token or personal account?
14. **Domain/hosting** — Available or future?
15. **Tech stack** — Backend, frontend, infra preferences
16. **Git workflow** — Branch strategy, commit conventions
17. **Budget limits** — Any spending caps?
18. **Hard constraints** — Anything not in the SOUL rules?
19. **Pending task handling** — Register as pending or just say "no se puede"?
20. **Progress reporting** — Per-task, daily, on-demand?
21. **Timezone** — Bogotá (UTC-5)
22. **Operational hours** — 8am-10pm usual, 24/7 if tasks exist
23. **Task tracking** — Local file + Notion board

## Common Pitfalls

- **pip not found**: Bootstrap with urllib first
- **Permission denied on /usr/local/bin/**: Install to ~/.local/bin instead
- **No curl/wget**: Always use Python urllib as fallback
- **gh CLI not available**: Download and install manually via urllib
- **No database yet**: Don't assume DB exists; ask before querying
- **MEMORY.md.lock permission denied**: Run `rm -f /opt/data/memories/MEMORY.md.lock` then retry memory tool
- **gh CLI download URL**: Use `v2.67.0/gh_2.67.0_linux_amd64.tar.gz` (confirmed working)
- **Credential handoff**: Use config.yaml as central bridge between sessions for pending integrations

## Post-Onboarding

- Save SOUL.md to persistent memory
- Create initial TODO.md for pending tasks
- Set up Notion integration
- Configure cron jobs for continuous operation
- Load architecture document when available
- Wait for Chucho to set up the main repo

## Credential Management Pattern

After core setup (GitHub, Notion, skills, identity), create `/opt/data/home/config.yaml` as a central credential store with:
- All active credentials (GitHub PAT, Notion token, etc.)
- Placeholders (`null`) for pending integrations (email, social, telegram, google)
- Team roster with Discord IDs and roles
- System paths and skill configurations

This config.yaml serves as a session bridge — when resuming onboarding, check it to see what's configured vs what's pending.

Example structure:
```yaml
system:
  name: "Ragnar"
  timezone: "America/Bogota"
  language_default: "es"

team:
  - username: "Killer420w"
    discord_id: "713538631918157853"
    role: "CEO / Administrator"

github:
  account: "Kattegat-crew"
  pat: "ghp_xxx"

notion:
  token: "ntn_xxx"
  tasks_db_id: "xxx"

email:
  enabled: false
  imap_host: null
  smtp_host: null
  username: null
  password: null

telegram:
  enabled: false
  bot_token: null
```
