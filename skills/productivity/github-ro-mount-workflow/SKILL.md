---
name: github-ro-mount-workflow
description: "Use when a repo mount is read-only; push via clone."
tags: [github, git, push, read-only, mounts, token]
version: 1.0.0
author: Hermes Agent (curator)
license: MIT
metadata:
  hermes:
    tags: [GitHub, Git, Repos, VPS, Push]
    category: github
    related_skills: [github-push-container, github-repo-management]
---

# Push a GitHub desde mounts de solo lectura (`/opt/repos/*`)

Complementa `github-push-container` (skill del usuario, no editable por el curator): esa receta
asume `sudo chown -R hermes:hermes /opt/repos/<repo>` para habilitar commits in-place. En el
contenedor Hermes actual **no hay `sudo`** y los mounts vienen `ro,relatime` — el chown es
imposible y `touch` falla con `Read-only file system`. El flujo verificado (28/08/2026, imagen
Goldie → Golden-Game-Casinos) es trabajar contra un clon escribible.

## When to Use

- El usuario pide colocar un archivo (imagen, doc) "en el repositorio" montado en `/opt/repos/...`.
- `touch` o `cp` dentro del repo falla con `Read-only file system`, o `mount` muestra `ro,relatime`.
- No hay `sudo` disponible para re-chownear el mount.

## Cuándo aplica este flujo en vez del in-place

```bash
mount | grep <repo>          # aparece ro,relatime → este flujo
touch /opt/repos/<repo>/.wtest 2>&1   # "Read-only file system" → este flujo
which sudo                   # ausente → este flujo
```

## Flujo (obligatorio, en orden)

1. **Verificar permisos del token ANTES de nada** (un token puede tener push aunque antes diera 403):
   ```bash
   TOKEN=$(sed -n 's/.*oauth_token: //p' ~/.config/gh/hosts.yml | head -1)
   curl -s -H "Authorization: Bearer $TOKEN" https://api.github.com/repos/<org>/<repo> \
     | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('default_branch'), d.get('permissions',{}).get('push'))"
   ```
2. **Clonar con header bearer** — `git clone https://…` sin header muere con `could not read Username for 'https://github.com': No such device or address`:
   ```bash
   AUTH="Authorization: Basic $(printf 'x-access-token:%s' "$TOKEN" | base64)"
   cd /opt/data && rm -rf <repo>-work
   git -c http.extraheader="$AUTH" clone --depth 5 https://github.com/<org>/<repo>.git <repo>-work
   ```
3. **Auditar el working tree del mount RO antes de duplicar trabajo**: puede tener archivos ya colocados pero SIN commitear por otro agente/sesión (`git -C /opt/repos/<repo> status --short`). Elegir nombre de archivo que no pise el huésped y avisar al usuario.
4. **Copiar + commit** (autor explícito, el contenedor no tiene identidad git global fiable):
   ```bash
   cp <src> <repo>-work/public/assets/images/<nombre>.jpg   # o la convención del repo
   cd <repo>-work && git add <ruta>
   git -c user.name="<usuario>" -c user.email="<usuario>@users.noreply.github.com" \
     commit -m "feat(assets): ..."
   ```
   Escaneo de secretos si son textos: `git diff --cached | grep -ioE '(sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{30,}|-----BEGIN [A-Z ]*PRIVATE)' | sort -u` (vacío = OK).
5. **Push a URL https explícita** (el remote local suele ser SSH `git@github.com:` — no autentica):
   ```bash
   git -c http.extraheader="$AUTH" push https://github.com/<org>/<repo>.git <rama>
   # éxito: tail muestra "old..new  rama -> rama"
   ```
6. **Verificación externa obligatoria** — `git ls-remote` tras el push también pide credenciales y falla; usar la API/raw:
   ```bash
   curl -s -o /dev/null -w "%{http_code} %{size_download}\n" \
     -H "Authorization: Bearer $TOKEN" \
     "https://raw.githubusercontent.com/<org>/<repo>/<rama>/<ruta/al/archivo>"
   # 200 + tamaño idéntico al original = entregado
   ```

## Pitfalls

- **El exit code del bloque shell engaña**: el push imprimió `3d40f4b..eda2ad0 main -> main` (éxito) pero el comando final del script (`ls-remote`) falló y devolvió exit 128. Leer la SALIDA línea por línea, no solo el exit code.
- **No persistir el token** en remote URLs ni `.git/config` — siempre `-c http.extraheader=…`.
- **Repositorios privados**: el raw verificado requiere el header Bearer; sin él da 404, no 403.
- **`/opt/data/entregables/<repo>/` NO es una copia del repo** (solo docs) — no asumir que existe un espejo escribible; verificar con `git -C … remote -v`.
- Si además hace falta desplegar (Coolify), eso es otra capa: ver `coolify-api-operations`.

## Receta verificada (28/08/2026)

Repo `Kattegat-crew/Golden-Game-Casinos`, rama `main`: clon → imagen en la carpeta de imágenes
del repo (bajo `public/assets/`) → commit `eda2ad0` → push OK → raw 200 con 176676 bytes
(idéntico al original). El working tree del mount ya tenía otra copia de la mascota sin
commitear — se eligió nombre distinto para no pisarla.
