---
name: ecosystem-setup
description: "Use when setting up Ragnar's environment and tooling."
tags: [setup, entorno, pip, github-cli, notion, hermes-cli, ragnar, configuracion]
---

# Nexa Labs — Ecosystem Setup

## Context
Ragnar (AI Chief Orchestrator) se configura en un entorno Linux con Python 3.13. `pip` puede no estar disponible inicialmente y requiere bootstrapping.

## Environment Notes
- Working directory: `/opt/data/home`
- Skills path: `/opt/data/skills/`
- Cache path: `/opt/data/cache/`
- Config: `/opt/data/home/config.yaml`
- `pip` puede faltar — usar `get-pip.py` bootstrap si es necesario

## Pip Bootstrap (si pip no esta disponible)
```bash
python3 -m ensurepip 2>/dev/null || python3 -c "import urllib.request; urllib.request.urlretrieve('https://bootstrap.pypa.io/get-pip.py', '/tmp/get-pip.py')" && python3 /tmp/get-pip.py --break-system-packages
```

## GitHub CLI Setup
1. Descargar gh CLI:
```bash
curl -fsSL https://github.com/cli/cli/releases/download/v2.67.0/gh_2.67.0_linux_amd64.tar.gz -o /tmp/gh.tar.gz
mkdir -p ~/.local/bin && tar -xzf /tmp/gh.tar.gz -C /tmp && cp /tmp/gh_2.67.0_linux_amd64/bin/gh ~/.local/bin/gh
```
2. Autenticar:
```bash
gh auth login --with-token <<< "ghp_TU_PAT_AQUI"
```
3. Verificar: `gh auth status`

## Notion Integration
- Token: ver `config.yaml`
- Crear database con propiedades: Status, Priority, Module, Assignee, Due Date
- Usar `requests` library para API calls
- Notion API endpoint: `https://api.notion.com/v1/`

## Document Reader Skill
- Path: `/opt/data/skills/document-reader/`
- Dependencias: python-docx, openpyxl, pandas, PyPDF2, pdfplumber, mammoth, Pillow
- Script: `scripts/parse_document.py`

## Roster (Discord IDs)
- Jonathan (Killer420w) — CEO — Discord ID: 713538631918157853
- Chucho (Jesus) — CTO — Discord ID: 742803595241717840
- Server ID: 1493354289266167808

## Configuration File
`/opt/data/home/config.yaml` contiene todas las credenciales. Actualizarlo cuando se agreguen nuevos servicios.

## Hermes CLI Location
- Binary: `/opt/hermes/.venv/bin/hermes`
- Always set PATH first: `export PATH="/opt/hermes/.venv/bin:$PATH"`
- Or use full path: `/opt/hermes/.venv/bin/hermes`

## Skills Architecture (Critical)
Skills come in 3 sources: **builtin**, **hub-installed**, and **local**.

- **Builtin skills** (75): Bundled with Hermes binary. Auto-available, no install needed. Listed by `hermes skills list` with `Source: builtin`. Common names differ from internal names (e.g., `serving-llms-vllm` not `vllm`, `fine-tuning-with-trl` not `trl-fine-tuning`).
- **Hub-installed skills**: Downloaded from the skills hub via `hermes skills install`. Fail if you try to install a builtin skill — it's not in the hub.
- **Local skills** (8): Custom skills in `/opt/data/skills/`.

To check all available skills: `hermes skills list` — shows 3-column table with Name, Category, Source, Trust.

**Key command**: `hermes skills list` — this is the single source of truth for what's available. No separate "enable" step needed for builtin skills.

## Antigravity CLI (agy) — instalar en equipos nuevos (Windows incluido)

`agy` = CLI de Google Antigravity (binario Go ~220 MB, auto-actualiza en segundo plano). En DEV: `/usr/local/bin/agy`.

Instalación: usar el instalador oficial documentado en https://antigravity.google/docs/getting-started/ (script `install.sh` para Linux/macOS → `~/.local/bin/agy`; `install.ps1` para Windows → `%LOCALAPPDATA%\agy\bin\agy.exe`). Descargar el script y revisarlo antes de ejecutarlo; no usar pipe directo a shell.

Pitfall Windows (verificado con usuario "Jesús Díaz"): si el PATH de usuario supera ~1024 caracteres, `[Environment]::SetEnvironmentVariable(..., "User")` falla EN SILENCIO y `agy` no se reconoce aunque el binario exista. Diagnóstico: `[Environment]::GetEnvironmentVariable("Path","User").Length`. Solución segura (no tocar el PATH largo): alias permanente en `$PROFILE`:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned -Force
if (!(Test-Path $PROFILE)) { New-Item -ItemType File -Path $PROFILE -Force }
Add-Content $PROFILE 'Set-Alias agy "$env:LOCALAPPDATA\agy\bin\agy.exe"'
```

Con espacios/tildes en el usuario, invocar con `& "$env:LOCALAPPDATA\agy\bin\agy.exe"`.

Autenticación OAuth: el primer `agy` abre onboarding + login Google; cambiar cuenta con `/logout` (o `/help` si no existe). Para verificar la cuenta usada por el agy de una VPS, decodificar el `id_token` en `~/.gemini/antigravity-cli/antigravity-oauth-token` (en DEV fleet: `/opt/hermes-agent-data/fleet/agy-home/.gemini/antigravity-cli/`) — cuenta verificada 2026-10: `jonathaun124@gmail.com`.

## Common Pitfalls
- `hermes: command not found` — CLI not in PATH, use full path or `export PATH="/opt/hermes/.venv/bin:$PATH"`
- `Error: No skill named 'X' found in any source` — trying to install a builtin skill from hub (they're already bundled)
- Permission denied en `/opt/data/memories/` — eliminar lock files si existen
- `pip` no encontrado — usar bootstrap
- Notion token expirado — regenerar en Notion integrations page
- GitHub PAT expirado — verificar con `gh auth status`
- Skills names differ from expected: `serving-llms-vllm` (not `vllm`), `fine-tuning-with-trl` (not `trl-fine-tuning`), `gguf-quantization` (not `gguf`), `stable-diffusion-image-generation` (not `stable-diffusion`), `audiocraft-audio-generation` (not `audiocraft`), `segment-anything-model` (not `segment-anything`), `evaluating-llms-harness` (not `lm-evaluation-harness`)
