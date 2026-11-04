---
name: hermes-vps-update
description: "Use when updating Hermes Agent on the VPS host."
tags: [hermes, vps, update, actualizar, upstream, docker, backup, gateway]
license: MIT
metadata:
  author: opencode
  version: "1.0"
---

# Actualizar Hermes Agent en VPS (a upstream/main) sin perder config

Patrón para el mantenimiento de instancias de Hermes en hosts remotos: lleva el
checkout a la última de NousResearch, rearma el gateway Docker y preserva TODA la
config real (`data/`, `.env`, NaN-Builders, allowlists, perfiles). El Desktop OS
pide este procedimiento cuando reporta "update hermes on the remote host".

## Disparadores

- «hermes update», «actualizar hermes en el VPS», «update hermes remote host»,
  «alinear hermes a upstream/main», «actualizar el fork», «estudio semanal de
  actualizaciones de Hermes».

## Decisión previa OBLIGATORIA: ¿el checkout tiene parches propios?

Antes de tocar nada, medir la divergencia. `reset --hard` / `checkout -B main
upstream/main` solo son válidos si la respuesta es 0:

```bash
cd /opt/hermes-agent        # o el checkout objetivo
MB=$(git merge-base HEAD upstream/main)
echo "propios: $(git rev-list --count $MB..HEAD) | detrás: $(git rev-list --count HEAD..$(git tag -l 'v0.*' | sort -V | tail -1))"
git log --oneline $MB..HEAD -- agent hermes_cli gateway tools plugins cron | wc -l
```

- **0 commits propios** → seguir el procedimiento de abajo (reset a upstream).
- **>0 commits propios** → **PROHIBIDO** `reset --hard` / `checkout -B main`:
  borra el fork entero. Usar el replay de parches de
  `references/fork-upstream-replay.md` (rama nueva desde el tag limpio +
  `cherry-pick -x` de los commits propios, `rerere` activo).

Caso real (nov-2026, `/opt/hermes-agent`): 56 commits propios de código, base
`v0.22.0`, 9.000 commits detrás de `v0.22.6`, solape en 67 archivos (49 de
código). Un `reset --hard` ahí habría borrado DSML guard, glm5.3-flash, memoria
on-demand, heartbeat efímero, frenos Telegram, Config Shield y `skill_route` —
ninguna existe upstream.

## Pre-vuelo: backups (obligatorio)

```bash
# 1. data/ completo (git-ignored, config real)
rsync -aHA /root/hermes-agent-legacy-docker/data/ /root/hermes-agent-legacy-docker-backups/data-$(date +%Y%m%d-%H%M%S)/
# 2. .env del root
cp /root/hermes-agent-legacy-docker/.env /root/hermes-agent-legacy-docker/.env.pre-update-$(date +%Y%m%d-%H%M%S)
git -C /root/hermes-agent-legacy-docker hash-object .env   # anotar hash para verificar post
```

## Procedimiento

### 1. Alinear checkout a upstream/main

```bash
cd /root/hermes-agent-legacy-docker
git fetch origin && git fetch upstream
git checkout -B main upstream/main
git reset --hard upstream/main
git hash-object .env     # DEBE ser idéntico al hash pre-vuelo
git check-ignore data    # → data/
```

Peligro: `git checkout` a `upstream/main` SOBRESCRIBE el `docker-compose.yml`
personalizado del VPS. Restaurarlo SIEMPRE desde la rama previa:

```bash
git show release-v0.20.4:docker-compose.yml > /root/hermes-agent-legacy-docker/docker-compose.yml
```

Luego apuntar `image:` a la imagen construida de la rama main (`hermes-agent`).

### 2. Reinstalar venv host + migrar config

```bash
cd /root/hermes-agent-legacy-docker
VIRTUAL_ENV=/opt/hermes-venv uv pip install -e ".[all,dev]"
/opt/hermes-venv/bin/hermes --version    # debe decir "Up to date"

# migrar la config REAL (HERMES_HOME explícito — sin él apunta a ~/.hermes)
VIRTUAL_ENV=/opt/hermes-venv HERMES_HOME=/root/hermes-agent-legacy-docker/data \
  /opt/hermes-venv/bin/python3.11 -c "
import os; os.environ['HERMES_HOME']='/root/hermes-agent-legacy-docker/data'
from hermes_cli.config import migrate_config; print(migrate_config(interactive=False))
"
```

### 3. Reconstruir el gateway Docker

```bash
cd /root/hermes-agent-legacy-docker
docker compose build     # reintentar si falla con `denied` en ghcr (ver Pitfalls)
docker compose up -d
```

### 4. Post-verificación

```bash
/opt/hermes-venv/bin/hermes --version
VIRTUAL_ENV=/opt/hermes-venv HERMES_HOME=/root/hermes-agent-legacy-docker/data \
  /opt/hermes-venv/bin/python3.11 -c "import os;os.environ['HERMES_HOME']='/root/hermes-agent-legacy-docker/data';from hermes_cli.config import check_config_version;print('config_version:',check_config_version()[0])"
cat /root/hermes-agent-legacy-docker/data/gateway_state.json | python3 -m json.tool | grep -A1 '"state"'
docker exec hermes-agent /opt/hermes/bin/hermes --version
```

## Supervisar un replay en curso ejecutado por otro agente

Cuando el replay lo corre un agente externo (Agy/antigravity, Claude Code, otro
perfil), **su informe de cierre no es evidencia**. Auditar el worktree con
comandos propios antes de dar el segundo OK; receta completa en
`references/auditoria-replay-tercero.md`.

Comprobación mínima (3 comandos, ~1 minuto):

```bash
W=/opt/hermes-agent-worktrees/upgrade-vX.Y.Z
# 1. ¿están TODOS los commits propios? (sin tr -d '\r' el comm miente)
cd /opt/hermes-agent; MB=$(git merge-base <rama-propia> vX.Y.Z)
git log --format='%s' $MB..<rama-propia> -- agent hermes_cli gateway tools plugins cron | tr -d '\r' | sort > /tmp/own.txt
cd $W; git log --format='%s' vX.Y.Z..HEAD | tr -d '\r' | sort > /tmp/rep.txt
comm -23 /tmp/own.txt /tmp/rep.txt        # ← debe salir vacío
# 2. ¿la «suite» que dice haber corrido es la suite?
python3 -c "import json;print(len(json.load(open('$W/.pytest_cache/v/cache/nodeids'))))"
git ls-tree -r --name-only HEAD | grep -cE '^tests/.*test_.*\.py$'
# 3. ¿sobreviven los archivos propios que upstream no tiene?
comm -23 <(git -C /opt/hermes-agent ls-tree -r --name-only HEAD | sort) \
         <(git ls-tree -r --name-only HEAD | sort) | head -30
```

Verde en 5 archivos de test sobre un repo de miles NO es «suite completada»:
exigir `scripts/run_tests.sh` y su salida.

## Pitfalls (anotadas: causa raíz de la operación real)

- **`cherry-pick` con conflicto `modify/delete` borra archivos propios en silencio**:
  si upstream eliminó un archivo que el fork mantiene (`PROJECT_MEMORY.md`,
  `.skills/`), la resolución natural deja la versión upstream (borrado) y el
  replay queda verde sin ese contenido. **Fix**: comparar los árboles del repo
  principal y de la rama nueva y restaurar los archivos del fork antes del cutover.
- **El trabajo sin commitear no viaja en el replay**: `cherry-pick` solo mueve
  commits; `gateway/run.py` y compañía con `git status` sucio se pierden o
  bloquean el `switch`. Contarlos con `git status --porcelain | awk '{print $1}'
  | sort | uniq -c` y resolverlos (commit temporal o parche exportado) antes de
  autorizar.
- **`git checkout upstream/main` sobrescribe `docker-compose.yml` del VPS**: el
  compose genérico de upstream monta `~/.hermes` y crea `hermes` +
  `hermes-dashboard`, NO tu `./data`, `.env`, vault, `mcp_tool.py` → contenedores
  accidentales apuntando a data vacía. **Fix**: restaurar el compose personalizado
  de la rama previa (mounts `./data`, `.env`, `./tools/mcp_tool.py`, vault,
  puertos `3000/9119`, `container_name: hermes-agent`, `image: hermes-agent`).
- **Token `ghcr.io` revocado (en `~/.docker/config.json`)**: rompe el build del
  `uv` público. **Fix**: backup del config docker, quitar la entrada `ghcr.io`
  (pull anónimo de imagen pública OK), reintentar el pull por reset de IPv6
  transitorio.
- **HERMES_HOME explícito**: sin él, `hermes` del host apunta a `~/.hermes`
  (default), NO a la data real del gateway (`/root/hermes-agent-legacy-docker/data`).
- **Migración sin pérdida**: esperar `env_added: []` y `config_added: []`.
- **Tags de fecha `v2026.M.D` no son versiones**: un regex `v(\d+)\.(\d+)\.(\d+)`
  los toma como "la última estable" y el informe concluye falsamente
  "0 commits por detrás". Filtrar `^v0\.(\d+)\.(\d+)$`.
- **`reset --hard` en un fork con parches propios destruye el trabajo**: verificar
  primero `git rev-list --count $MB..HEAD` (ver "Decisión previa") — no asumir
  que todo checkout de Hermes es descartable.
- **`shared:a2a fatal` (bind 9900)**: pre-existente, no es un retroceso del update.

## Rollback de una actualización fallida

Cuando el upgrade/port rompe el sistema, el procedimiento inverso (snapshot del
estado malo, reconstrucción del árbol pre-upgrade desde parche de tracked +
tarball de untracked, restauración de state.db y reinicio canónico) está en
`references/rollback-failed-upgrade.md`. Incluye el pitfall de los normalizadores
de config que silencian valores nuevos (`tool_progress_grouping: replace`
rechazado por v0.22.6 → caía a `accumulate`).

## Auditoría post-deploy por host (lección 04-nov-2026: DEV y PROD divergieron)

Tras un upgrade fallido en DEV y un deploy exitoso de Roshi en PROD, los dos hosts quedaron en estados opuestos. Tres reglas duras extraídas:

- **La conclusión de un host nunca es el estado del otro.** Antes de recomendar revertir/desplegar, verificar EN VIVO en cada host: `docker ps` (imagen exacta), `docker inspect` (StartedAt, RestartCount), health desde dentro del contenedor y plataformas conectadas de `gateway.log` (`Gateway running with N platform(s)`).
- **Comparar timestamp de la imagen construida vs timestamp de los commits de fix.** Si la imagen se construyó ANTES de los fixes, los huecos están vivos en producción aunque el deploy haya sido «exitoso». Verificar dentro del contenedor: `docker exec hermes-agent grep -n "tool_progress_grouping" /opt/hermes/gateway/display_config.py`.
- **Verificar que la regresión aplica al host ANTES de proponer revertir.** El rechazo de `replace` en `display_config.py` era irrelevante en PROD porque su config tenía `tool_progress: 'off'`. Revertir un sistema sano por una brecha que su config no ejercita es churn con riesgo propio. Caso real: la sugerencia de revertir PROD se retiró tras revisar su config.

Y no presentar una conclusión vieja como actual: si el deploy de terceros ocurrió DESPUÉS del último chequeo, re-auditar antes de responder (un «PROD está intacto» previo al deploy miente después del deploy).

## Salida

- Archivos tocados y estado post-verificación.
- Ruta de backups creados.
- Comandos reales ejecutados.
- `config_version` y plataformas en `gateway_state`.
- Cualquier incidente.

## Referencias

- `references/fork-upstream-replay.md` — actualizar un fork con parches propios
  (replay de parches, medición de solape, ¿upstream ya lo trae?) y cadencia
  semanal con autorización en dos pasos.
- `references/rollback-failed-upgrade.md` — rollback de un upgrade fallido:
- `references/auditoria-replay-tercero.md` — auditar un replay ejecutado por
  otro agente: leer su transcript, cobertura real de commits, paridad funcional
  por keyword y los dos agujeros (modify/delete y working tree sucio).
- `scripts/hermes_upstream_review.py` — informe semanal listo para Discord
  (≤1900 chars) con veredicto de riesgo; detalle en
  `/opt/data/logs/hermes-upstream-review-latest.md`.
- `docs/actualizacion-hermes-vps-2026-08-20.md` — bitácora completa de la operación real.
- `hermes-desktop-remote-connection/SKILL.md` — diagnóstico de conexión remota Desktop.
