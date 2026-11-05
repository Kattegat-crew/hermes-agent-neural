---
name: hermes-cron-health
description: Use when checking cron job health, deliveries or failures on DEV/PROD Hermes ("revisa cómo va X", streaks, matutino, envíos de clientes) — esquema real de executions.db y jobs.json, verificado 29-oct-2026.
---

# Diagnóstico de salud de crons Hermes (PROD/DEV)

Verificado en vivo 29-oct (auditoría de envíos Golden/Lucky). Los crons viven en
el contenedor `hermes-agent`: `/opt/data/cron/executions.db` (SQLite) y
`/opt/data/cron/jobs.json`.

## Consulta estándar de ejecuciones

```python
import sqlite3
db = sqlite3.connect('/opt/data/cron/executions.db')
db.row_factory = sqlite3.Row
q = "SELECT job_id,status,started_at,error,delivery_outcome FROM executions WHERE job_id IN (%s) AND started_at >= 'YYYY-MM-DD' ORDER BY started_at DESC LIMIT 100"
```

- **`started_at` es string ISO** (`2026-10-29T10:18:15-05:00`), NO epoch — filtra
  por fecha `'2026-10-27'` en SQL, no con `time.time()`.
- `job_id` completo en jobs.json; en la tabla usar prefijo/IN con ids completos.
- Pasar el script por `docker exec -i hermes-agent python3 -` (stdin). Los
  heredoc anidados por ssh rompen el parsing.
- Tablas: `executions`, `cron_incidents` (columna status=resolved abre/cierra).

## Semántica de `delivery_outcome`

- `delivered` = entregado al canal destino (evidencia de envío OK).
- `suppressed` = corrida OK sin salida que entregar — **silencio sano**, no fallo
  (típico en watchers intervalo: avisos→Bob cada 5 min, repartidor cada minuto).
- Jobs `no_agent: true` (scripts .sh) pueden NO registrar filas en executions:
  verifica por `jobs.json` → `last_run_at`, `last_status` ("ok"),
  `failure_streak`, `next_run_at`, `last_dispatch.lateness_seconds`, `deliver`.

## Topología multi-perfil de jobs.json (verificado 03-nov-2026)

- `/opt/data/cron/jobs.json` SOLO contiene los jobs del perfil `default`.
- Cada perfil de cliente tiene su propio store: `/opt/data/profiles/<name>/cron/jobs.json`
  (jacqueline, nancy, gerardo, ivan, oscar, ...).
- Auditoría global ("cuántos jobs hay", "hay alguno enabled", limpieza de zombis):
  SIEMPRE glob de ambos roots, nunca solo el del default — un conteo solo-default
  subestima el inventario y puede aprobar un borrado con alcance mal reportado.
  Ej. real: 41 jobs reportados como "internos" eran en realidad cross-profile
  (default 16, jacqueline 16, nancy 4, gerardo 2, ivan 2, oscar 1).

```python
import json, glob
files = ['/opt/data/cron/jobs.json'] + glob.glob('/opt/data/profiles/*/cron/jobs.json')
# jobs = d if isinstance(d,list) else d.get('jobs', d); if dict -> list(values())
```

## Hashes y manifiestos de scripts destructivos (patrón self-fingerprint)

- Un sha256 registrado de un script NO es confiable a futuro: en 3-min-2026 un
  hash "FINAL" quedó stale a los 3 minutos porque otro agente parchó el archivo.
- Patrón duradero: el script se auto-firma DENTRO de su propio manifiesto
  (`huella_script()` → `manifest["script"] = {path, bytes, sha256}` calculado con
  `os.path.abspath(__file__)` al correr). Así el manifiesto siempre documenta el
  binario exacto que ejecutó, sin registro externo que pueda quedar viejo.
- Al recibir el acuse de otro agente sobre un script destructivo: verificar
  counts/ids contra los stores vivos (y cross-perfil), no contra el manifiesto
  del reportador; confirmar también `apply:false` y que `--apply` sea opt-in.
- Vigilar huérfanos: un hilo saltado como "dinámico de job X" puede pertenecer a
  un job que YA NO EXISTE en ningún store (protección por patrón de nombre) —
  queda como basura post-limpieza; registrar en Fase 4 como huérfano.

## Hilos de foro Discord: huérfanos vs objetivos de entrega (webhook_id ≠ hilo referenciado)

Verificado 03-nov-2026 (limpieza Fase 0, Discord API + grep en DEV y PROD).

- **`webhook_id` presente en un mensaje NO significa que el hilo sea objetivo de
  entrega.** El webhook `1564305619228295291` de `crons-dev` (foro, type 15) crea
  un hilo NUEVO por corrida cuando el llamador hace `curl -X POST "$WEBHOOK_URL"`
  SIN `?thread_id=` — bloquear el borrado por la sola presencia de mensajes de
  webhook deja esos hilos en Fase 4 para siempre.
- Criterio correcto para clasificar un hilo de foro:
  1. ¿Alguna config referencia su id (`?thread_id=<id>`, `chat_id`, .env, prompt
     del job, scripts, ActivePieces) en TODOS los hosts y stores? Grep global;
     cero hits ⇒ hilo huérfano, borrable sin romper entrega.
  2. ¿Lo crea un job vivo con nombre dinámico? ⇒ no borrar: renacería en la
     siguiente corrida; aplicar el fix en el PROMPT del job (añadir
     `?thread_id=`, con separador condicional `?`/`&`), no "arreglar el webhook".
  3. ¿Hilo fijo con `?thread_id=` en config (ej. informe-diario-exacto,
     VIGIA_DISCORD_THREAD_ID, crontab root)? ⇒ NUNCA borrar: el webhook
     publicaría contra un hilo inexistente y falla en silencio.
- Receta de verificación: `GET /channels/{foro}/threads/active` +
  `/threads/archived/public` con el token del bot (header `Authorization: Bot`,
  `User-Agent` de bot); leer los 1ers mensajes de cada hilo para extraer
  `webhook_id`/`author.username`; correlacionar contra el grep de configs.
  `GET /guilds/{id}/webhooks` y `/channels/{id}/webhooks` dan 403 sin
  MANAGE_WEBHOOKS — no es bloqueante para la clasificación.
- Señales de hilo huérfano-by-webhook: 1 mensaje por hilo, nombres progresivos
  entre corridas (vigia-report → vigia-reports → informe-vigia-28-oct), fechas
  que siguen la cadencia del cron, y username distinto al default del webhook
  (el llamador lo sobreescribe por POST).

## Reconfigurar entregas a Discord (multi-destino, canales de marca, uploads)

- **`--deliver`/`--failure-deliver` aceptan lista coma-separada** (`discord:<id>,discord:<id>`, o `whatsapp,discord:<id>`): la misma salida va a TODOS los destinos. Para añadir una copia a Discord a un job de cliente, CONCATENA el destino actual delante — nunca reewire el job del cliente a solo-Discord (le corta el WhatsApp).
- Validar un rewiring con un job desechable, nunca esperando la corrida real: crear `hermes cron create '0 4 1 1 *' --script <echo.sh> --no-agent --repeat 1 --deliver '<lista>'` → `hermes cron run <id>` → leer ambos hilos por API de Discord (evidencia con message ids) → `hermes cron delete <id>` + borrar los mensajes de prueba. Y `--failure-deliver '<lista>'` para que los avisos de fallo no sigan al WhatsApp personal.
- Un bot SOLO puede EDITAR sus propios mensajes: PATCH sobre un mensaje publicado por OTRO bot (token distinto) da 403 Forbidden aunque tenga permisos de canal. Para limpiar mensajes ajenos: DELETE (requiere MANAGE_MESSAGES) o dejarlos; no intentar edición cross-bot.
- Publicar un archivo (PNG/informe) en un hilo: POST multipart `/channels/{id}/messages` con `files[]` + `payload_json` (header `Authorization: Bot`, User-Agent de bot). Probar la función contra el hilo REAL vía `docker exec` ANTES de cablear el cron — el upload falla distinto al POST de texto y el verde del texto no lo cubre.
- En scripts que TAMBIÉN entregan al cliente: envolver el post de Discord en try/except con log — un fallo de Discord nunca debe abortar el envío al cliente (son dos entregables independientes).
- Antes de declarar huérfano/roto un cron con `deliver=local`, clasificar leyendo su script y prompt: (a) el script se auto-publica en Discord por su cuenta → local por diseño; (b) el prompt dice explícitamente "sin publicar" o es mantenimiento → silencio deliberado; (c) el prompt dice "avisa en Discord" pero deliver=local → incoherencia REAL, el job nunca puede notificar — fix: editar deliver a un hilo. La clase entera NO es "rota"; solo el caso (c).

## Falsos verdes estructurales en reportes de salud (verificado 03-nov-2026)

- Si un script/monitor resume "Crons: sin errores en las últimas 24 h",
  verificar que lea las claves REALES de jobs.json: `last_run_at` (ISO) y
  `last_status` ∈ {ok, delivered, success}. NO existe `last_run` en ninguna job.
- Patrón de falso verde: `ts = j.get("last_run") or 0` + `if ts < corte:
  continue` + `if not fallidos: "sin errores"` — con la clave equivocada TODAS
  las jobs se saltan, `fallidos` queda siempre vacío y la línea de salud se
  imprime pase lo que pase (96/96 jobs sin clave en el caso real, informe
  "sin errores" mientras el estado real era incognoscible). Verificar el patrón
  con conteo global: cuántas jobs tienen la clave que el código lee.
- El código muerto delata el bug: un `if <cond> < corte: append(sin_correr)`
  DESPUÉS de un `continue` por la misma condición nunca ejecuta — señalarlo.
- **`last_status` de un job de intervalo es un SNAPSHOT, no una ventana (verificado
  03-nov-2026)**: el `escalation-watcher` corre cada 2 min; un dry-run del bloque
  Crons capturó `default:escalation-watcher=error` y dos minutos después el mismo
  job estaba en `last_status=ok` con `failure_streak=0`. Un único snapshot de un
  job de alta frecuencia puede mostrar un error transitorio que ya se autoreparó
  (o al revés). Antes de tratar un "1 error" del bloque Crons como persistente:
  leer `jobs.json` de nuevo en vivo y cruzar `executions.db` por ventana temporal
  del job afectado; solo un error que persiste en la re-lectura merece acción.

## Tests de scripts de auditoría de cron sin ensuciar producción (verificado 03-nov-2026)

Un test que importa el ensamblador/monitor real y llama su flujo de publicación
sin desviar las globals ESCRIBE en el log y destino de producción (aquí: líneas
falsas de hilo 123 en `ncl_diario_crons.log` confundirían forense posterior).
Patrón verificado (12/12 OK, `/opt/hermes/.venv/bin/python3` = intérprete del
cron, dentro del contenedor):

- El módulo bajo test se resuelve por variable de entorno: `ENSAMBLADOR=<ruta>
  importlib.util.spec_from_file_location(...)` — así la MISMA suite valida la
  copia de DEV o de PROD sin duplicar tests.
- Al re-verificar el claim de tests de otro agente, NO corras la suite contra
  tu copia local (puede estar stale): copia el artefacto VIVO, verifica su sha
  contra el hash declarado y SOLO ENTONCES corre contra esa copia. Receta
  verificada 03-nov-2026 (NCL-DIARIO, cierre ticket 021): `scp
  prod:/opt/data/scripts/ncl_diario_ensamblador.py ./live.py && sha256sum
  live.py` (debe dar `db4dd2b6…`, el sha citado por el par) → `ENSAMBLADOR=$(pwd)/live.py
  python3 tests/test_ncl_diario_ensamblador.py -v`. Un 12/12 verde sobre una
  copia vieja no prueba nada; sobre la copia sha-identica al vivo, es evidencia
  concluyente incluso cuando un selftest huérfano sugiere lo contrario.
- En `setUp`, desviar SIEMPRE las globals de efectos: `mod.DESTINO`,
  `mod.TOKEN_ENV` y `mod.LOG` a archivos temporales de test. Una suite que
  testea `publicar()` sin desviar `LOG` es un test que muta producción.
- Cobertura mínima del bloque Crons: sano, error, >24 h, nunca ejecutado,
  disabled, sin fuentes (debe decir "sin datos", no un verde vacío), perfil
  extra, y parsing de `last_run_at` en sus 3 formas reales (ISO con Z, ISO
  naive heredado, epoch legacy). Más un caso de publicar con desarchivo del
  hilo (mock del GET/PATCH) antes del POST.
- Ejecutar la suite con el MISMO intérprete del job (`/opt/hermes/.venv/
  bin/python3` vía `docker exec hermes-agent`), no con un python del host:
  dependencias y versión difieren y un  verde con otro intérprete no prueba nada.

## Hilo Discord con auto-archive: fallo POST permanente (verificado 03-nov-2026)

- Un hilo de entrega diaria con `thread_metadata.auto_archive_duration` (7 d
  = 10080 s) se ARCHIVA si nadie escribe en él. El POST a hilo archivado
  falla con error 50083 "Thread is archived".
- Riesgo compuesto: si el job falla ≥7 días seguidos, el hilo se archiva y
  A PARTIR DE AHÍ todo POST falla para siempre aunque el cron ya esté sano —
  el fallo se vuelve permanente. Fix barato: antes del POST, PATCH
  `/channels/{tid}` con `{"archived": false}` si `archived` es true.
- Cuidado con los saltos de contexto al auditar health de gateways: en PROD
  los gateways de perfil escuchan en 127.0.0.1:3000-3002 SOLO DENTRO del
  contenedor `hermes-agent` (ss/curl desde el host devuelven vacío y parecería
  que todo está caído). Probar /health con `docker exec hermes-agent ...`.

## Verificar que un informe agendado sigue actualizado (pedido "¿está actualizado?")

- Verificar CADA dato del informe contra su fuente viva (fecha/hora con `date`,
  clima re-consultado, cada tarea contra el store de pendientes, cada alerta
  contra el output real del cron que la origina) y reportar por clases:
  vigente / obsoleto (el hecho ya se resolvió y el informe lo repite) /
  ausente (hay alerta activa que el informe no menciona). No dar un único
  veredicto global: el valor está en señalar qué líneas están muertas.
- El informe hereda lo que dice el store de pendientes: un P-XX cerrado en la
  realidad pero abierto en pending.md reaparece cada mañana como alerta falsa.
  Cerrarlo con evidencia, no con "parece resuelto": `python3
  /opt/hermes-agent-data/scripts/pending_tasks.py close --id P-XX --evidencia
  "<hecho verificado + fecha>"` (regenera pending.md; confirmar con `list
  --estado abierto` → el id ya no aparece).
- Si al informe le falta una fuente (ej. cuota de modelos del watchdog),
  añadirla al PROMPT del job con `hermes cron edit` (ver hermes-cron-ops) y
  ejecutar a mano el comando exacto que el job correrá mañana — la sección
  nueva del prompt se valida con la salida real, no con el eco del edit.

## Reportes agendados: separa productor de emisor y difféa contra el contrato (verificado 04-nov-2026, NCL-DIARIO)

Un pipeline de reporte diario que nace como "un script que calcula Y publica" duplica posts y mezcla roles. Estructura verificada: productor (06:30, SIN `--send`, solo escribe el markdown fuente) → emisor (06:50, valida schema y hace push del JSON) → publicador (07:15, ensambla y POSTea, script puro 0 tokens). Reglas duras:

- **`--send` prohibido en el productor**: solo el emisor/publicador toca Discord. Un productor con send garantiza doble publicación cuando se añade una etapa intermedia.
- **Diffear la composición REAL contra el § de composición del contrato escrito antes de dar por bueno un deploy** — un acuerdo de 5 bloques se implementó con 4 y salió a producción incompleto sin que nadie lo notara; el deploy verde no prueba que el artefacto coincida con lo acordado.
- **Probar el degradado antes de publicar**: sin bloque DEV, pendientes vacíos, todo-verde (modo una línea). El mensaje no debe romperse ni inflarse con datos faltantes.
- **Corrección de un mensaje ya publicado: prefijo explícito (`--nota '<texto>'`)**, nunca un segundo post silencioso que parezca el informe de otro día.
- **Las cifras del informe cambian DESPUÉS de publicarse** si un reporte de ventas entra más tarde que la hora del cron: los totales del histórico quedan viejos a propósito. Antes de citar esas cifras en una decisión de negocio, reconciliar contra la fuente viva — no contra el mensaje publicado.

## Interpretación

- Cero filas para un job NO significa que nunca corrió — leer jobs.json.
- Un `code -15` en un watcher de intervalo puede ser el timeout del runner, pero NO lo
  des lidiando por sentado: verificar la línea `cron.sigterm_audit` del scheduler. Cuando
  un script muere con -15, el runner etiqueta el origen (`origen=runner` para
  timeout/cancel); una muerte `-15` SIN esa línea con `origen=runner` y SIN rastro de
  killguard ni `Received SIGTERM` en gateway.log = **origen=EXTERNO**: alguien fuera del
  runner mandó el SIGTERM al pgid del script. Los scripts se lanzan con
  `start_new_session=True`, así que un `killpg` desde el grupo del gateway NO los
  alcanza — el señalador apuntó deliberadamente al pgid del hijo. Reportar
  "origen externo" y escalar con la evidencia; no atribuir timeout/OOM/restart sin una
  de esas tres descartes (duración larga descarta timeout, killguard descarta el runner,
  gateway.log descarta reinicio).
- Saludos programados de perfiles de cliente (7AM/9AM) están deshabilitados
  intencionalmente (`en: false`) — no es falla.
- `failure_streak` refleja la VENTANA ACTUAL, no el historial (verificado
  03-nov-2026): antes de proponer pausar un cron "fallando", clasificar los
  últimos N runs por ventana temporal + tipo de error. Ej. real: 45 corridas
  con 39 `completed` / 6 `failed` TODAS de la ventana de arranque
  (`dependency environment ... facts.json` + un SIGTERM), `failure_streak=0`,
  `last_status=ok` → cron sano; el "streak=4" citado por otro agente era dato
  viejo del arranque. Re-verificar en vivo antes de pausar o alertar a un par.
- Fallo de 401 "Invalid API key" en un cron → probable placeholder `${VAR}`
  literal en config.yaml (ver mcp-fleet-audit, gotcha generalizado).
