---
name: hermes-desktop-windows-troubleshooting
description: Use when Hermes Desktop install/update fails on Windows.
---

# Hermes Desktop Install/Update Troubleshooting (Windows)

Client-side (end-user Windows machine) Hermes Desktop installer/updater failures.
Validated 2026-08-19 on two Windows machines (users `Jesús Díaz` and `wwwko`).
These are the real failure classes in `bootstrap-installer.log`, at
`C:\Users\<user>\AppData\Local\hermes\logs\bootstrap-installer.log`.

## Class 1 — npm EBADENGINE "Unsupported engine" (npm version in an excluded band)

Log signature (stage=desktop):
```
npm error notsup Required: {"node":">=22.22.0","npm":"<11.10.0 || >=11.17.0"}
npm error notsup Actual:   {"node":"v24.15.0","npm":"11.12.1"}
```
The desktop workspace package gates its `engines` field: npm must be `<11.10.0` OR
`>=11.17.0`; npm 11.10–11.16 is the excluded hole. Node `>=22.22.0` is usually fine.

**Fix:** align npm into a supported band, prefer up:
```
npm install -g npm@11.17.0
```
(or `npm@11.9.0`). Verify with `npm --version` in a NEW terminal.

**Windows dual-npm gotcha (the 80% case):** `npm install -g` cannot overwrite the
npm bundled in `C:\Program Files\nodejs` (Program Files, not writable), so the new
npm lands in the user global dir `C:\Users\<user>\AppData\Roaming\npm`, which is
SECOND in PATH. `npm --version` still shows the old one. Check with `where npm`
and `npm root -g`. Fix: prepend the Roaming dir to User PATH, using the 8.3 short
path to avoid spaces/accents:
```powershell
[System.Environment]::SetEnvironmentVariable('Path',
 'C:\Users\JESSDA~1\AppData\Roaming\npm;' +
 [System.Environment]::GetEnvironmentVariable('Path','User'),'User')
```
Close the terminal COMPLETELY (a new tab in Windows Terminal inherits old env) then
relaunch Hermes so retry inherits the new PATH. In cmd, `$env:Path=` fails with
"El nombre de archivo ... no son correctos" — use
`set "PATH=C:\Users\JESSDA~1\AppData\Roaming\npm;%PATH%"` for that session.

## Class 2 — same EBADENGINE but caused by an ODD Node major

After npm is fixed, EBADENGINE can reappear for a different reason:
```
npm ERR notsup Required: {"node":"^22 || ^24 || >=26"}
npm ERR notsup Actual:   {"node":"v25.8.0","npm":"11.17.0"}
```
Dependencies (e.g. `nanoid@6.0.0`) gate on EVEN Node majors (22/24/26+); Node 25
(odd "Current" branch) is rejected. **Fix: install Node 24 LTS** (nodejs.org),
which also satisfies the base `>=22.22.0`. Verify `node --version` in a new
terminal; if old persists, `where node` and reorder PATH the same way.

## Class 3 — update blocked: "Hermes is still running. Close all Hermes windows"

Log signature (stage=update, repeated many times):
```
error= "Hermes is still running. Close all Hermes windows and try the update again."
```
The updater refuses to touch files while any Hermes process lives. The Desktop app
hides in the system tray (arrow ^ by the clock) — closing the window does NOT exit
it. Fix:
1. Tray icon → right-click → Salir.
2. Task Manager (`Ctrl+Shift+Esc`) → kill everything containing "Hermes" (Electron
   app, `hermes.exe`, `hermes gateway`, console windows).
3. If it persists, restart Windows, then run the updater before opening anything.
Inspect survivors: `Get-Process | Where-Object { $_.Name -like "*hermes*" }`, then
`Stop-Process -Name hermes -Force`.

## General rules
- The installer is idempotent and resumes: after fixing the blocker, "Retry install"
  re-runs from the failed stage, not from scratch (repo and Python deps persist).
- The "browser tools / TUI npm install failed" lines in stage node-deps are the SAME
  root cause class but non-fatal there (installer continues) — fix npm/node once.
- Always read the LAST attempt in the log, not the first failure block: the log
  appends one "stage transition" block per retry and the current error may differ.