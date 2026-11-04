---
name: zmx
description: "Use when managing tmux/zellij sessions headlessly."
tags: [tmux, zellij, terminal, sesiones, background-tasks, orquestacion]
license: MIT
compatibility: hermes, opencode, bash
metadata:
  hermes:
    tags: [tmux, zellij, terminal, multiplexing, sessions, background-tasks, orchestration]
    category: devops
---

# Terminal Multiplexing Architecture (Tmux & Zellij)

Guidelines and operational patterns for running persistent, headless, and isolated background tasks using terminal multiplexers in Linux server environments.

## 1. When to Use Multiplexers

Use `tmux` or `zellij` when:
- Spawning long-running build, migration, or daemon tasks that must survive SSH disconnection.
- Isolating sub-processes where stdout/stderr must be monitored or captured without blocking the primary agent turn.
- Orchestrating multi-service local testing stacks without Docker Compose.

---

## 2. Tmux Headless Automation Patterns

Headless agents interact with `tmux` via command-line flags without attaching to a TTY.

### A. Session Lifecycle Management
```bash
# 1. Start a detached session with a defined name
tmux new-session -d -s <session_name> -n <window_name>

# 2. Check if a session exists safely (returns 0 if exists, 1 if not)
tmux has-session -t <session_name> 2>/dev/null

# 3. Kill a session gracefully
tmux kill-session -t <session_name>

# 4. List all active sessions
tmux list-sessions -F "#{session_name}: #{session_windows} windows (created #{session_created_string})"
```

### B. Sending Input and Commands
Always append `Enter` or `C-m` when dispatching commands to a pane:
```bash
# Send command to specific session/window
tmux send-keys -t <session_name> "python3 /path/to/daemon.py" Enter

# Send SIGINT (Ctrl+C) to terminate a running command
tmux send-keys -t <session_name> C-c
```

### C. Capturing Output and Logs
```bash
# Capture the last 200 lines of scrollback history
tmux capture-pane -t <session_name> -p -S -200

# Stream or dump pane content directly to a file
tmux capture-pane -t <session_name> -p -S - > /tmp/<session_name>.log
```

---

## 3. Zellij Headless Automation Patterns

Zellij provides modern layout declarative configurations and session attachments.

### A. Session Control
```bash
# 1. Start a detached named session
zellij --session <session_name> attach --create-background

# 2. List sessions
zellij list-sessions

# 3. Kill session
zellij kill-session <session_name>
zellij delete-all-sessions --yes
```

### B. Action & Plugin Dispatch
```bash
# Run a specific command in a new floating pane within a session
zellij action new-pane --floating -- name "worker" -- python3 /path/to/script.py

# Dump screen contents for debugging
zellij action dump-screen /tmp/zellij_dump.txt
```

---

## 4. Production Best Practices for Autonomous Agents

1. **Deterministic Naming**: Prefix session names with the service or agent ID (e.g., `hermes_worker_01`, `build_job_1403`).
2. **Socket Isolation**: Use custom sockets (`tmux -S /tmp/hermes_tmux.sock`) to prevent collisions with user sessions.
3. **Resource Guarding**: Always ensure background sessions clean up their child processes upon completion or timeout.
