---
name: vps-ops
description: >-
  Use when running ops on the VPS via SSH (opencode, orca). Unified VPS operations: run OpenCode, Agy, manage Orca worktrees, access host files, check services. All via SSH from Hermes container. Triggers: "vps", "opencode", "agy", "orca", "worktree", "ejecuta en el vps", "corre en el server", "host", "servidor". author: opencode version: "2.0.0" replaces: [vps-host-access, vps-opencode-runner, vps-agy-runner, vps-orca-manager]
tags: [vps, ssh, opencode, orca, worktree, servidor, host, devops]
category: devops
metadata:---

# VPS Operations — Unified Skill

All VPS operations from Hermes container via SSH to root@10.0.7.1.

## Connection

```bash
SSH_HOST="root@10.0.7.1"
SSH_OPTS="-o StrictHostKeyChecking=no -o ConnectTimeout=10"
SSH="ssh $SSH_OPTS $SSH_HOST"
```

## 1. Run OpenCode

### Simple task
```bash
ssh $SSH_OPTS $SSH_HOST "cd /root/<project> && opencode --prompt '<TASK>'"
```

### With model override
```bash
ssh $SSH_OPTS $SSH_HOST "cd /root/<project> && opencode --model <MODEL> --prompt '<TASK>'"
```

### Background (long tasks)
```bash
ssh $SSH_OPTS $SSH_HOST "cd /root/<project> && nohup opencode --prompt '<TASK>' > /tmp/opencode-output.log 2>&1 &"
ssh $SSH_OPTS $SSH_HOST "tail -50 /tmp/opencode-output.log"
```

### Check version
```bash
ssh $SSH_OPTS $SSH_HOST "opencode --version"
```

## 2. Run Agy

### Simple task
```bash
ssh $SSH_OPTS $SSH_HOST "cd /root/<project> && agy '<TASK>'"
```

### Check version
```bash
ssh $SSH_OPTS $SSH_HOST "agy --version"
```

## 3. Manage Orca

### Status
```bash
ssh $SSH_OPTS $SSH_HOST "orca status --json"
```

### List repos
```bash
ssh $SSH_OPTS $SSH_HOST "orca repo list --json"
```

### List worktrees
```bash
ssh $SSH_OPTS $SSH_HOST "orca worktree ps --json"
```

### Create worktree with OpenCode
```bash
ssh $SSH_OPTS $SSH_HOST "orca worktree create --repo name:<REPO> --name <TASK> --agent opencode --prompt '<PROMPT>' --json"
```

### Create worktree (no agent)
```bash
ssh $SSH_OPTS $SSH_HOST "orca worktree create --repo name:<REPO> --name <TASK> --json"
```

### List terminals
```bash
ssh $SSH_OPTS $SSH_HOST "orca terminal list --json"
```

### Send command to terminal
```bash
ssh $SSH_OPTS $SSH_HOST "orca terminal send --terminal <HANDLE> --text '<CMD>' --enter --json"
```

### Read terminal output
```bash
ssh $SSH_OPTS $SSH_HOST "orca terminal read --terminal <HANDLE> --json"
```

### Delete worktree
```bash
ssh $SSH_OPTS $SSH_HOST "orca worktree rm --worktree id:<ID> --force --json"
```

## 4. Host File Access (fallback if SSH不够)

### Read file via Docker bind mount
```bash
docker run --rm -v /root/<path>:/file:ro alpine cat /file
```

### Read directory
```bash
docker run --rm -v /root/<path>:/dir:ro alpine ls -la /dir
```

### Check host service
```bash
docker run --rm --pid=host --privileged alpine nsenter -t 1 -m -u -n -i systemctl status <service>
```

## 5. System Checks

### Orca service status
```bash
ssh $SSH_OPTS $SSH_HOST "systemctl status orca-serve.service --no-pager | head -10"
```

### Docker containers
```bash
ssh $SSH_OPTS $SSH_HOST "docker ps --format 'table {{.Names}}\t{{.Status}}'"
```

### Disk usage
```bash
ssh $SSH_OPTS $SSH_HOST "df -h / /root"
```

### Running processes
```bash
ssh $SSH_OPTS $SSH_HOST "ps aux | grep -E 'orca|hermes|opencode' | grep -v grep"
```

## Registered Repos

| Repo | Path |
|------|------|
| golden-game-landing | /root/golden-game-landing |
| marketing-campaign-generator | /root/marketing-campaign-generator |
| hermes-agent | /root/hermes-agent-legacy-docker |
| ai-platform | /opt/ai-platform |
| activepieces | /root/activepieces |
| neuralcrew-saas-platform | /root/Neuralwebsite/neuralcrew-saas-platform |
| paradise-casino-landing | /root/paradise-casino/paradise-casino-landing |

## Pitfalls

- Long SSH commands may timeout. Use `nohup` for background execution.
- Git repos need `orca:orca` ownership on `.git` for Orca worktree creation.
- Orca worktree IDs are `<repoId>::<path>` — copy the full value.
- Terminal handles are runtime-scoped; re-list if `terminal_handle_stale`.
- Always use `--json` for machine-readable Orca output.
- For file writes, use `/opt/data/` (bind mount to host) instead of SSH.
