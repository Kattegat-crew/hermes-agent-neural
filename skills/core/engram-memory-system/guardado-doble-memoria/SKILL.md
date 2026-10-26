---
name: guardado-doble-memoria
description: "Use when saving to Engram and Hermes memory on request"
tags: [memoria, engram, guardado, persistencia, sesion, cron, hermes, dedup]
author: Ragnar
version: "1.0"
created: 2026-08-21
category: engram-memory-system
metadata:
  hermes:
    tags: [memoria, engram, guardado, persistencia]
    related_skills: [engram-memory-system, hermes-memory-maintenance, mapa-de-carpetas]
---

# Guardado Doble de Memoria (Engram + Hermes)

## When to Use

Dispara cuando Jonathan pide "_guarda_", "_documenta_", "_guarda y documenta_" o al
cierre de una sesión/hito de trabajo: guardar lo sucedido en Engram MCP y en la
memoria nativa de Hermes (doble persistencia).

## Cuándo se activa (triggers)

- El Admin (Jonathan) dice: **"guarda"**, **"documenta"**, **"guarda y documenta"**, **"guarda esto"**, etc.
- **Al terminar una sesión de trabajo** (se cierra tarea, se despide, cambio de tema mayor, o el Admin indica que cierra).
- Al finalizar hitos importantes: decisiones, bugfix, configs, despliegues, skills creadas, contratos, reuniones.

**NO esperar a que lo pidan:** si en la sesión hubo trabajo significativo, hacer el doble guardado ANTES de dar el cierre.

## Pasos (orden exacto)

### Paso 1 — Engram MCP (memoria compartida del VPS)

1. Buscar si ya existe memoria sobre el tema (evitar duplicados):
   ```
   mcp__engram__mem_search(all_projects=True, query="<tema>", match_mode="any", limit=5)
   ```
   **SIEMPRE** `all_projects=True` (accede a OpenCode/Agy/Antigravity/neuralwebsite/vault).
2. (Recomendado) Obtener topic_key estable para que actualice la observación en vez de duplicar: `mcp__engram__mem_suggest_topic_key(title="<Título>", type="architecture|decision|…")`. Si el tema ya tiene observación anterior, reutilizar el topic_key.
3. Guardar con `mcp__engram__mem_save`:
   - `title`: corto y buscable (ej. "Integración Orca↔Bots: Code-Delegate").
   - `content`: formato `**What** / **Why** / **Where** / **Learned**`.
   - `type`: architecture | decision | bugfix | config | discovery | pattern | learning.
   - `topic_key`: el estable (si corresponde).
   - `project`: el proyecto real cuando se sabe (ej. `hermes`, `golden-game-landing`); si Engram sugiere otro nombre con más memorias, valorar usarlo.
4. Verificar: `mem_search(all_projects=True, query="<tema>")` → debe aparecer la observación nueva/actualizada.

### Paso 2 — Memoria Hermes nativa (la de cada sesión)

- Usar la herramienta `memory`:
  - `target="user"` para preferencias/personalidad del Admin.
  - `target="memory"` para notas del entorno, convenciones, lecciones.
- Formato: hechos declarativos, compactos; los procedimientos van en skills, no en memoria.
- Si `memory` falla por lock/permisos → aplicar skill `hermes-memory-maintenance` (chown hermes:hermes + chmod 600 + quitar *.lock vía `docker exec hermes-agent`, NO sudo).

### Paso 3 (complementario si aplica) — Brain Wiki / docs

- Si una decisión merece canon: crear/actualizar concepto en `brain/concepts/<tema>.md`, entidad en `brain/entities/`, y actualizar `brain/index.md` y `brain/log.md`.
- Antes de escribir CUALQUIER archivo: skill `mapa-de-carpetas` (SCAN→MAP→RULES→VERIFY).
- Verificación post-escritura: read-back de la ruta.

## Ejemplo real (21/08/2026)

- Marcado en USER.md: "Guarda SIEMPRE en doble memoria al terminar sesión o cuando diga 'guarda y documenta'".

## Variante Cron "guardado diario automático"

Si el doble guardado corre como **cron automático** (job `guardar-diario-memoria`,
criptor de sesiones `daily_session_report.py` que vuelca la jornada al prompt):

- El cron corre en **sesión limpia**, sin el contexto de la conversación — por eso
  necesita un `script` de recolección que le inyecte "lo que se hizo hoy"
  (consulta `state.db`, tabla `sessions` + `messages`).
- **OBLIGATORIO incluir el toolset `memory` en `enabled_toolsets`** del job; si solo
  pones `terminal/file/code`, la herramienta nativa `memory` NO carga y el cron
  no puede escribir en MEMORY.md (pasó el 24/08: reportó "memory no disponible").
  La piel de memory en ese control no es un fallo de engine — es config del job.
- Entregar en silencio: `deliver='local'` (no notifica a ningún canal).
- **Verificar ANTES de escribir**: (a) que la tool `memory` esté presente en el run (si no aparece en el toolset, el paso nativo es inejecutable → anotarlo en el resumen y seguir con Engram); (b) que `/opt/data/memories/MEMORY.md` sea **legible y escribible** por `hermes` (uid 10000). Si está `root:root` (lo dejan así las escrituras del runtime root del Desktop), reparar primero con `docker exec hermes-agent chown hermes:hermes /opt/data/memories/MEMORY.md` + `chmod 600` (ver skill `hermes-memory-maintenance`). Sin ese chown el cron reporta "memoria no disponible" y pierde la capa nativa (pasó el 24/08 y otra vez el 11/09).
- **Trazabilidad en el resumen:** Engram devuelve el `id` de cada observación (`#640`, `#641`…); anotar el rango de ids del día en la entrada del `brain/log.md` es la forma más rápida de que otro agente encuentre lo guardado sin re-buscar.
- **CRÍTICO EN PROD (24/08):** el CLI `hermes` del host es un wrapper `docker exec`
  que NO pasa `HERMES_HOME` → `hermes cron create` desde el host escribe el job en
  DEFAULT aunque hagas `cd` al perfil. Método correcto para crons por perfil:
  `docker exec -e HERMES_HOME=/opt/data/profiles/<p> hermes-agent hermes cron ...`
  (dentro del contenedor `hermes-agent`, ruta de prod `/opt/data` symlink a
  `/opt/hermes/data`).
- **El run de prueba tarda 2-3 min** (incluye LLM): lanzar con nohup en background
  del VPS (`nohup docker exec -e HERMES_HOME=... hermes-agent hermes cron run <id>
  </dev/null >/tmp/x.log 2>&1 &`) y verificar `last_status` en
  `<home>/cron/jobs.json`; el foreground SSH da timeout pero el job sigue.
- **HTTP 429** en varios runs paralelos = rate limit transitorio del proveedor;
  reintentar secuencial.
- El cron debe `mem_search(all_projects=True)` antes de cada `mem_save` y usar
  `mem_suggest_topic_key` para actualizar en vez de duplicar.

## Variante AISTLADO (agente de producción por cliente)

Para un agente de prod que corre **aislado** (su propio contenedor/perfil, memoria
propia, Engram propio, cero compartición) el cron de guardado es el MISMO mecanismo
pero **con 3 cambios obligatorios** — de lo contrario rompe el aislamiento:

1. **`HERMES_DB_PATH`** apunta a SU `state.db` (el `daily_session_report.py` ya lo
   honra vía env). El script NUNCA debe resolver contra la DB central del host.
2. **PROHIBIDO `all_projects=True`** en `mem_search`/`mem_save`. En la variante
   compartida se usa para deduplicar a través de toda la base; en un cliente
   aislado hay que buscar y guardar SOLO en su propio proyecto/topic. El prompt
   del cron aislado NO lleva esa bandera. Este es el punto de seguridad crítico.
3. **`deliver`** a su propio canal (o `local`), nunca al de Ragnar ni al host.
   Lo que guarde (observaciones Engram, MEMORY.md) viven en su home, no en la central.

**Regla de oro:** en el mismo host, roshi y Ragnar comparten Engram y por tanto el
cron COMPLETO (con `all_projects`); un perfil/cliente aislado recibe la variante
sin compartición. No existe "mitad compartido": o comparten toda la base o no se
cruza nada. En Engram-compartida usa el cron original sin `HERMES_DB_PATH`.

## Pitfalls

- **Varios perfiles comparten Engram y DUPLICAN el guardado (13-sep-2026):** en este host `default`, `roshi` y `vigia` tienen cada uno su job `guardar-diario-memoria` a las 23:00 y escriben al MISMO Engram. Si un perfil (vigia) fija `HERMES_DB_PATH=/opt/data/state.db` — la DB del perfil *default* — re-guarda la jornada de Ragnar: el 13-sep todo quedó duplicado (#663–666 de vigia vs #667–669 del default, tema EAN triplicado con los de roshi) y la jornada propia de vigia sin guardar. Regla: cada job debe apuntar a la DB de SU perfil; si el store es compartido, basta con UN job. Un job con store compartido y fuente implícita duplica en silencio: ningún run individual lo reporta como error. Caso completo en `brain/ops/auditoria-harness-2026-09-13.md` (addendum D7).
- **No duplicar:** usar topic_key y buscar antes. Engram actualiza la observación con topic_key y devuelve `id` único.
- **`all_projects=True` OBLIGATORIO** en `mem_search` — sin él solo busca en el proyecto actual y parece que "no hay nada".
- **Memoria Hermes rota** (root:root o locks): aplicar `hermes-memory-maintenance` ANTES de reintentar; nunca reescribir a mano (el tool valida hash on-disk).
- **No guardar** datos triviales, log de tareas completadas ni SHAs/PRs que quedan obsoletos en 7 días — solo hechos durables y preferencias.
- Si `memory` add falla por límite de chars → UNA llamada batch (`operations`) que consolide y agregue.
- **`memory` con `action=replace` sobrescribe la ENTRADA COMPLETA**, no solo el fragmento de `old_text`: para retocar una frase hay que reescribir la entrada entera en `new_text` (el 11/09 truncó 3 entradas de roshi y hubo que restaurarlas en un segundo batch). Tras un batch de replaces, VERIFICAR leyendo el store (`<perfil>/memories/MEMORY.md`).
- **El CLI de engram no tiene `update` ni `judge`** (12/09): para retocar una observación propia hay que **re-guardarla con el MISMO `topic_key`** (upsert: sube `revision_count` y conserva el id; el contenido anterior se pierde, así que se reescribe completo + lo nuevo). `engram conflicts` es de solo lectura (`list|show|stats|scan|deferred`): `mem_judge` solo existe por el servidor MCP stdio.
- **Verificar conflictos contra los ids propios, no por el resumen**: `conflicts stats` filtra por UN proyecto y engaña (dice `pending: 28` de `data` cuando la base tiene 123 pendientes en 10 proyectos). Consulta directa: `SELECT * FROM memory_relations WHERE judgment_status='pending'` y compara `source_id`/`target_id` (son el `sync_id` `obs-…`) contra los `sync_id` de las observaciones recién creadas. Si el save no devolvió `judgment_required`, no hay nada que juzgar.
- **Mirar las observaciones del MISMO día de otros agentes antes de guardar**: `SELECT id,title,type,project,topic_key FROM observations WHERE id >= <n>` en `engram.db`. El 12/09 ya existía una observación de otra sesión sobre el mismo `guion_session.py` (bloqueos del E2E): en vez de duplicar, se metió el **cross-ref dentro de la observación propia** (upsert) apuntando a la ajena.
- **En la sesión del cron el MCP de engram no está expuesto**: equivalencia CLI con la DB compartida — `ENGRAM_DATA_DIR=/opt/data/home/.engram engram search <q>` (~mem_search) y `engram save <title> <content> --type T --project P --topic K` (~mem_save). Verificar después con `engram search`; los conflictos ajenos pendientes no exigen `mem_judge` si el save no devolvió `judgment_required`.
- **`messages` usa `timestamp` REAL, no `created_at` (24-oct-2026, roshi):** el script de recolección debe leer `messages.timestamp` (numérico) y filtrar por epoch; `created_at` no existe en esa tabla y aborta el dump. Además cada perfil tiene su propio `profiles/<perfil>/state.db`: si el `daily_session_report.py` dice "sin sesiones", NO significa que el host no tuvo trabajo — `/opt/hermes-agent-data/state.db` (perfil default) puede tener la jornada de otro agente. Nunca guardes desde la DB ajena: verifica `profiles/<perfil>/state.db` antes de concluir y antes de duplicar.
- **`sessions.started_at` / `last_activity_at` son EPOCH REAL, no texto (28-sep-2026, vigia):** filtrar la jornada con `WHERE last_activity_at >= '2026-09-28'` devuelve **0 sesiones en falso** (en SQLite todo número ordena antes que cualquier texto) y el guardado concluiría "no hubo jornada" con la jornada existiendo. Convertir el rango a epoch con `zoneinfo.ZoneInfo("America/Bogota")` y comparar numérico. En `cron/executions.db` en cambio `started_at` SÍ es TEXT ISO (`2026-09-28T23:00:48-05:00`) — no mezclar formatos entre DBs. En el host no hay CLI `sqlite3`: abrir con python (`sqlite3.connect("file:<db>?mode=ro", uri=True)`) y separar jornada real de runs del ticker con `source NOT IN ('cron')`.

## Referencias

- Skill `engram-memory-system`.
- Skill `hermes-memory-maintenance` (reparar store nativo).
- Skill `mapa-de-carpetas` (dónde escribo archivos/docs).