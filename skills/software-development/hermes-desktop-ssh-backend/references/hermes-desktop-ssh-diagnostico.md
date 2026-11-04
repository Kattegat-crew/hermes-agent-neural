<!-- Caso absorbido por F6 lote 2 el 2026-09-23 desde `software-development/hermes-desktop-ssh-diagnostico`.
     Contenido íntegro; original en
     `data/archive/F6_lote2_20260923-154924/absorbidas/`. -->

---
name: hermes-desktop-ssh-diagnostico
description: >-
  Use when to connect Hermes Desktop to a VPS backend via SSH and it fails with
  "remote install does not support --ssh-session-token-file", connects but shows no
  sessions/bots/profiles, or reports "le falta inferencia". Diagnóstico por capas.
category: devops
tags: [hermes, desktop, ssh, vps, hermes_home, remoteHermesPath, perfiles, sesiones, inferencia]
version: 1.0.0
author: Hermes
triggers:
  - no veo mis sesiones
  - le falta inferencia
  - ssh-session-token-file
  - remote hermes install does not support
---

# Hermes Desktop → VPS por SSH — diagnóstico

## Mapa mental (el flujo)

Español/Key:
1. Desktop **NO** usa `hermes serve` 9112 en modo SSH. **Lanza su propio backend remoto**
   por SSH: `hermes serve --isolated --ssh-session-token-file ... --ssh-owner-nonce ...`
2. Config en Windows: `C:\Users\wwwko\AppData\Roaming\Hermes\connection.json`
   (`mode`, `remote.host/user/keyPath/remoteHermesPath`).
3. `locateHermes` resuelve el binario remoto en orden: `command -v hermes` →
   `~/.local/bin/hermes` → `/usr/local/bin/hermes` → `~/.hermes/hermes-agent/venv/bin/hermes`.
4. El **home de datos** del backend lanzado lo elige `probeRemoteHermesHome`:
   `echo "${HERMES_HOME:-$HOME/.hermes}"`. Si `HERMES_HOME` no va en el entorno SSH,
   cae a `~/.hermes` (¡vacío!) aunque los datos reales vivan en otro lado.
5. `remoteSupportsSshOwnership` comprueba el binario: grep `ssh-owner-nonce` en `serve --help`.

## Diagnóstico en 4 capas (en este orden)

### Capa 1 — Binario remoto mal apuntado
`[ssh-lifecycle] located hermes at /root/hermes-agent-legacy-docker` (un **directorio**) → Desktop usa
`/root/hermes-agent-legacy-docker serve --help` → `Is a directory` → grep falla.
Fix: `connection.json` → `remoteHermesPath` al binario (`/usr/local/bin/hermes`).
Verificación remota:
```bash
hermes serve --help 2>&1 | grep -cE "ssh-session-token-file|ssh-owner-nonce"   # = 2
```

### Capa 2 — `HERMES_HOME` no apunta a los datos reales
Síntoma: conecta (`Remote Hermes backend is ready`) pero sin sesiones/bots/perfiles.
`HERMES_HOME=${HERMES_HOME:-$HOME/.hermes}` = `/root/.hermes` (débil);
los datos viven en `/root/hermes-agent-legacy-docker/data` (ragnarcho, compartidos; state.db de 164 MB).
Fix: `PermitUserEnvironment yes` + `/root/.ssh/environment`
(`HERMES_HOME=/root/hermes-agent-legacy-docker/data`).

### Capa 3 — Sin key / provider
"le falta inferencia": el `config.yaml` del home activo apunta a OpenRouter (`claude-opus-4.6`) sin key.
Fix: alinear `config.yaml` a NaN-Builders (`api.nan.builders/v1`, `deepseek-v4-flash`); backup.

### Capa 4 — Proceso SSH stale re-usado
`hermes serve --isolated...` viejo (pid) sigue vivo y Desktop lo reutiliza vía lockfile.
Fix: matar el proceso + limpiar `/root/.hermes/desktop-ssh/`.

## Referencias y falsos positivos

- El diálogo "instalar subsistema Linux/WSL" es un falso aviso: el modo SSH usa `ssh.exe`/Git
  Bash, no WSL.
- `connection.json` con `keyPath` estilo Linux (`/root/.ssh/...`) funciona porque el cliente
  SSH del usuario lee `~/.ssh/config`.

## Referencia
- `references/caso-2026-08-20.md`
- Skills relacionadas: `hermes-desktop-remote-connection`, `hermes-desktop-remote-backend`,
  `vps-host-access`, `nan-builders-api`, `hermes-provider-configuration`.