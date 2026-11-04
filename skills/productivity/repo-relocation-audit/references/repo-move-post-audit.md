# Caso verificado: mover `marketing-campaign-generator` a `/root/<repo>` (DEV, 2026-09-11)

Petición del Admin: "migré el repositorio a la carpeta root; audita tú mismo que quedó funcional.
Solo audita, si encuentras inconsistencias repórtalas y yo las corrijo". Tres rondas de validación.
Todo lo de abajo se observó en vivo.

## Checklist por consumidor — qué encontró cada punto

| Consumidor | Cómo se verificó | Defecto real encontrado |
|---|---|---|
| Git | `git status`, `git log`, `git ls-remote --heads origin` (host + contenedor) | ninguno: limpio, `main == origin/main` |
| systemd | `systemctl show <u> -p WorkingDirectory -p ExecStart` + `list-timers` | `cleanup-previews.service --base <repo>/output` mientras el engine escribe en `<repo>/assets` (`DEFAULT_BASE` de `scripts/output_layout.py`) → el timer corría sin limpiar nada |
| crons | `jobs.json`, `executions.db`, wrappers `data/scripts/*.sh` | el render de dashboards apuntaba al árbol muerto con `open(dash,'w')` sin `makedirs` → `FileNotFoundError` en la primera marca y, como el publish a wiki va después en el mismo bucle, se perdían dashboard **y** wiki de ambas marcas |
| registros no-git | `~/.config/orca/profiles/*/orca-data.json`, `docker inspect`, nginx, `~/.config/opencode/` | Orca registrado como `video-ai-generator` → `/root/video-ai-generator` (inexistente) y el repo nuevo sin registrar |
| skills | `grep -rn <ruta-vieja>` en `/opt/data/skills/`, `profiles/*/skills/`, OpenCode | operativas: `docker -v /root/video-ai-generator:/repo`, `cd /root/video-ai-generator && source .env`, `/root/video-ai-generator/.env`, y una regla que afirmaba que el repo DEBE vivir en `data/repos` |
| docs del repo | texto vs `git grep` de la ruta viva | "la ruta vieja `/root/<repo>` ya no existe" cuando esa era la ruta **actual** |
| higiene | `package.json:name`, `.atl/skill-registry.md`, `git ls-files | grep -c '\.bak'`, `find <repo> -uid 0` | nombre viejo `video-ai-generator`, 6 `.bak-*` rastreados, 52 entradas `root:root` |

## Comandos reutilizables

```bash
# qué candidato elegiría cada wrapper (read-only, sin ejecutar)
for t in planning/calendario-sep2026/cron_publish_due.py; do
  for c in /host/root/<repo> /root/<repo> /opt/data/repos/<repo> /root/hermes-agent-legacy-docker/data/repos/<repo>; do
    [ -r "$c/$t" ] && echo "$t -> $c" && break; done; done

# historial de cron con el stdout embebido (la ruta muerta aparece literal en el error)
sqlite3 /opt/data/cron/executions.db \
 "select started_at,status,substr(coalesce(error,''),1,200) from executions where job_id='<id>' order by started_at desc limit 5"

# ningún contenedor debe montar el árbol movido
for c in $(docker ps -q); do docker inspect -f '{{.Name}} {{range .Mounts}}{{.Source}} {{end}}' $c; done | grep <repo> || echo none

# drift de dueño
find <repo> -uid 0 -not -path './.git/*' ! -name '*.pyc' -printf '%p\n'
```

## Trampa de tests (lo que más tiempo costó)

Dos artefactos de entorno, los dos fáciles de confundir con regresiones:

1. `fs.protected_regular=2` + `/tmp/test_verify.html` dejado por la corrida con el **otro** uid → 15
   `PermissionError` en `test_review_page.py` **incluso como root**. Corriendo ese archivo como el
   dueño del temporal: 36/36 verdes. Borrar el temporal lo resuelve para cualquier uid.
2. `test_security_credentials.py` usa `Path.home()`: pasa con `HOME=/root` (ahí está
   `/root/.config/akari-video/credentials.env`, modo 600) y falla con `HOME=/opt/data`.

Totales medidos: 663 tests recolectados (el README documentaba 605).

## Cómo se ve una prueba de éxito real

Un fix de rutas solo queda "verificado" cuando una corrida real escribe **dentro del árbol del
repo**: tras la corrección, la corrida de 18:04 escribió `content-intel/data/{golden,lucky}-dashboard.html`
+ `posts.jsonl` en el repo y quedaron commiteados. Un wrapper que "resuelve" no es evidencia. Si el
cron aún no ha corrido desde el fix, se dice: "verificable en la próxima pasada (mañana 06:00)".

## Ritmo real de las rondas

Ronda 1 → 2 de 5 grupos cerrados. Ronda 2 → Orca, scripts del host, skills de perfiles, árbol de
OpenCode, docs del repo e higiene cerrados; el trabajo en curso seguía sin commitear. Ronda 3 → el WIP
commiteado y pusheado; el resto igual. Conclusión operativa: **re-corre la checklist completa cada
ronda** — tarda minutos porque los comandos ya están escritos, y es donde aparecen las regresiones.
