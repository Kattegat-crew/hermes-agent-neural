---
name: tesoreria-casinos-ops
description: Use when operating or debugging the casino treasury pipeline (radar de pagos, ingesta Gmail, Sheet diario, clasificacion de pagos Nancy/Yulieth). Rutas, deploy a PROD, dedupe, journal y trampas conocidas.
---

# Tesoreria casinos — operacion y pitfalls

Pipeline de pagos Golden (Nancy) y Lucky/The Grand Paradise Club (Yulieth). Repo `Kattegat-crew/Golden-Game-Casinos`, modulo `finanzas/`. Fuente de verdad = repo en DEV; PROD solo recibe copias.

## Rutas
- DEV: `/opt/golden-game-landing/finanzas` (owner orca:orca; el agente no escribe ahi → instalar via `ssh root@147.93.3.250` + chown).
- PROD host: `/opt/hermes/data/scripts/finanzas/*.py` (uid 10000) = contenedor `/opt/data/scripts/finanzas/` → `docker cp` + chown.
- DB: `/opt/hermes/data/finanzas-casinos/golden.db`.
- Jobs: `99b6b918537c` informe 20:00 · `3b718dbbf7da` Nancy 20:15 (Golden) · `a5faf18b066b` Yulieth 20:16 (Lucky).
- Sheet vivo `1PkVF9CUiLiwu3caXxUK0LiWNx0WFPXtIZKqjWQRZWoE`.
- Clasificador web: systemd `clasificador-pagos` en host PROD, `100.73.30.29:8777`.

## Comandos
```bash
cd /opt/golden-game-landing/finanzas && /opt/data/venvs/finanzas/bin/python -m unittest discover -s tests
scp -q f.py root@100.73.30.29:/tmp/ && ssh root@100.73.30.29 'cp /tmp/f.py /opt/hermes/data/scripts/finanzas/ && chown 10000:10000 /opt/hermes/data/scripts/finanzas/f.py && docker cp /opt/hermes/data/scripts/finanzas/f.py hermes-agent:/opt/data/scripts/finanzas/f.py'
ssh root@100.73.30.29 'docker exec hermes-agent python3 /opt/data/scripts/finanzas/preguntas.py --db /opt/data/finanzas-casinos/golden.db --marca Golden'
ssh root@147.93.3.250 'cd /opt/golden-game-landing && HOME=/opt/hermes-agent-data/home git push origin main'
```

## Trampas que costaron tiempo
1. `hermes cron create` sin `HERMES_PROFILE=<perfil>` va a `/opt/data/cron/jobs.json` y no tickea. Usar `docker exec -e HERMES_PROFILE=nancy ...`.
2. `state.db` de otro perfil esta bloqueado por regla deny. Para recuperar algo de un chat: job agent-mode en ese mismo perfil con prompt explicito.
3. Instrucciones al LLM no son garantias: `AGENTS.md` no se inyecta por turno; `SOUL.md` si. Aun asi, para registrar datos usar mecanismo determinista (hook con filtro o cron de lectura).
4. Marca: Nancy=Golden, Yulieth=Paradise. Si el generador devuelve 0 lineas NO enviar: verificar el cuerpo antes de entregar.
5. `dedupe.py` marca con `duplicado_de` (no borra); informe/preguntas filtran `duplicado_de IS NULL`. GOU = pasarela que duplica pago real. Misma fuente+mismo monto = ambiguo, no tocar.
6. Un perfil no entrega a chats de otro; no duplicar tokens de bot entre perfiles.
7. El repo tiene archivos sueltos de otros trabajos (meta-capi): commitear solo rutas de `finanzas/`, nunca `git add -A`.

## Loop de clasificacion
`preguntas.py` arma el mensaje (pendientes numerados) → `respuestas.py --texto` parsea, escribe en `pagos`, journaliza en `clasificacion_journal` y aprende en `conceptos_aprendidos`. El registro debe ser determinista; si el agente no ejecuta, la respuesta se pierde (ocurrio con 3 notas de voz de Nancy).

- **Gate anti-mensaje-vacio:** los jobs de pregunta (`pregunta-pagos-nancy/yulieth`) deben correr con `--monitor-script`: el script cuenta pendientes del dia en la DB y si es 0 NO despierta al agente (sin mensaje, sin costo). Nunca depender de que el generador decida callarse: un entregador con 0 lineas ya envio un mensaje mudo en produccion.
- **Captura determinista de la respuesta:** en la build 0.22.6 (PROD, commit 97511f5df0) el hook `pre_llm_call` **no soporta `{"action":"block"}`** (no existe `PRE_LLM_BLOCK_EXIT_REASON`): solo inyecta `{"context": "..."}` en el mensaje del usuario. El plugin `pagos-gate` (perfiles `nancy` y `yulieth`, hooks `pre_llm_call`) aplica la clasificación él mismo y devuelve contexto "REGISTRO YA EJECUTADO..." para que el agente solo confirme. Ver sección «Gate pagos-gate».
- **Horario y alcance (decidido 04-nov-2026):** las preguntas salen a las **06:00 (Golden) y 06:01 (Paradise)** — antes 20:15/20:16, «muy tarde». `preguntas.py` corre en **modo mes** por defecto: `--desde` cae al día 1 del mes en curso, así la pregunta lista TODO lo que sigue sin clasificar del mes (no solo el día), y el título dice «Pagos de <mes>». Para preguntar solo un día: `--desde <mismo día>`.
- **Gate y modo mes:** el gate valida por pago (`_sigue_pendiente(pid)`, `categoria IS NULL`), no contra la lista de pendientes del día, y `_dia_con_pendientes` acepta un día que solo tenga fila fijada en `pregunta_dia_marca`. Sin eso, los números del modo mes se descartaban como «ya clasificados».
- **Envío manual de la pregunta** (sin esperar al cron): generar y mandar con acuse
  `docker exec hermes-agent sh -c 'python3 /opt/data/scripts/finanzas/preguntas.py --db /opt/data/finanzas-casinos/golden.db --marca Golden > /tmp/q.txt; hermes send -t whatsapp:<jid> -f /tmp/q.txt'`
  El script imprime y fija el pin a la vez; si no hay pendientes no imprime nada (silencioso, no se envía mensaje vacío).

## Gate pagos-gate (registro determinista de la respuesta)

Cierra el agujero "el LLM olvidó ejecutar `respuestas.py`": el registro ocurre en un hook, no depende del modelo.

- **Pinning por marca (bug real):** `pregunta_dia` tiene PK solo `dia`, así que la pregunta de Nancy (20:15, Golden) y la de Yulieth (20:16, Paradise) se pisan con `INSERT OR REPLACE`; `respuestas.aplicar()` leía esa fila y podía clasificar pagos de una marca con los números de la otra. Además, tras aplicar parte de los números la lista pendiente se reordena y los números **se desplazan**. Solución: `preguntas.py` ahora escribe `pregunta_dia_marca (dia, marca, ids)` al armar la pregunta, y el gate mapea número → id contra esa fila fija.
- **Script:** `/opt/data/scripts/finanzas/respuestas_marca.py --db <db> --marca Golden|Paradise --texto "..." [--dia] [--dry-run]`. Reutiliza `preguntas.pendientes`, `respuestas.parsear` y `asegurar`; escribe `pagos` + `clasificacion_journal` (`despues='respuesta manual (gate)'`) + `conceptos_aprendidos`. Solo aplica categorías reconocidas: `desconocido`/`otros` quedan como `dudosos` para el agente. Nunca reescribe un pago que ya no está pendiente.
- **Plugin:** `/opt/data/profiles/<nancy|yulieth>/plugins/pagos-gate/{plugin.yaml,__init__.py,config.json}` + `pagos-gate` en `plugins.enabled` del `config.yaml` del perfil. `config.json` = `{"marca":"Golden"|"Paradise","db":"/opt/data/finanzas-casinos/golden.db"}`.
- **Guardas del hook** (evitan secuestrar la charla normal): solo `platform=whatsapp`, texto ≤500 chars, sin `/comando`, con número (`1 ...`) **y** una categoría del catálogo de `respuestas.CATS`. Dry-run primero; solo si hay algo aplicable ejecuta de verdad.
- **Sin reinicio:** el multiplexor recarga plugins por perfil con el verbo de control:
  `docker exec hermes-agent /opt/hermes/.venv/bin/python -c "from pathlib import Path; from gateway.control_socket import reload_gateway_plugins as r; print(r(Path('/opt/data'), profile_home=Path('/opt/data/profiles/nancy')))"`
  Respuesta buena = `reloaded: True` + `pagos-gate` en `activations` con `hooks:['pre_llm_call']`. No hace falta tocar `gateway-default` (Nancy y Yulieth NO tienen gateway standalone: sus servicios `gateway-nancy`/`gateway-yulieth` tienen archivo `down` y las sirve el multiplexor).
- **Prueba sin datos reales:** copiar la DB con `sqlite3 src.backup(dst)`, marcar 2-3 pagos de ayer con `categoria=NULL`, fijar `PAGOS_GATE_DB`/`PAGOS_GATE_MARCA` e invocar el hook a mano. Casos que deben devolver `None`: saludo, `2 ok`, `3 no sé`, texto >500, `discord`, `/soul`, y repetir un texto ya aplicado.

## Mapa de canales (Discord NCL, 04-nov-2026)

- Un hilo por agente dentro del foro `⚔️・digital-vikings`; los crons de cada agente entregan ahí con `deliver=discord:<id del hilo>`.
- Ids: Bragi `1567587777120313376` · Vili `1567587877255258185` · Heimdall `1567587887757926501` · Sindri `1567587895827763212` · Hermodr `1567587903406612661` · Brokkr `1567587908989485108` · Freyja `1567587916639903794` · Ullr `1567587925548335355` · Finanzas `1567587939783806996` · Calendario `1567587946373062667`.
- **Al archivar un hilo al que un cron entrega, la entrega se rompe en silencio.** Antes de archivar/migrar: buscar el id en todos los `jobs.json` (`deliver` y `failure_deliver`) y re-apuntar. Chequeo: cruzar cada `deliver=discord:<id>` contra el estado real del guild (activo/archivado/inexistente).
- Los foros `⏰・crons-bragi` y `⏰・crons-ads` quedaron históricos (0 jobs apuntan a ellos); los canales de texto viejos de cada bot también (0 referencias).

- **Jobs legacy retirados (04-nov-2026):** `recuperar-respuesta-nancy` y `reenvio-pregunta-nancy` borrados; el registro ya es del gate, no de un cron de recuperación. El `informe-pagos-diario-golden-lucky` se queda a las 20:00 (decisión de Plon).

## Verificacion antes de declarar hecho
- journal crecio y `pagos.categoria` cambio (que el mensaje saliera no es prueba).
- HEAD local == origin/main.
- Sheets: leer de vuelta por API.
