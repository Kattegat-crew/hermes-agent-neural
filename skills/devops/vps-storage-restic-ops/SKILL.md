---
name: vps-storage-restic-ops
description: Use when a VPS disk fills up, when pruning space on DEV/PROD, or when moving restic backups off-site to a 3-2-1 layout. Audit method, what is NOT cache, restic pitfalls and the verified pull-to-PROD architecture.
category: devops
---

# VPS storage audit + restic 3-2-1

## Cuándo usar
- "el disco está al X%", "hace falta poda", "qué se puede borrar"
- mover respaldos a otro servidor para liberar DEV
- un `restic forget/prune` falla con "repository is already locked"

## 1. Medir antes de opinar
```bash
df -h /
du -x --max-depth=1 -B1 /opt | sort -nr | head
du -x --max-depth=1 -B1 /opt/hermes-agent-data | sort -nr | head
```
Reglas de medición:
- `du -sb` **no** admite `--max-depth` (error "summarizing conflicts"). Usar `du -x --max-depth=1 -B1 <path>`.
- Sin `-x`, `du /` se cuela en `/proc` y devuelve cifras absurdas (TB).
- Un directorio grande **no** es sinónimo de caché: hay que mirar dentro y ver qué proceso lo usa.

## 2. Lo que en DEV parece caché y NO lo es
- `/root/.codex/packages` — binarios del daemon Codex **en ejecución** (`app-server --managed-daemon`). Borrarlo lo tumba.
- `/root/.codex/sessions`, `/root/.codex/thread_history*.sqlite` — historial, no regenerable.
- `/root/.gemini/antigravity-cli`, `/root/.akari/app` — CLIs instaladas, no caché.
- `/root/.local/share/opencode/opencode.db` — base de sesiones.
- `/opt/hermes-agent-data/installs/*` — entornos con `.install.lock` activo.

Sí son basura segura: `/root/.npm/_cacache`, `/root/.cache/restic`, `/root/.cache/uv`,
servidores VS Code viejos en `/root/.vscode-server/cli/servers/` (conservar el de mtime más reciente),
`/tmp` con más de 48 h y `drafts/` de proyectos ya entregados.
Verificar antes de borrar: `pgrep -af "<proceso>"` y `ls -ld <ruta>`.

## 3. Poda restic local (DEV)
```bash
export RESTIC_PASSWORD_FILE=/opt/hermes-agent-data/backup-keys/master-backup.key
restic -r /opt/hermes-agent-data/backups/restic-local unlock --remove-all
restic -r /opt/hermes-agent-data/backups/restic-local forget --keep-last 3 --group-by "" --prune
```
Pitfalls verificados:
- `--keep-daily N` agrupa por **host+paths**: snapshots viejos con rutas distintas forman su propio grupo y sobreviven. Para quedarse con los N últimos: `--keep-last N --group-by ""`.
- Un `restic copy` interrumpido deja un lock con el **PID del otro host**; `unlock` normal no lo quita, hace falta `unlock --remove-all` (comprobar antes que no haya backup corriendo).
- `prune` solo libera packs no referenciados: con dedupe alto, pasar de 22 a 3 snapshots puede liberar 5 G, no 12 G.

## 4. Mover el histórico a otro servidor (pull, no push)
PROD ya entra a DEV por SSH sin contraseña ⇒ DEV **no** necesita credenciales hacia PROD.
```bash
# en el servidor de respaldo (PROD)
scp root@DEV:/opt/hermes-agent-data/backup-keys/master-backup.key /root/.restic-dev.key
chmod 600 /root/.restic-dev.key
export RESTIC_PASSWORD_FILE=/root/.restic-dev.key
restic -r /opt/backups/restic-dev init
rsync -a --partial root@DEV:/opt/hermes-agent-data/backups/restic-local/ /opt/backups/restic-dev/
restic -r /opt/backups/restic-dev check      # debe decir "no errors were found"
```
`restic copy` por sftp va a ~0,9 MB/s; `rsync` va a 3-9 MB/s. Bootstrap inicial con rsync,
deltas nocturnos con `restic copy --from-repo sftp:...`.
**Nunca** rsync con `--delete` de forma recurrente sobre el repo replicado: espejaría la poda de
DEV y destruiría el histórico.

## 5. Guardrails del entorno Hermes
- Si un guard bloquea un borrado, respetar la aprobación requerida o detenerse. Nunca cambiar a `mv`, Python u otro mecanismo para eludirlo.
- Antes de retirar árboles, comprobar referencias vivas en `/proc/*/{cwd,exe,fd,maps}` y rutas de argumentos; repetir la comprobación inmediatamente antes del borrado. Excluir directorios compartidos de trabajo, entornos Python, historiales, DB y sesiones.
- Medir espacio liberable por bloques e inodos, no solo por tamaños: cachés UV pueden compartir hardlinks con entornos activos y cachés Snap con revisiones instaladas. Quitar un nombre no libera el bloque mientras existan otros enlaces.
- Para intermedios de render, probar primero compresión sin pérdida de una muestra. JPEGs de secuencias similares pueden reducirse mucho con `tar -I 'zstd -T2 -3 --long=27'`. Mantener un respaldo fuera de scratch; verificar `zstd -t`, comparar el archivo completo con los originales mediante `tar --compare`, y probar una restauración con SHA-256 antes de dar por seguro el retiro. Conservar fuentes y masters; comparar sus hashes y decodificar los masters completos tras la limpieza.
- Para imágenes Docker sin contenedor, exportar las referencias exactas, verificar el archivo y probar `docker image load` antes del retiro. Preservar las imágenes de TODOS los contenedores, incluidos los detenidos, y todos los volúmenes. Si un ID tiene varias etiquetas, quitar sus referencias explícitas sin `--force`. Registrar y verificar también los efectos parciales de un comando fallido.
- Informar ahorro NETO de `df` entre inicio y fin, descontando respaldos nuevos. No sumar estimaciones de capas compartidas de Docker ni liberar revisiones Snap si mantener una copia local ya comprimida anula el beneficio.
- Heredocs vía `ssh` remoto se rompen: `write_file` + `scp` + ejecutar el script.
- `pkill -f "<patrón>"` puede matar la propia shell si el patrón aparece en el comando: construir el patrón por concatenación.

## 6. Verificación obligatoria al cerrar
```bash
df -h /
restic -r <repo> snapshots --compact | tail -1
restic -r <repo> check --read-data-subset=5%
```
Mínimo 3 copias: local (3 diarios), off-site (histórico) y nube. Si el off-site muere junto al
servidor de producción, no es off-site.
