# Caso trabajado — auditoría del calendario bingo-sep2026 (2026-09-10)

Auditoría independiente read-only sobre el pipeline de publicación automática (repo `marketing-campaign-generator`, crons `calendario-*`). Veredicto: **APROBADO CON HALLAZGOS MENORES** (11/11 checks con evidencia, 2 hallazgos medios + 2 menores).

## Checks que salieron PASS (y cómo se probó)

| Check | Evidencia usada |
|---|---|
| Crons existen/habilitados | `hermes cron list` (`[active]`) + `enabled: true`, `last_status`, `last_run_at`, `next_run_at` leídos de `/root/hermes-agent-legacy-docker/data/cron/jobs.json` |
| `cron/output` de uid 10000 | `stat -c '%U:%G %A'` + `setpriv … bash -c '[ -w . ]'` (host **y** contenedor) |
| Repo limpio y sincronizado | `git status --porcelain` vacío; `## main...origin/main`; `rev-parse HEAD origin/main` iguales (`55b226f`); `fetch` y `ls-remote` rc=0 como uid 10000 |
| 64 filas JSON válidas | script Python que parsea y cuenta estados (64/64, 64 ids únicos) |
| 5 scripts compilan | `python3 -m py_compile` con `PYTHONPYCACHEPREFIX=/tmp/audit-pycache` |
| E2E dry-run | `publish.py --id <ID> --dry-run` → JSON correcto; id inexistente → rc=2 |
| Wrapper silencioso | `calendario_publish_due.sh` → rc=0, **stdout 0 bytes**, stderr vacío, host y `docker exec -u 10000 -e HOME=/opt/data` |
| Composio read-only | `composio execute INSTAGRAM_GET_USER_INFO … --account instagram_demal-molala` → `successful:true` (`goldengame_casinos`, 14 media) |
| Portal de assets | `curl -sI` → HTTP 200 ×3 (`golden-cover.png`, `golden-reel-pacho.mp4`, `lucky-reel-chiqui.mp4`) |
| Gate de aprobación | `cron_publish_due.py:69-70` filtra `estado=='aprobado'`; `:79-83` anti-dup por `media_ids`; `publish.py:146-147` `SystemExit` si `estado!='aprobado'`; único importador del publicador = ese cron |

## Hallazgos

**H1 (medio) · dual ticker.** El backend root del Desktop (`hermes serve --isolated`, `HERMES_HOME=/root/hermes-agent-legacy-docker/data`, `HERMES_DESKTOP=1`) seguía tickeando el mismo `jobs.json` que el gateway (uid 10000). Prueba: artefactos `root:root` de hoy — `output/ff3e1c2b759f/…06-02-40.md` (métricas), `output/fee5dcf7691b/…07-31-11.md` (paquete 7:30), `output/794be6c2336b/…09-34-16.md` (publicación horaria) + los vigía cada 10 min. Si el ticker root gana un turno de publicación escribiría `calendario.jsonl`/XLSX/dashboards como `root:root` (ya había **58 ficheros root** en el repo).

**H2 (medio) · drift de estado.** `golden-sep09-story-1` y `lucky-sep09-story-1` con `estado: aprobado` **y** `media_ids` presentes, ya registradas y cosechadas en `content-intel/data/posts.jsonl`. El XLSX de Drive también decía `aprobado` ⇒ el sync (`Estado` es campo EDITABLE) lo revierte cada tick. El auto-sanado (`cron_publish_due.py:79-83`) solo actúa dentro de la ventana `0 <= now - slot <= 2h`, así que un slot pasado nunca se corrige; los informes que leen el JSONL cuentan mal.

**H3 (menor) · rutas del checklist inexactas.** El checklist nombraba `/root/marketing-campaign-generator` (no existe) y `/opt/data/...`: el repo real es `/root/hermes-agent-legacy-docker/data/repos/marketing-campaign-generator` (host) = `/opt/data/repos/…` (contenedor); el `/opt/data` del host es un árbol obsoleto casi vacío.

**H4 (menor) · esquema inconsistente.** `media_ids` como **lista** `["ig_id","fb_id"]` en las 2 filas del 08-sep vs **dict** `{"instagram":…,"facebook":…}` que escribe el código actual. Además `--dry-run` retorna antes del gate de aprobación (`publish.py:144-145`): un dry-run verde no prueba que la fila sea publicable.

## Higiene aplicada (efectos laterales = cero)

`py_compile` fuera del repo (`PYTHONPYCACHEPREFIX`), temporales en `/tmp`, y el wrapper (que commitea/pushea) se ejecutó solo tras probar con `sync_from_drive.py --dry-run` → `0 cambios del humano` y `HEAD == origin/main`. Al cierre: `git status --porcelain` vacío, HEAD idéntico, sin publicar, sin mensajes, sin tocar Drive.

## Reparaciones recomendadas al dueño

1. Aplicar el stand-down real del ticker root (o deshabilitarlo para ese `HERMES_HOME`) + `chown -R 10000:10000` del repo.
2. Corregir el `estado` de las 2 filas + regenerar el XLSX y subirlo a **ambas** copias de Drive (si no, el sync de la mañana lo revierte).
3. Unificar `media_ids` a dict (migrar las filas viejas).
