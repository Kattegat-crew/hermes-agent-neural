---
name: hermes-desktop-ssh-backend
description: >-
  Use when Hermes Desktop connects to a VPS backend via SSH (connection.json
  mode "ssh") and fails with "remote install does not support
  --ssh-session-token-file", or connects but shows no sessions/bots/profiles,
  or reports "le falta inferencia". Covers the SSH-stable workflow end to end.
category: devops
tags: [hermes, desktop, ssh, vps, hermes_home, remoteHermesPath, sessions, profiles, inference]
version: 1.0.0
author: Hermes
triggers:
  - desktop ssh
  - conexion ssh hermes
  - no veo mis sesiones
  - le falta inferencia
  - ssh-session-token-file
  - remote Hermes install does not support
  - no aparecen bots
  - ssh no me deja
---

# Hermes Desktop ↔ VPS por SSH (workflow estable)

La conexión **SSH** es la que el usuario prefiere porque es **más estable** que el
modo "Remote gateway" (`hermes serve` en 9112), que se cae seguido. Este runbook
cubre el flujo completo verificado el 20/08/2026 en Hermes v0.20.4 (Desktop en
Windows → VPS root, host `147.93.3.250`).

## Cómo funciona (mental model — CLAVE)

1. Desktop (Electron) NO usa el `hermes serve` de 9112 en modo SSH. **Lanza su
   propio backend remoto** por SSH:
   ```bash
   hermes serve --isolated --host 127.0.0.1 --port 0 \
     --ssh-session-token-file <token> --ssh-owner-nonce <nonce>
   ```
   y lo expone por túnel local `127.0.0.1:<puerto>` → puerto remoto.
2. La config de la conexión vive en **Windows**:
   `C:\Users\wwwko\AppData\Roaming\Hermes\connection.json` (JSON con `mode`,
   `remote.host/user/keyPath/remoteHermesPath`).
3. `locateHermes` resuelve el binario remoto con este orden (primero que exista):
   `command -v hermes` → `~/.local/bin/hermes` → `/usr/local/bin/hermes` →
   `~/.hermes/hermes-agent/venv/bin/hermes`.
4. El **home de datos** del backend lanzado lo decide `probeRemoteHermesHome`:
   `echo "${HERMES_HOME:-$HOME/.hermes}"`. Si `HERMES_HOME` no está en el entorno
   SSH, cae a `~/.hermes` (¡vacío!) aunque los datos reales vivan en otra parte.
5. `remoteSupportsSshOwnership` comprueba el binario remoto:
   ```bash
   help="$($hermes serve --help 2>&1)"
   printf '%s' "$help" | grep -q ssh-session-token-file && \
   printf '%s' "$help" | grep -q ssh-owner-nonce && echo YES || echo NO
   ```

## Diagnóstico en 4 capas (en este orden)

### Capa 1 — El binario remoto está mal apuntado
Síntoma en `C:\Users\wwwko\AppData\Local\hermes\logs\desktop.log`:
```
[ssh-lifecycle] located hermes at /root/hermes-agent-legacy-docker
Desktop boot failed: The remote Hermes install does not support
--ssh-session-token-file and --ssh-owner-nonce.
```
Si `located hermes at <ruta>` muestra un **directorio** (p.ej. `/root/hermes-agent-legacy-docker`
o `/root/hermes-agent-legacy-docker/data`) en vez de un binario, Desktop ejecuta
`/root/hermes-agent-legacy-docker serve --help` → `Is a directory` → grep falla → error.

**Fix:** en `connection.json` poner `remoteHermesPath` al binario real:
```json
"remoteHermesPath": "/usr/local/bin/hermes"
```
(O dejarlo vacío para auto-detect; `/usr/local/bin/hermes` es lo correcto en este VPS.)
Siempre **cerrar la app** antes de editar el JSON (si está abierta lo sobrescribe al salir).
Verificación remota del binario:
```bash
hermes serve --help 2>&1 | grep -cE "ssh-session-token-file|ssh-owner-nonce"   # debe ser >= 2
```

### Capa 2 — HERMES_HOME no apunta a los datos reales
Síntoma: conecta bien (el log muestra `Remote Hermes backend is ready`), pero **no
aparecen sesiones, bots ni perfiles** (Ragnar, etc.), y el `state.db` del backend
lanzado está casi vacío.

Causa raíz: el backend SSH hereda `HERMES_HOME=${HERMES_HOME:-$HOME/.hermes}` =
`/root/.hermes`, que es un home **distinto** del real. En este VPS los datos viven
en `/root/hermes-agent-legacy-docker/data` (state.db ~160MB, perfiles `ragnarcho` y `shared`),
mientras `/root/.hermes/state.db` era ~229KB (vacío).

**Fix — bindear HERMES_HOME en toda sesión SSH:**
```bash
# 1) sshd debe permitir variables de entorno del usuario
printf 'PermitUserEnvironment yes\n' > /etc/ssh/sshd_config.d/99-hermes-env.conf

# 2) definir HERMES_HOME para el usuario
umask 077
printf 'HERMES_HOME=/root/hermes-agent-legacy-docker/data\n' > /root/.ssh/environment
chmod 600 /root/.ssh/environment

# 3) validar y recargar
sshd -t && systemctl reload ssh   # o: service ssh reload
```
**Verificar:**
```bash
ssh root@<host> 'echo $HERMES_HOME'                      # -> /root/hermes-agent-legacy-docker/data
env HERMES_HOME=/root/hermes-agent-legacy-docker/data hermes profile list   # debe listar perfiles
```

### Capa 3 — Inferencia sin key / provider
Síntoma: "le falta inferencia". El `config.yaml` del HERMES_HOME activo apunta a un
provider sin key o con key inválida.

Fix: alinear `config.yaml` del home con un provider que funcione (ver skill
`nan-builders-api` y `hermes-provider-configuration`). En este VPS lo que funciona:
```yaml
model:
  api_key: <key>
  base_url: https://api.nan.builders/v1
  default: deepseek-v4-flash
  max_tokens: 65536
  provider: NaN-Builders
providers:
  NaN-Builders:
    api_key: <key>
    base_url: https://api.nan.builders/v1
```
Verificar la key (debe dar 200):
```bash
curl -sS -o /dev/null -w "%{http_code}\n" https://api.nan.builders/v1/models \
  -H "Authorization: Bearer $KEY"   # -> 200
```
Hacer backup antes de editar: `cp ~/.hermes/config.yaml ~/.hermes/config.yaml.bak.<fecha>`.
Cuando se edita `config.yaml` con un `api_key` dentro, **no** hace falta tocar `.env`.

### Capa 4 — Proceso/lock viejo reutilizado
Síntoma: tras arreglar config, Desktop sigue con el backend anterior.

Causa: Desktop reusa el dashboard remoto vía lockfile si el proceso sigue vivo y
"owned". Un backend lanzado antes de los fixes sigue con la config vieja.

**Fix — matar los dashboards SSH stale y limpiar locks:**
```bash
ps aux | grep "serve --isolated.*ssh-session-token-file" | grep -v grep   # identificar pids
kill <pid>                                              # todos los que apliquen
rm -rf /root/.hermes/desktop-ssh/*                      # limpiar locks de ownership
```
Después, en Desktop: **Sign out → Sign in** (o cerrar y reabrir) para forzar un
backend nuevo con la config corregida.

## Orden recomendado al resolver un caso completo

1. Ver `C:\Users\wwwko\AppData\Local\hermes\logs\desktop.log` (tail) → buscar
   `[ssh-lifecycle] located hermes at <ruta>` y el mensaje de fallo.
2. Si la ruta es un directorio → Capa 1 (corregir `remoteHermesPath`).
3. Probar el binario remoto (`serve --help | grep`). Debe dar YES.
4. Conectar → si "ready" pero sin sesiones/bots → Capa 2 (HERMES_HOME).
5. Si conecta y hay sesiones pero responde "le falta inferencia" → Capa 3 (provider/key).
6. Después de cualquier cambio en config remota → Capa 4 (matar stale + re-login).

## Pitfalls

- **El diálogo de "instalar subsistema para Linux / WSL" es un falso aviso.** El
  modo SSH usa `ssh.exe`/`bash.exe` (Git Bash), NO WSL. Se puede ignorar.
- `connection.json` con `keyPath` estilo Linux (`/root/.ssh/...`) funciona porque
  el cliente SSH del usuario lee `~/.ssh/config` (Host 147.93.3.250 → IdentityFile).
- No editar `connection.json` con la app abierta.
- Los perfiles de sesiones son **por perfil** (`ragnarcho` vs `shared`) y dependen
  del HERMES_HOME correcto; si no eliges el perfil, parece que "no hay nada".
- `hermes serve` en 9112 (modo remote gateway) corre con su propio
  `HERMES_HOME=/root/hermes-agent-legacy-docker/data` y **no se recarga** solo al cambiar
  `config.yaml`; necesita reinicio de ese proceso/servicio.

## Referencias
- `references/caso-2026-08-20.md` — caso real completo con salidas y pasos exactos.
- Skills relacionadas: `hermes-desktop-remote-connection`, `hermes-desktop-remote-backend`,
  `nan-builders-api`, `hermes-provider-configuration`, `vps-host-access`.
