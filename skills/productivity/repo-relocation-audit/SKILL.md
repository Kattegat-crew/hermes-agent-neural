---
name: repo-relocation-audit
description: "Use when auditing a repo move or rename, read-only"
tags: [auditoria, audit, repo, migracion, read-only, systemd, crons]
category: devops
metadata:
  author: Ragnar
  version: "1.0.0"
---

# Auditoría de reubicación de un repositorio (read-only)

Usar cuando alguien **ya movió/renombró** un repo, proyecto o árbol de producción y pide validar que
quedó funcional ("migré el repo, audita tú mismo", "¿quedó todo subsanado?", "valida de nuevo").
El trabajo **no** es mover nada: es verificar en vivo a todos los consumidores y reportar, no
reparar, salvo autorización explícita.

Complementa (no sustituye) a `repo-rename` (ejecutar el rename) y `independent-infra-audit`
(auditoría genérica de pipeline). Detalle verificado del caso real y clases de hallazgo:
`references/repo-move-post-audit.md`.

## Regla de oro

- **Solo lectura.** Nada de editar, commitear, publicar, ni correr jobs reales. Los dry-runs,
  `git ls-remote`, `systemctl show`, `curl /health` y la simulación del resolver de rutas sí valen.
- **Un repo movido no rompe donde vive, rompe en quien lo referencia.** El hallazgo útil casi nunca
  está en el repo: está en units, wrappers, registros externos, skills y docs.
- Al terminar, confirmar que el audit no dejó rastro: `git status --porcelain` vacío y `HEAD` igual.
- Reportar en orden de radio de impacto: **(1)** funcional con evidencia viva → **(2)** rompe un cron
  → **(3)** degradado → **(4)** cableado muerto → **(5)** docs/higiene, y una línea de transparencia
  sobre los efectos secundarios que causó el propio audit.

## Checklist por consumidor

1. **Repo vivo:** `git status` limpio, `main == origin/main`, `git ls-remote --heads origin` desde
   host **y** contenedor; ninguna ruta histórica debe seguir existiendo (`ls -ld`) y no debe haber
   copia duplicada.
2. **Systemd:** `WorkingDirectory`, `EnvironmentFile`, `ExecStart` y todo flag con ruta (`--base …`)
   de cada unit del repo. Confirmar la config **efectiva**: `systemctl show <u> -p WorkingDirectory`
   (no basta con leer el archivo) + `systemctl list-timers`. Un unit viejo puede arreglarse **solo**
   si el repo volvió a su ruta original: verifica el efecto, no la mtime.
3. **Crons:** `jobs.json`, `executions.db` (`ORDER BY started_at DESC`, nunca por `id`) y los wrappers
   de `data/scripts/*.sh`. El `error` de las corridas fallidas suele traer la ruta muerta literal, y
   el último `status` puede ser engañoso tras un reinicio del scheduler (`unknown — owner exited`).
4. **Consumidores no-git:** registro de Orca (`~/.config/orca/profiles/*/orca-data.json`), bind mounts
   (`docker inspect` de cada contenedor), nginx/NPM, árbol de OpenCode (`~/.config/opencode/`:
   symlinks, skills, `SKILLS_INDEX.md`).
5. **Skills y conocimiento:** `grep -rn <ruta-vieja>` en `/opt/data/skills/`,
   `/opt/data/profiles/*/skills/` y el árbol de OpenCode. Clasificar **operativas** (comandos que un
   futuro agente ejecuta tal cual) vs **históricas** (informes fechados): solo las primeras se
   corrigen, y decirlo así evita una lista inmanejable.
6. **Claims dentro del repo:** README/CHANGELOG/`docs/planes` quedan autocontradictorios tras un
   segundo movimiento ("la ruta vieja X ya no existe" con X = la ruta actual). Contrastar el texto
   con `git grep` de la ruta real.
7. **Higiene:** `package.json:name`, encabezado `.atl/skill-registry.md`, `.bak-*` **rastreados**
   (`git ls-files | grep -c '\.bak'`) y drift de dueño (`find <repo> -uid 0 ! -name '*.pyc'`). El
   drift reaparece cada vez que un proceso root importa o escribe en el repo.
8. **Conocimiento del operador:** `/opt/vps-brain/HISTORIAL_Y_CONTEXTO_VPS.md` y `/opt/vault/`
   (leer antes de acusar: `REPOS-ARQUITECTURA.md` prohíbe por diseño las tablas estáticas y manda
   descubrimiento en vivo — no es un hueco).

## Probar sin efectos secundarios

Resolver de rutas de un wrapper, sin ejecutarlo (read-only, el chequeo más informativo):

```bash
for t in planning/<x>/cron_<job>.py; do
  for c in /host/root/<repo> /root/<repo> /opt/data/repos/<repo> /root/hermes-agent-legacy-docker/data/repos/<repo>; do
    [ -r "$c/$t" ] && echo "$t -> $c" && break; done; done
```

Dentro del contenedor gateway `id -u` ya es 10000 (el uid del cron), así que los wrappers se corren
directamente; `setpriv --reuid=10000` aborta ahí (`setgroups failed: Operation not permitted`) y de
todas formas no cambia el mount namespace. Si el check exige el namespace del contenedor usar
`docker exec -u 10000`, si exige el árbol del host usar `ssh dev`, y si no hay forma local, reportar
**BLOCKED** en vez de un verde parcial.

## Triage de tests: artefacto de entorno vs regresión

Antes de reportar una regresión, reclasifica **cada** fallo re-corriendo el subconjunto con el uid y
el `HOME` operativos:

- `fs.protected_regular=2` + un temporal de `/tmp` con ruta fija perteneciente al **otro** uid ⇒
  `PermissionError` masivo, incluso para root. Diagnóstico: `ls -l <temporal>` + `sysctl
  fs.protected_regular`; corre ese archivo como el dueño del temporal (o bórralo).
- Tests que usan `Path.home()` cambian de resultado entre `HOME=/root` y `HOME=/opt/data`.
- El número de tests del README suele estar viejo: cuenta los recolectados, no los citados.

## Validación en rondas

El Admin arregla por lotes y vuelve a pedir "valida de nuevo". En cada ronda **vuelve a correr toda
la checklist**, no solo los pendientes: siempre queda algo parcial y es donde se esconden las
regresiones. Un hallazgo que ya no aplica se **retracta explícitamente**; una corrección que solo se
puede confirmar en el próximo tick del cron se dice así ("verificable mañana 06:00"), sin implicar
cobertura E2E.

## Pitfalls

- **Scripts del pipeline sin `argparse`: `--help` ejecuta el trabajo real.** Un `cron_harvest.py
  --help` lanzó un harvest real (murió en la primera pieza por PATH, sin escribir). Antes de probar
  un script del repo, lee su `main()`/`argparse`; para sintaxis usa `py_compile` con
  `PYTHONPYCACHEPREFIX=/tmp/audit-pycache`, y deja la corrida real al cron.
- **No declares un hueco de documentación sin leer el archivo.** Reportar un doc como "faltante" por
  no listar el repo fue un falso hallazgo (el doc manda descubrimiento dinámico por diseño).
  Retractarse en la ronda siguiente cuesta credibilidad.
- **`grep` inline con comillas anidadas se bloquea** como payload inejecutable: usa `search_files` o
  escribe el script a un archivo y córrelo.
- **La “evidencia viva” mínima** de un fix de rutas es un run real escribiendo dentro del árbol del
  repo (dashboard/JSONL commiteado), no un resolver que "resuelve".
- **No confundir un temporal de test con un archivo del repo** al reportar drift de dueño: los `.pyc`
  y `/tmp/*` son artefactos, los archivos rastreados no.
