---
name: wizard
description: "Generate an interactive bash wizard that walks a human step by step through manual operations (provisioning infrastructure, third-party dashboards, OAuth, secrets, DNS)."
tags: [automation, bash, hitl, onboarding, devops, secrets, operations]
version: 1.0.0
author: NeuralCrew Labs (adapted from Matt Pocock)
license: MIT
platforms: [linux, macos, windows]
---

# Wizard: Interactive Human-In-The-Loop Scripts

A **wizard** is an interactive bash script that walks a human, step by step, through a manual procedure that's tedious to do by hand and tedious to re-explain to an AI every time. It opens each URL, says exactly what to click and copy, captures the values, writes them where they belong (`.env`, secrets, configs), confirms at every stage, and shows progress.

The delightful UX is solved by [`template.sh`](template.sh): stage-by-stage progress, confirmation gates, cross-platform URL opening (Linux, macOS, WSL), hidden secret entry, idempotent `.env` upserts, and a closing summary. **Your job is only to scope the procedure and author its stages below the STAGES marker.**

A wizard is ephemeral by default: built for one run, saved to a scratch or `scripts/` path, deleted when the job's done. Commit it only when the user wants a repeatable setup path that should live in the repo.

## Process

### 1. Scope the Procedure

Work out every manual step the human must take and every value that gets captured along the way:

- For setup: inspect `.env`, `.env.example`, `docker-compose*`, framework config, credentials.
- For a migration: identify the current state, target state, and irreversible actions between them.

**Done when:** Every stage is named in order, and for each captured value you know:
1. Where the human gets it (exact dashboard page or CLI command).
2. Where it's written (`.env`, a secret vault, or a config file).
3. Whether it's secret (hidden entry via `ask_secret`) or public (`ask`).

### 2. Map Each Stage's Journey

For each stage, write the precise path a human follows: which URL to open, what to do there, where a value is shown, which variable it fills (e.g., "Meta Events Manager → Settings → Conversions API → Generate Access Token → copy"). Never invent steps that may not exist; verify with docs or ask the human first.

### 3. Author the Wizard

Copy `template.sh` to the target script path (e.g., `scripts/setup-meta-capi.sh`). Author the stages below the `# STAGES` marker. Use the library helpers:
- `stage "Stage Name"`
- `say "Instructions"` / `step "Action item"`
- `open_url "https://..."`
- `ask "PROMPT" VAR_NAME` / `ask_secret "PROMPT" VAR_NAME`
- `write_env "KEY" "$VALUE"`
- `confirm "Are you ready to proceed with this irreversible action?"`
- Set `TOTAL_STAGES` to the number of stages written.

### 4. Verify and Hand Off

1. Verify syntax: `bash -n <script>`.
2. Make executable: `chmod +x <script>`.
3. Do NOT run it unattended: it blocks on human input and opens URLs. Tell the user how to run it in their terminal.
