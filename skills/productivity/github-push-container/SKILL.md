---
name: github-push-container
description: >-
  Use when pushing to GitHub from the Hermes container. Push a GitHub desde el contenedor: token y auditoría.
tags: [github, git, push, token, contenedor, container]
version: 1.0.0
author: Ragnar
triggers:
  - push: pushear / push a github / subir cambios al repo / actualizar repositorio
  - git: commitear / repo privado / token de github / deploy key / github push
  - backup: versionar en github / respaldar en repo / sincronizar brain a github
---

# GitHub Push desde el contenedor Hermes

Flujo verificado (19/08/2026) para empujar cambios de repos montados en el
contenedor a GitHub. Cubre: auditoría previa, autenticación por token sin
persistir credenciales, arreglo de permisos, escaneo de secretos y push.

## Flujo (obligatorio, en orden)

1. **Auditar qué existe** antes de tocar nada:
   ```bash
   ls /opt/repos  # inventario
   for r in /opt/repos/*/; do echo "-- $r"; git -C "$r" remote -v | head -2
     echo "branch: $(git -C "$r" rev-parse --abbrev-ref HEAD 2>/dev/null)"
     echo "dirty: $(git -C "$r" status --porcelain 2>/dev/null | wc -l) files"; done
   ```
   Además: `ls -d /opt/data/brain/.git /opt/data/skills/.git` (¿los datos viven en algún repo? si no, no se pueden pushear).
2. **Verificar acceso + auth del token**:
   ```bash
   TOKEN=$(sed -n 's/.*oauth_token: //p' ~/.config/gh/hosts.yml | head -1)
   curl -s -H "Authorization: Bearer $TOKEN" https://api.github.com/repos/<org>/<repo> \
     | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('full_name'), d.get('permissions'), d.get('default_branch'), 'private:', d.get('private'))"
   ```
   La SSH key del contenedor suele fallar (`Permission denied (publickey)`) — no pelear con ella; usar el token.
3. **Permisos de escritura local** — repos montados de root dan `index.lock: Permission denied` al commitear:
   ```bash
   sudo chown -R hermes:hermes /opt/repos/<repo>   # sudo passwordless disponible
   ```
4. **Escaneo de secretos ANTES de commitear**:
   ```bash
   git add -A && git diff --cached | grep -ioE '(sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{30,}|-----BEGIN [A-Z ]*PRIVATE)' | sort -u
   # vacío = OK; si no, NO commitear
   ```
5. **Push sin persistir credenciales** (header bearer, no tocar remote URLs):
   ```bash
   AUTH="Authorization: Basic $(printf 'x-access-token:%s' "$TOKEN" | base64)"
   git -c http.extraheader="$AUTH" push origin <rama>
   # si el remote usa SSH (git@github.com:...), push directo a URL https:
   git -c http.extraheader="$AUTH" push https://github.com/<org>/<repo>.git <rama>:<rama>
   ```
6. **Verificar el resultado**: el tail del push muestra `old..new  rama -> rama`; nunca dar por hecho sin verlo.

## Reglas de contenido al versionar conocimientos (brain/skills a un repo)

- NO volcar directorios enteros sin decantificar: skills incluyen mucho de terceros; brain incluye raw pesados (54M+ de descargas) y grafos generados (>1M). Versionar SOLO lo estructural: brain sin raw pesado (solo `raw/*.md`), sin `graphify-out/` (regenerable), sin `*.bak`; skills solo las de autoría propia (grep `author:` en cada SKILL.md).
- Documentar en README qué se incluye y qué se excluye.
- Respetar `.gitignore` del repo objetivo; ampliarlo si hace falta (p. ej. `brain/graphify-out/`, `brain/raw/*/`, `*.bak`).

## Pitfalls

- **SSH key del contenedor no autentica** → header bearer con TOKEN de `~/.config/gh/hosts.yml`. No persistir el token en la URL del remote (queda en .git/config).
- **Repos root-owned** → `sudo chown -R hermes:hermes` (sin esto `git commit` falla con index.lock).
- **Nombres de repo pueden engañar** (p. ej. guion final en documentación vieja): verificar el nombre real con la API, no asumir 403 ni el nombre viejo.
- **Un token puede pasar de no-push a push** sin aviso: verificar permisos en el paso 2, no asumir 403 permanente.
- **Hermes `write_file`/`patch` rechazan salir de `/opt/data`**: clonar repos de trabajo en `/opt/data/` (p. ej. `/opt/data/<repo>-repo/`).
- **Receta completa verificada del 19/08** (comandos, repos, commits): `references/2026-08-19-verified-push-session.md`. Ver también repos existentes en `/opt/vault/REPOS-ARQUITECTURA.md`.
