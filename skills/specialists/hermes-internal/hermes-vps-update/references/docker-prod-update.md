# Actualizar Hermes en PROD cuando corre en Docker Compose

Aplica a instancias servidas por contenedor (compose con `build: .`), no a
instalaciones nativas con systemd. La diferencia clave: en Docker el artefacto
desplegado es una **imagen**, y la pregunta previa no es «¿qué commits me faltan?»
sino «¿el árbol del repo es realmente lo que está corriendo?».

---

## 1. Pre-vuelo obligatorio: ¿el árbol coincide con la imagen?

Un repo puede tener rama, tags y commits correctos y **no** ser la fuente de la
imagen que corre. Comprobarlo con hashes, antes de prometer nada:

```bash
for f in agent/redact.py gateway/run.py hermes_cli/main.py agent/turn_context.py; do
  C=$(docker exec <container> sha256sum /opt/hermes/$f | awk '{print substr($1,1,12)}')
  H=$(sha256sum /opt/hermes/$f | awk '{print substr($1,1,12)}')
  printf '%-24s imagen=%s arbol=%s\n' $f "$C" "$H"
done
```

Si **cualquiera** difiere, el árbol no es el contexto de build: un
`docker compose build` hoy desplegaría otra cosa (típicamente el fork viejo, si
el repo quedó en una rama anterior). En ese caso **no se actualiza desde PROD**:
se transporta un commit ya validado (§2).

Señales de la misma deriva, más baratas de leer:

- `docker exec <container> hermes --version` → `vunknown` = imagen sin metadatos
  de versión; no se puede auditar imagen↔repo.
- `git describe --tags --abbrev=0 HEAD` devuelve un tag de respaldo
  (`backup/…`) en vez de una versión → el HEAD no nace de un release.
- `git merge-base --is-ancestor <tag-que-dice-correr> HEAD` → exit 1.

**Fix duradero:** construir con `--label org.opencontainers.image.revision=$(git
rev-parse HEAD)` y dejar un guard semanal que compare 5 hashes del contenedor
contra el árbol; si difieren, avisar.

## 2. Transportar el commit validado (sin merge ni reset)

En DEV, exportar solo el delta (PROD ya tiene el tag de upstream):

```bash
cd /opt/hermes-agent
git bundle create /tmp/ncl-vX.Y.Z.bundle <rama-validada> --not vX.Y.Z
git bundle verify /tmp/ncl-vX.Y.Z.bundle && sha256sum /tmp/ncl-vX.Y.Z.bundle
scp /tmp/ncl-vX.Y.Z.bundle prod:/root/
```

En PROD, rama nueva a partir del bundle y reconstrucción del overlay propio:

```bash
cd /opt/hermes
git fetch /root/ncl-vX.Y.Z.bundle <rama-validada>:ncl/vX.Y.Z
git switch ncl/vX.Y.Z
git checkout <HEAD-anterior> -- docker-compose.yml <archivos-modificados-sin-commit>
# untracked propios (ej. nginx-proxy/) se copian a mano
git add -A && git commit -m "chore(prod): preservar overlay de PROD sobre vX.Y.Z"
comm -23 <(git ls-tree -r --name-only <HEAD-anterior> | sort) \
         <(git ls-tree -r --name-only HEAD | sort) | grep -vE '^(skills|docs|tests)/' | head -30
```

Si el `comm` devuelve archivos, decidir cada uno antes de construir. Los archivos
bind-mounteados desde el repo (`tools/mcp_tool.py`, plugins parcheados) suelen
venir ya idénticos en la rama validada: comparar hash, no asumir.

## 3. Rollback: crearlo ANTES, no cuando hace falta

`docker images` puede tener **solo** la imagen actual. Sin tag previo no hay
vuelta atrás real:

```bash
docker tag <imagen-actual> rollback-prod:<version-anterior>
docker save rollback-prod:<version-anterior> | gzip > $B/imagen-rollback.tar.gz
```

El rollback completo es imagen + DBs + config + `.env`, en ese orden: cambiar el
tag del `image:` en el compose, `docker compose up -d`, restaurar cada `.db` con
`.restore` y las copias de config. Medirlo: 5–10 min, no «< 3 min».

## 4. Canario en Docker

Proyecto compose aparte, datos copiados, sin privilegios de PROD:

- `-p hermes-canary -f docker-compose.canary.yml`, `container_name` distinto y
  **otro puerto** (9120) fijado en el YAML del compose.
- Volumen `./data` propio: `rsync` de `config.yaml`, `.env`, `cron/`, `profiles/`
  (≥2 perfiles) y `skills/`; `cron/jobs.json` = `{"jobs": []}`.
- Sin `docker.sock`, sin vault, sin repos montados de PROD, plataformas apagadas.
- Allí se ensaya la migración de esquema y de config **sobre copia**.

`docker compose -p hermes-canary down` (nunca `-v`) al terminar.

## 5. Cutover y verificación

```bash
docker exec <container> hermes cron pause --all
docker compose stop hermes
sed -i 's|<imagen-vieja>|<imagen-nueva>|' docker-compose.yml
stat -c %h data/gateway.lock 2>/dev/null && rm -f data/gateway.lock   # solo con el contenedor parado y nlink=1
docker compose up -d
docker exec <container> hermes cron resume --all
```

Puertas que se pegan en el informe (no «parece que sí»):

- `docker ps` → `Up (healthy)` y la imagen nueva.
- health del API **desde dentro** del contenedor: si el puerto solo está publicado
  en una IP de Tailscale, `curl 127.0.0.1` desde el host da 000 y no significa caída.
- dashboard (`9119`) → 302; un servicio `active` puede devolver 500 si su entorno
  de runtime fue recolectado (ver pitfalls).
- nº de plataformas y `Connected as <bot>`; nº de crons; nº de servidores/tools MCP.
- `0 Traceback` en `data/logs/gateway.log` y `errors.log` desde el arranque.
- `sqlite3 data/state.db "PRAGMA quick_check; select version from schema_version;"`.
- diff de `config.yaml` contra el `.bak-<ts>` que deja el migrador: **solo**
  `_config_version` debe cambiar.
- decisión tomada sobre `session_reset` (ver SKILL.md).

## 6. Pitfalls propios de Docker

- **El contenedor puede seguir `active` con su entorno borrado.** Si un `pm gc`
  elimina el install-state mientras el proceso vive, cada request falla con
  `ModuleNotFoundError: anyio._backends` / `KeyError: 'asyncio'` y el servicio
  responde 500. Síntoma: el path del traceback apunta a un `installs/<id>` que ya
  no existe. Fix: `docker compose restart` (reconstruye/resuelve el entorno).
- **`docker compose down -v`, `volume prune`, `system prune`**: prohibidos. El
  volumen de datos es el negocio.
- **`gateway.lock` con `nlink>1`** (snapshot/backup con hard-links): borrarlo solo
  tras `stat -c %h` = 1, o el gateway arranca creyendo que hay otro.
- **UID**: el contenedor corre con `HERMES_UID`/`HERMES_GID` (10000 habitual). Todo
  archivo que se cree en el host para el contenedor debe quedar con ese dueño.
- **`data/` es bind mount** (`./data:/opt/data`): respaldar DBs con `.backup`, no
  con `cp` en caliente; el `rsync` de datos vivos nunca con `--link-dest`.
- **El `.env` vive dos veces** (raíz del compose y dentro de `data/`): respaldar
  ambos y verificar sus hashes; nunca registrarlos en claro.
