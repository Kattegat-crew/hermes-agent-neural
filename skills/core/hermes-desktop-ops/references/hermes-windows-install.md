---
name: hermes-windows-install
description: Hermes Desktop install fails on Windows (npm error).
version: 1.0.0
license: MIT
platforms: [windows]
metadata:
  tags: [hermes, windows, npm, install, gateway, bootstrap]
---

# Hermes Windows Install & Runtime Troubleshooting

Diagnose and fix Windows installs of Hermes Desktop failing at the npm/browser/desktop stages.

## Trigger
The Windows installer shows:

```
INSTALL DIDN'T FINISH
desktop workspace npm install failed (exit 1) -- see lines above for cause
```

## Diagnose (2 min)

1. Open the bootstrap log (button "Open logs" or file):
   - `%LOCALAPPDATA%\hermes\logs\bootstrap-installer.log`
   - e.g. `C:\Users\<USER>\AppData\Local\hermes\logs\bootstrap-installer.log`
2. "see lines above for cause" → the real error is ABOVE that line. Grep the last `npm error*` block:
   - `npm error code EBADENGINE` / `npm error notsup Required: {"node":"...","npm":"..."}` / `Actual:` → **npm version outside the package's engine range**. This is the classic fatal cause.
   - Versions: `node --version`, `npm --version`.
3. Stop chasing non-issues:
   - Spaces/accents in the username are FINE — the installer handles them (it expands 8.3 short paths).
   - "Browser tools npm install failed" / "TUI npm install failed" during the earlier `node-deps` stage are warnings the installer continues past — the fatal one is stage `desktop`.

## Fix: npm within the supported engine range

Requirement looks like `{"node": ">=22.22.0", "npm": "<11.10.0 || >=11.17.0"}`. Align npm to a SUPPORTED value, pinned (NOT `@latest` — it can fall inside the gap again):

```
npm install -g npm@11.17.0
```

On a Node.js.org install, the bundled npm lives in `C:\Program Files\nodejs` and **cannot be overwritten** — so `npm install -g` lands a SECOND copy in the user global dir (`npm root -g` → `C:\Users\<USER>\AppData\Roaming\npm\node_modules`). That copy is AFTER `C:\Program Files\nodejs` on PATH → `npm --version` still shows the old one.

Confirm the dual copy and order:
```
where npm
npm root -g
```

### Option A — persistent (User PATH prepend), in PowerShell
```powershell
[System.Environment]::SetEnvironmentVariable('Path','C:\Users\<USER>\AppData\Roaming\npm;'+[System.Environment]::GetEnvironmentVariable('Path','User'),'User')
```
Verify the FIRST entry is the npm global dir:
```powershell
[System.Environment]::GetEnvironmentVariable('Path','User').Split(';')[0]
```
Then open a BRAND-NEW shell (see trap: a new tab in an already-open Windows Terminal does NOT pick the change up) and `npm --version`.

### Option B — session-scoped, guaranteed, no registry
In the SAME shell that will launch the installer:
```
# cmd
set "PATH=%APPDATA%\npm;%PATH%"
# PowerShell
$env:Path = "$env:APPDATA\npm;" + $env:Path
```
verify `npm --version`, then LAUNCH the Hermes Desktop/installer from that same shell so the child inherits the fixed PATH. The "Retry install" button uses the env inherited by ITS process — a fully fresh launch, not the already-open window.

### Re-run
"Retry install" is idempotent: Python deps are already installed; it resumes from the failing stage.

## Traps

- **cmd vs PowerShell**: `$env:Path` is PowerShell — in cmd it errors "El nombre de archivo... no son correctos" / "not recognized". Read the prompt: `>` = cmd, `PS >` = PowerShell. ALWAYS label which shell each command is for.
- **Windows Terminal "new tab"** inherits the OLD env — close ALL windows (or use Option B) to get a fresh env.
- The PowerShell `SetEnvironmentVariable` call returns nothing silently — that's normal; verify by reading the stored value (as above).
- **Accents/spaces in the username path break unquoted commands** in both shells. Use the 8.3 short path (`C:\Users\JESSDA~1\AppData\Roaming\npm`) — list it with `cmd /c dir /x C:\Users` — to avoid quoting entirely.
- Restoring afterward is symmetric: `npm install -g npm@<original>` and remove the PATH entry.

## Communication (user-aware)
**Lead with the answer** — the exact URL/command first, the short explanation after. This user gets frustrated by multi-turn diagnostic trails and asks for the deliverable directly ("¿Solo necesitaba la URL?"). One clear recommendation, not a menu of options; don't make them run three diagnostics before the payoff.

## Related
- Remote-gateway connect (Desktop "Connect to existing Hermes"): see `references/remote-gateway-vps.md`.
- Windows runtime quirks (keybinds, BOM, WinError 10106): bundled `hermes-agent` skill reference `references/windows-quirks.md`.