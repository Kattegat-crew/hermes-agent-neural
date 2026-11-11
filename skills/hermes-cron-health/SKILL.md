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
  heredoc anidados por ssh rompen el parsing. Flujo fiable: escribir el script
  con write_file en scratch local y redirigir
  `ssh prod 'docker exec -i hermes-agent python3 -' < script.py`; escapar
  comillas dentro de `sh -c "..."` anidado rompe SIEMPRE (un paréntesis mal
  balanceado en el quoting consume más tiempo que escribir el archivo).
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
- **La CLI se apunta a otro perfil con `HERMES_HOME=<dir del perfil>`, no con `HERMES_PROFILE`**
  (verificado 11-nov-2026): `HERMES_HOME=/opt/hermes-agent-data/profiles/vigia hermes cron list`
  muestra `(profile: vigia)` y `cron create/edit/run/runs` operan sobre ese store. Con
  `HERMES_PROFILE=vigia` la CLI sigue respondiendo `(profile: default)` y se crean jobs en el
  store equivocado sin ningún error.
- **`deliver discord:<id>` exige la plataforma configurada EN ESE PERFIL.** Un job de un perfil
  sin Discord devuelve `ran, but the result was not delivered (platform 'discord' not
  configured/enabled)` y sale igualmente `completed`: crear el job en `vigia` con deliver a
  Discord falla siempre, aunque el hilo exista y otro bot tenga acceso. Opciones: (a) crear el
  job en el perfil que sí tiene Discord, o (b) `deliver local` + que el script publique con un
  poster propio (`scripts/vigia_post_thread.sh`) usando el token del bot.
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

- **Token resuelto desde `.env` que ya no vive ahí = meses de avisos perdidos con `exit 0`**
  (verificado 11-nov-2026): un poster que hacía `grep ^DISCORD_BOT_TOKEN= /opt/data/.env`
  devolvía vacío porque desde oct-2026 el token lo materializa el gateway desde el vault
  (`/opt/data/secrets/<bot>.token`). El script salía `exit 0` «silencioso», el cron marcaba
  `ok` y el hilo llevaba sin recibir un aviso desde el 25-oct. Al auditar un job que «avisa»:
  comparar la fecha del ÚLTIMO mensaje real en el canal con la cadencia del job; si el hueco
  supera la cadencia, el aviso está perdido aunque `last_status=ok`. Resolución del token en
  cadena: variable de entorno → `/opt/data/secrets/<bot>.token` → `.env` legacy.

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
- **`last_status` de un job PAUSADO/DISABLED es una reliquia, no un estado**: un job con `enabled: false` + `state: "paused"` (+ `paused_reason`/`paused_at`) lleva días sin correr pero sigue citando el `last_status=ok` de su última corrida pre-pausa como si fuera actual. Un confirmador o chequeo diario que usa `last_status` de un job pausado está confirmando con un dato del pasado: antes de dar por sano o por "sin confirmar" un job, leer `enabled`/`state`/`paused_at` de jobs.json y clasificarlo como `pausado, no ejecutado` cuando `paused_at` antecede a la ventana que se confirma. La causa típica es un `paused_reason=emergency-...` que nadie reactivó.

## Confirmador por ventana: script que audita si otro job corrió cuando debía

Un "confirmador" (ej. verificar que cada perfil guardó memoria en la ventana nocturna) corre como cron `no_agent` y publica UNA línea en Discord. Reglas duras verificadas en producción:

- **El mensaje es contrato de una línea ≤2000 chars**: el detalle por-job debe sanearse (colapsar whitespace, `;`→`,`, `(`/`)`→`[`/`]`, truncar a ~160) — un traceback o un error con `;` del job auditado rompe la separación entre perfiles e infla el mensaje. Calcular el peor caso (N perfiles × detalle máximo) contra el límite, no el caso feliz.
- **Clasificar por verdad viva, no por marcadores**: `paused_reason` residual tras una reanudación NO significa pausado — decide `enabled` + `state` + ventana del `last_run_at`. El `last_status` null con `last_run_at` presente es "sin status registrado", no "nunca ejecutado" (mensajes distintos para estados distintos).
- **Tolerar el run que cruza la medianoche**: un cron `0 23 * * *` legítimamente termina 00:00-01:59; un confirmador que exige el run dentro del mismo día natural produce falso rojo todas las noches. Ventana = franja natural + tolerancia (~2 h post-medianoche), con edad máxima (12 h) que rechaza runs de jornadas anteriores; probar el borde exacto en tests (ej. 02:00 debe ser rechazado).
- **Fail-loud ante ambigüedad**: `enabled` como string ("false") o ausente, `state` en mayúsculas, JSON raíz escalar/lista, fecha ilegible → estado rojo con detalle, jamás verde. Todo lo ambiguo falla en rojo; el único verde es la evidencia positiva (run dentro de la ventana).
- **Verificación e2e del confirmador**: `hermes cron --accept-hooks run <job_id>` → `hermes cron runs <id>` marca `source=direct completed` → leer el último archivo de `cron/output/<job_id>/` y el `delivery_outcome` de deliveries.db. El mensaje entregado en el hilo ES la evidencia viva; un `rc=0` del script aislado no prueba el wiring.

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

## Salud ≠ calidad: cron verde con entregable degradado (verificado en vivo sobre el resumen diario de tickets)

Un `last_status=ok` solo prueba que el script TERMINÓ, no que el entregable valga. El resumen diario de tickets salió con líneas sin sentido mientras el cron marcaba verde — tres defectos encadenados que ningún check de health detecta. Al auditar o reparar un job, leer el CONTENIDO publicado, no solo el estado:

- **Verificar QUÉ ruta produjo la salida.** Un script con ruta primaria (LLM/API) + fallback determinista sigue en exit-0 cuando la primaria falla en silencio (ej. la clave de API fue renombrada en .env: el script buscaba la variable vieja y el fallback tomó el control sin loggearlo). Sonda: invocar la ruta primaria de forma aislada con la misma lectura de credenciales y confirmar que devuelve contenido real, no el fallback.
- **Los modelos de razonamiento consumen `reasoning_content` del MISMO presupuesto `max_tokens`**: con un límite justo, el `content` llega VACÍO o truncado aunque la respuesta sea 200. Presupuestar ~3x el output esperado y validar longitud mínima del content antes de aceptarlo como válido.
- **Probar los helpers de corte de texto contra la forma REAL de los datos**: un `split(" — ")` correcto en títulos sueltos produce basura cuando TODAS las filas comparten prefijo (`TKT — <título real>`) → N líneas idénticas. Un helper que nunca vio el corpus real no está probado.
- **Regla de legibilidad para reportes agendados: cada línea se explica sola** — el lector no abre los hilos/fuentes. Prohibida la línea que solo repite el nombre del ítem: en abiertos/pendientes, qué es y qué falta para cerrarlo; en cerrados, el resultado operativo.
- **`/opt/hermes-agent-data/scripts/` está en .gitignore (`/scripts/*`)**: los scripts de crons NO tienen versionamiento ni backup por defecto. Antes de editar uno con historial implícito, copiar la versión previa con timestamp a un backup propio; nunca asumir que git lo cubre.

## Atribuir el exit 1 al paso real (y no re-parchar lo ya corregido)

- Antes de proponer un fix sobre un script de cron que falló, cruza la hora de la corrida fallida con el `git log` del script: si el commit que corrige el problema es POSTERIOR a la última corrida fallida, el job ya está corregido en disco y solo falta una corrida verde — parchar de nuevo duplica trabajo y ensucia el diff.
- El exit 1 de un job multi-paso puede venir de un paso FINAL (push git, upload a Drive), no del trabajo principal: los errores por-ítem suelen saltarse con `continue` y no tumban el job. Ubica el traceback en el output file del cron y mapea los números de línea contra el archivo EN DISCO actual, no contra la versión que crees que corrió. La regla vale para TODA cita en un reporte de verificación entre agentes: números de línea y rutas se citan SOLO desde una lectura de disco hecha en la MISMA sesión del reporte — citarlos desde el contexto de turnos anteriores apunta a una versión que otro parche pudo mover, y el bloque/ruta que citas sale desplazado sin que el comportamiento descrito cambie (típico: la rama citada baja ~100 líneas y el log vive bajo el directorio de output del componente, no donde lo recordabas).
- Los errores de API por-ítem marcados con ✗ en el log NO son la causa del exit 1 si el loop los salta: acota el paso muerto con la última línea exitosa del log, no con el primer error visible.

## Alertas de fallo en ventana de arranque del gateway (Gateway starting: deadline)

- Un aviso "cron failed: GatewayUnavailableError: Gateway starting: deadline"
  puede NO ser un fallo del job: `hermes cron runs <job_id>` (dentro del
  contenedor) marca cada corrida con `source` — `direct` = corrida
  manual/forzada, no del scheduler. Verificar SIEMPRE si la corrida que falló
  fue manual antes de diagnosticar el job; el run agendado puede estar sano y
  simplemente pendiente.
- El dispatch de cron exige el gateway en estado `running`: durante el boot del
  contenedor hermes-agent (~4 min hasta que el bridge de WhatsApp conecta) el
  gateway pasa por `starting`/`draining` (transitorios) y el dispatcher aborta
  con "Gateway starting: deadline" SIN fallback local. Cruza los timestamps de
  los fallos con los arranques del contenedor (uptime de `docker ps` + banners
  "Hermes Gateway Starting" en el log del gateway): si caen dentro de ventanas
  de boot, es ambiental — no parches ni pauses el job.
- Estado vivo del gateway: `/opt/data/gateway_state.json` en la RAÍZ de
  /opt/data (NO bajo `profiles/<name>/`); si un script dice FileNotFoundError
  ahí, la ruta asumida está mal, no el sistema. Campos útiles: `gateway_state`,
  `pid`, `platforms.<x>.state/updated_at`, `updated_at` (mtime fresco = vivo).
- **Gateway caído ≠ fallo del job, y NO hay catch-up**: las corridas agendadas
  durante la caída quedan como `missed ×N (skipped, catch-up off)` en
  `hermes cron runs <job_id>` — al volver el gateway el scheduler NO las
  re-ejecuta. Tras una caída, revisar los jobs críticos con `cron runs`,
  rescatar a mano lo que aún tenga sentido con `hermes cron run <job_id>`
  (queda como `source=direct`), y verificar que la siguiente corrida agendada
  sale `ok` antes de dar por recuperado el servicio.
- Firma de caída por memoria agotada: bucle de `gateway.exit_nonzero` en el log
  de diagnósticos + pocos MB libres y varios GB de swap. Antes de culpar al
  gateway o a los crons, medir con `ps -eo pid,etime,rss,cmd --sort=-rss`:
  los procesos agy/opencode de horas acumulando 0.5-1.5 GB cada uno son la
  causa típica; liberarlos recupera el host, matar/reiniciar el gateway no.
- Output del run de ~87 bytes (`# Cron Job … (FAILED)`) = el agente nunca
  arrancó: cero costo de tokens y nada guardado; no hay nada que reconciliar y
  `failure_streak` se resetea con la próxima corrida exitosa.
- Para atribuir reinicios del contenedor: `docker inspect` → `RestartCount` y
  `HostConfig.RestartPolicy.Name`. Con `RestartCount=0` y policy
  `unless-stopped`, los reinicios son EXTERNOS (compose/manual), no crash-loop
  de Docker. Compara `docker images ... CreatedSince` con el `Created` del
  contenedor: imagen vieja + contenedor recreado = re-config o reinicio manual,
  no deploy de imagen nueva.

## Reinicio del gateway y pausas de emergencia (bucle de caídas)

- `systemctl restart` del hermes-agent desde un cron/script dentro del contenedor falla SIEMPRE con "Interactive authentication required" (no hay tty/agent de polkit que apruebe la acción privilegiada). Ruta que SÍ funciona: la unidad tiene `Restart=on-failure` — matar el proceso del gateway (SIGTERM al PID de `gateway_state.json`, escalar a SIGKILL si no muere) y dejar que systemd lo relance. Cerrar el ciclo verificando: PID nuevo distinto del anterior + procesos hijos MCP levantados (`ps` bajo el nuevo PID).
- Patrón de diagnóstico "TODOS los servidores stdio caídos, TODOS los HTTP vivos" = los hijos stdio murieron con el proceso padre del gateway (los HTTP viven fuera y sobreviven). Es UN síntoma con UNA cura (reinicio del gateway), no un problema por-servidor: no auditar configs servidor a servidor ni parchar timeouts/lazy flags — el patrón global de 30+ servidores lo descarta de entrada.
- Una pausa masiva de crons (`paused_at` + `paused_reason=emergency-...`) debe nacer con plan de reactivación: los jobs pausados dejan de notificar en silencio (ventas, alertas, digests) y nada delata el silencio mientras dure. Al reactivar, ir por criticidad de negocio primero (watchers de ingresos) y decidir el resto después; distinguir los pausados deliberadamente de los arrastrados por una emergencia ajena.
- Reanudación masiva: la CLI `hermes cron` agota timeouts con muchas jobs — reanudar con la tool de crones en tandas de ~10-20 llamadas y cerrar con conteo final de `paused_at` restante (0 salvo pausas deliberadas), no con el eco de las llamadas.
- La pausa de emergencia y su reanudación son OPERACIONES CROSS-PERFIL: cubren `/opt/data/cron/jobs.json` (default) Y `profiles/*/cron/jobs.json` a la vez. Una reanudación aplicada solo al store del default deja TODOS los jobs de perfiles pausados (buzones, vigilancia, guardado de memoria) con `paused_reason=emergency-...` indefinidamente — y el silencio es invisible porque los jobs pausados ni notifican ni fallan. Cerrar el ciclo SOLO con conteo de `paused_at` restante por CADA store globado, nunca por el default solo. Antes de reanudar, re-apuntar los `deliver` de los jobs críticos si su canal destino cambió (un canal muerto reintroduciría el silencio que la pausa causó).
- **"Revertida a medias" se detecta por el sello residual, no por el acta**: una reversión de pausa masiva puede haberse aplicado a un subconjunto de stores y el resto queda congelado sin que nadie lo note (nada falla, nada notifica). Días después, un confirmador o el usuario descubren jobs "sin confirmar" con el sello intacto. Regla: tras revertir, re-grep del `paused_reason` de la emergencia en TODOS los stores globados; cualquier hit = reversión incompleta, re-aplicar sobre los faltantes.
- **Al reanudar, el catch-up dispara de inmediato y luego re-ancla**: los jobs de intervalo re-habilitados corren en los minutos siguientes a la reanudación (esa tanda de corridas `ok` con timestamps idénticos es la EVIDENCIA de que la reanudación funciona) y su `next_run_at` se recoloca en la franja natural de la cadencia — no es un desajuste. Un job reanudado SIN stamp de corrida inmediata no está realmente reanudado: re-verificar.
- Verificar que el canal del `deliver` existe ANTES de confiar en la notificación: un canal borrado o un bot expulsado del guild devuelve 404/10003 "Unknown Channel" y el mensaje se pierde sin que `last_status` lo refleje. Al descubrir un canal muerto, re-wirear TODOS los jobs que apuntaban a él (grep de ids en jobs.json cross-perfil), no solo el que se descubrió fallando. PERO clasifica el canal con el cliente sancionado (tool discord, `scripts/_discord_token.py`), no con curl a mano sobre el token del gateway: una REST manual puede responder 401 por auth/UA aunque el canal exista, y re-wirear sobre ese falso muerto rompe entregas vivas.
- Un `delivery_failed` puede apuntar a un canal VIEJO mientras el script del job ya se auto-publica por su cuenta en el canal nuevo: lee la config `deliver` actual del job y el canal que el script usa antes de sentenciar roto — el fallo puede ser solo el aviso de fallo, no la entrega real.

## Brote transitorio: rebuild de dependencias del PM tras update (NoCommittedEnvironment / pre-ack)

- Firma: VARIOS crons fallan en cadena dentro de una ventana corta con
  `cron external worker exited before ownership acknowledgement` o
  `NoCommittedEnvironment (no dependency environment is committed for this install)`.
  Causa: un update de versión dispara el rebuild de dependencias (el mtime de
  `.venv/lib/python3.14/site-packages` cambia en medio de la ventana) y los workers
  externos arrancan sin generación comprometida y mueren antes del ack. Es AMBIENTAL:
  los jobs no están rotos, no parches scripts ni pauses nada.
- Cierre del caso con evidencia viva, no con la ausencia de nuevos fallos: releer
  `jobs.json` de cada job afectado (`last_status=ok`, `failure_streak=0`, corrida
  posterior a la ventana) y ejecutar a mano el script de al menos un job con su modo
  dry-run (`--dry-run`, exit 0) antes de declarar recuperado el lote.

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
- Un `code -15` NO implica entregable perdido: cruza la hora del error con `agent.log` —
  si el mismo job aparece segundos después como `delivered ... message_id=`, el SIGTERM
  llegó DESPUÉS de producir la salida y el aviso de "job muerto" es ruido (el reportador
  lee el rc de la fila, no la entrega). Clasificar por el entregable real publicado, no
  por el código de salida.
- Los parches de runtime aplicados sobre la instalación viva SE PIERDEN en un
  cutover/upgrade de versión (la imagen nueva trae HEAD limpio sin el parche). Antes de
  usar el killguard como descarte de origen, verificar que sigue presente en el código
  vivo (`git show HEAD:cron/scheduler_script.py | grep -c killguard` → 0 = ausente;
  `agent/killguard.py` inexistente) y re-aplicar el patcher preservado en
  `/opt/data/scripts/` (p. ej. `zz_patch_killguard.py`), commit al overlay de PROD para
  que el próximo upgrade no lo borre de nuevo. Un vigía que atribuye muertes a "PID
  reciclado" sin confirmar que el blindaje sigue instalado está citando una protección
  que ya no existe.
- Los outputs per-run viven en `/opt/data/cron/output/<job_id>/<fecha_hora>.md` con el status textual (`silent (empty output)` = OK, `script failed / exited with code -15`): leer las corridas vecinas del mismo job ahí clasifica un -15 puntual (una mala rodeada de silencios sanos = ruido transitorio) sin abrir executions.db.
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
