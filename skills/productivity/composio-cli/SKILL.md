---
name: composio-cli
description: "Use when installing or automating with the Composio CLI."
tags: [composio, cli, integraciones, oauth, connectors, automatizacion]
---

# Composio CLI (integration platform)

Composio (ComposioHQ/composio) is a hosted integration platform: a catalog of 250+ third-party connectors (Google/Gmail/Calendar/Drive, Slack, Discord, Notion, HubSpot, Meta, YouTube, etc.) exposed as actions/triggers for agents (MCP/API). It complements the self-hosted ActivePieces hub for cases where you want a quick integration without building a flow.

## Install (rootless VPS/container — no sudo)
The official install `curl -fsSL https://composio.dev/install | sh` pulls a release binary to `~/.composio/composio` (~102 MB) and symlinks `~/.local/bin/composio`. It requires `unzip` on PATH (`command -v unzip`) AND calls `unzip -oqd <dir> <archive>`. On the rootless `hermes` user there is no `unzip` and no sudo → provide a user-level `unzip` wrapper FIRST.

Run the wrapper installer: `scripts/install_rootless_unzip.sh` (creates `~/.local/bin/unzip` wrapper, chmod +x, prepends `~/.local/bin` to PATH and persists it in `~/.bashrc`). Then:

```bash
export PATH="$HOME/.local/bin:$PATH"
curl -fsSL https://composio.dev/install | sh
```

Verify: `composio --version` → e.g. `0.4.0`.

## Login
Login is browser-based. For a headless agent:

```bash
composio login --no-browser --no-wait --no-skill-install
# prints:  https://dashboard.composio.dev/?cliKey=<key>
# hand the URL to the human; once they open it:
composio login --poll            # completes login from the cached key (polls up to 10 min)
```

- `--no-skill-install` skips installing the composio-cli skill for Claude Code.
- Unattended / no human present: `composio login --agent` signs in with a Composio agent account (creating one if needed) WITHOUT a browser.

## Gotchas / pitfalls
- **Combined `-oqd` flag**: the installer calls `unzip -oqd "$tmpdir" "$tmpdir/$archive_name"`. In a hand-written wrapper, `-d` inside the combined cluster consumes the NEXT argument as the destination dir. If the wrapper ignores it, the bundle extracts to cwd and you get `error: Binary not found in extracted archive`. The wrapper in `scripts/install_rootless_unzip.sh` handles this.
- **Archive layout**: binary lives at `composio-<target>/composio`; for linux-x64 that is `composio-linux-x64/composio`. Direct asset URL: `https://github.com/ComposioHQ/composio/releases/download/@composio/cli@<version>/composio-<target>.zip`.
- **Version check fails with getcwd error**: if the shell cwd was deleted/renamed (e.g. you `rm -rf`'d the dir you were `cd`'d into), `composio --version` breaks on `pwd`. Run it from a valid dir (use the terminal `workdir` param or `cd /opt/data`).
- 102 MB binary; extraction is slow.

## Automations worth wiring (agency context)
See `references/composio-automation-ideas.md` for task suggestions grounded in NeuralCrew Labs (publishing content, lead capture to Twenty/HubSpot, onboarding email from captain@, Google Business / Search Console review & SEO monitoring, competitor mention alerts).

## Related
- activepieces-* skills (self-hosted OAuth hub) — Composio is a quick-connect catalog, NOT a replacement for the client-connection hub.
- agent-reach / integration-platform skills for the broader automation stack.
