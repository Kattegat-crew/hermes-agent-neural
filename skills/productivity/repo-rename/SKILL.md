---
name: repo-rename
description: "Use when renaming a production-wired repo."
tags: [git, github, rename, systemd, migracion, verificacion]
category: devops
metadata:
  author: Ragnar
  version: "1.0.0"
---

# Repo Rename seguro (GitHub + host + systemd + rutas)

Renombrar un repo que está **cableado a producción** (systemd services, scripts con
rutas absolutas hardcodeadas, worker activo, crons) no es un `mv` ni un rename en
GitHub: es una operación sobre **4 planos** y, si se salta uno, algo queda roto o el
worker cae. Verificado end-to-end el 04/09/2026 (`video-ai-generator` →
`marketing-campaign-generator`, 41 commits intactos, worker `:8090` sano, sin romper
nada).

## Regla de oro

El rename **preserva historial, PRs y popularidad**: no es fork ni repo nuevo. La URL
vieja redirige con 301. Verificar, no asumir.

## Planos a tocar (todos)

1. **GitHub** — PATCH al repo (requiere `permissions.admin: true`).
2. **Host** — `mv` del directorio + `git remote set-url origin` a la URL nueva.
3. **Systemd** — units que apunten a la ruta vieja (`WorkingDirectory`, `EnvironmentFile`, `ExecStart`).
4. **Código** — rutas hardcodeadas en scripts y docs.

## Orden crítico de ejecución

**FASE 0 — Preparar** (backups antes de tocar nada)
- Backup del `.git/config` (remote) y de cada unit systemd que se vaya a reescribir.
- `git status` limpio / WIP commitado.
- Verificar permisos del token con `curl GET /repos/<org>/<repo>` → leer `permissions.admin` (rename lo exige).

**FASE 1 — Rename remoto (GitHub)**
```bash
curl -s -X PATCH -H "Authorization: Bearer $TOKEN" \
  https://api.github.com/repos/<org>/<repo> -d '{"name":"<nuevo>"}'
```
- Verificar: `full_name` → nuevo, `default_branch` intacto, historial intacto.
- Verificar que la URL vieja redirige (301), no 404.

**FASE 2 — Rename local (host)**
```bash
mv /root/<viejo> /root/<nuevo>
git remote set-url origin git@github.com:<org>/<nuevo>.git
```
- Verificar `git rev-list --count HEAD` (nº commits intacto) y `git log -1`.

**FASE 3 — Systemd**
- Reescribir cada unit (path nuevo) guardando `.bak`.
- `systemctl daemon-reload` + `restart` del service.
- ⚠️ `daemon-reload`/`restart` se hacen desde un **contenedor privilegiado** (ver pitfall abajo), no desde un volumen simple.

**FASE 4 — Código**
- `sed -i "s|/root/<viejo>|/root/<nuevo>|g"` sobre scripts (ROOT paths, `.fal-gate.json`, `.env`) y docs.
- Backupear el estado de scripts antes del sed (`cp -r scripts scripts.bak-<ts>`); NO commitear ese backup.

**FASE 5 — Commit + push + verificación**
- Escaneo de secretos antes de commit (`git diff --cached | grep -ioE 'ghp_...|sk-...|AKIA...'`).
- Push header-bearer, sin persistir credenciales.
- Verificar el worker con `GET /health` desde el **netns real del host** → `{"status":"ok"}`.

## Pitfalls (todos verificados, no asumidos)

- **`alpine/git` entrypoint es el binary git** (no acepta `sh`/`bash`): usar `--entrypoint sh` + `-e GIT_CONFIG_COUNT=1 -e GIT_CONFIG_KEY_0=safe.directory -e GIT_CONFIG_VALUE_0=<mount>` o git falla con "dubious ownership".
- **`systemctl daemon-reload` falla** con `nsenter: can't open /proc/1/ns/mnt: Permission denied` desde un volumen simple. Fix: `docker run --rm --privileged --network=host --pid=host -v /:/hostfs ... ` + `chroot /hostfs systemctl daemon-reload` (o `nsenter -t 1` con contenedor privilegiado).
- **Health-check del worker**: `curl`/`wget`/`ss` dentro de un chroot NO ven el socket (el proceso escucha en el netns del host). Fix: `nsenter -t 1 -n -- sh -c "wget -q -O- http://127.0.0.1:<port>/health"`.
- **Alpine no trae python3** — usar `sed`, no `python3 - << PYEOF`, para editar en volúmenes (o el fallo es silencioso).
- **Rutas hardcodeadas**: `grep -rl "<viejo>"` en `scripts/ docs/ README.md CHANGELOG.md` — hay rutas en `ROOT = Path(...)`, `.fal-gate.json`, `.env`, `sys.path.insert`, y strings de echo. Varre todo.
- **Renombrar ≠ mover**: la URL vieja de GitHub redirige (los clones viejos funcionan), pero el directorio host y las units NO redirigen — hay que re-apuntarlos.
- **No commitear backups** de scripts/docs (`.bak-<ts>`) al repo; quitar del staging antes del commit.

## Referencia completa

Runbook verificada con comandos exactos, referencias detectadas y salidas:
`references/repo-rename-safe-runbook.md`.
