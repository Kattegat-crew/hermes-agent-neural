---
name: hermes-cron-ops
description: >-
  Creación, diagnóstico y verificación en vivo de tareas cron en Hermes. Manejo de namespaces (host vs contenedor), watchers, entregas a Discord y auditoría de jobs programados.
tags: [cron, scheduler, hermes, discord, nsenter, watchdog, vigia, devops]
version: 2.0.0
author: NeuralCrew / Hermes Fleet
---

# Operaciones y Verificación de Cron en Hermes

Habilidad canónica para gestionar, depurar y auditar todas las tareas programadas (cron jobs) de la flota de agentes Hermes, garantizando entregas fiables a Discord y consistencia en los entornos de ejecución.

---

## Cuándo usar esta Skill (Triggers y Síntomas)

Usa esta skill inmediatamente cuando se presente cualquiera de estas situaciones:
- Peticiones del usuario: *"por qué falló la tarea de la noche"*, *"el cron no mandó el reporte a Discord"*, *"crea un cron para vigía"*, o *"audita las tareas programadas"*.
- Diagnóstico de jobs que aparecen como activos pero no producen salida o fallan con errores de permisos (`Errno 13`) o archivos no encontrados (`ENOENT`).
- Configuración de alertas automáticas, watchdogs y entrega de reportes recurrentes.

---

## Arquitectura de Ejecución: La Trampa de los Dos Tickers

Un job en Hermes puede ser reclamado por uno de dos planificadores con vistas de sistema de archivos completamente distintas:

| Ticker / Planificador | Usuario | Resolución de `/opt/data` |
|---|---|---|
| **Gateway (`gateway-default`, s6)** | `uid 10000` (namespace contenedor) | El árbol compartido real del contenedor (`/opt/data`). |
| **Root ticker (Hermes Desktop / Host)** | `root` (namespace del host) | Directorio del host; el árbol real vive en `/root/hermes-agent-legacy-docker/data` o montaje persistente. |

**Consecuencia**: Un script que hardcodea `/opt/data/...` funciona si lo reclama el gateway, pero muere con `FileNotFoundError` si lo reclama el host.

### Regla para Wrappers de Cron
Todo script wrapper de cron debe auto-detectar su entorno antes de ejecutar:

```bash
IN_CONTAINER=0
[ -f /.dockerenv ] && IN_CONTAINER=1

run_cmd() {
  if [ "$IN_CONTAINER" = "1" ]; then
    bash -c "$1"
  else
    docker exec -u 10000 hermes-agent bash -c "$1"
  fi
}
```

---

## Verificación en Vivo bajo Namespaces (`nsenter`)

Para diagnosticar exactamente lo que ve el contenedor del gateway sin suposiciones:

```bash
# 1. Obtener el PID del proceso gateway
G_PID=$(pgrep -f "hermes.*gateway" | head -1)

# 2. Entrar al namespace de montaje y usuario (uid 10000)
nsenter -t $G_PID -m -S 10000 -u -- python3 -c "import os; print(os.listdir('/opt/data'))"

# 3. Comprobar permisos de escritura reales
nsenter -t $G_PID -m -S 10000 -u -- touch /opt/data/cron/output/test_write.tmp && rm -f /opt/data/cron/output/test_write.tmp
```

Si el comando falla con permisos, reparar desde el host:
```bash
chown -R 10000:10000 /opt/data/cron/output/
```

---

## Herramientas y Scripts Incluidos en esta Skill

Esta skill contiene herramientas operativas listas en su subcarpeta `scripts/`:

1. **Auditoría de flota de cron**:
   ```bash
   python3 /opt/hermes-agent/skills/core/hermes-cron-ops/scripts/cron_fleet_audit.py
   ```
2. **Watchdog de ejecución y fallback**:
   ```bash
   python3 /opt/hermes-agent/skills/core/hermes-cron-ops/scripts/fallback_watchdog.py
   ```
3. **Verificación de webhook de Discord**:
   ```bash
   python3 /opt/hermes-agent/skills/core/hermes-cron-ops/scripts/discord_verify_webhook.py --url "$DISCORD_WEBHOOK_URL"
   ```

---

## Migrar de polling a evento

Antes de convertir cualquier cron a webhook, leer `references/migrar-polling-a-evento.md`: cubre cobertura de caminos, flags que nadie activa, permisos del secreto, degradación gradual y cómo probar cobertura en vez de solo transporte.

## Gotchas y Errores Críticos Detectados en Producción

1. **Archivos creados por root**: Si ejecutas pruebas manuales como `root` que escriben en `/opt/data`, dejas trampas de sólo lectura para `uid 10000`. Siempre haz `chown -R 10000:10000` en los archivos creados.
2. **Serialización de terminal background**: Al lanzar procesos en segundo plano con `terminal(background=True, notify=True)`, el valor `notify` debe ser booleano estricto. Si se serializa como cadena `"True"`, el runtime arroja error.
3. **Salida limpia para eventos accionables**: Los cron jobs no deben imprimir basura en stdout si no hay error; solo emitir salida cuando requieran acción para no saturar los canales de alerta.
4. **El `python3` del PATH del cron es el intérprete bundled de Hermes (sin módulos de terceros)**: los scripts de cron resuelven `python3` al intérprete empotrado (ej. 3.14) que NO incluye PyYAML ni otras dependencias externas. Un script que lee secretos con `python3 -c "import yaml"` termina con KEY vacía → `EXTRACT_ERROR` nocturno recurrente y difícil de ver porque el error es silencioso. Regla: en scripts de cron, invocar SIEMPRE `/usr/bin/python3` por ruta absoluta (el sistema tiene PyYAML y el stack completo); verificar antes con `/usr/bin/python3 -c "import <mod>"` cada módulo no-stdlib que el script use.
5. **El ledger no se autolimpia: `failure_streak`/`last_status` persisten tras la recuperación** — un job que falló una vez y hoy entrega bien sigue apareciendo como `error` en `jobs.json`, y los informes matutinos lo reportan como caído (falsa alerta). Protocolo de auditoría antes de creer un "fallo": cruzar `jobs.json` contra las entregas reales en `logs/gateway.log` / `logs/errors.log` del día del fallo. Firma de despacho falsa-negativa conocida: `cron external worker exited before ownership acknowledgement (exit -15)` = worker systemd scope terminado por SIGTERM a los ~8 s; si gateway.log muestra la entrega del mensaje ese día, el job funcionó y solo el ledger quedó sucio. Limpiar el streak manualmente tras confirmar la entrega. Causa raíz confirmada y con pruebas en el repo (ver #6): no es el worker el que falla, es el dispatch que muere y el ticker que re-dispara.
6. **Firma `exit -15` antes del ack = doble disparo del mismo instante**: si el systemd scope del worker muere por SIGTERM antes de publicar el ack, el scheduler registra `dispatch failed` (`mark_job_run(False)` + aviso de crash), pero el job sigue vencido → el ticker lo re-dispara en proceso (`source=builtin`) segundos después y ESE intento es el que corre y entrega. Resultado: una entrega correcta + un aviso de falso fallo + `failure_streak` sucio, y el mismo instante ejecutado DOS veces (riesgo de efectos duplicados si el primer worker alcanzó a actuar). Contratos verificados con pruebas (tests/cron/test_dispatch_failure_terminal.py, verdes): (a) un fallo pre-ack deja el intento TERMINAL — `recover_interrupted_executions()` devuelve 0, la recuperación de dead-owner NUNCA re-ejecuta ese intento; (b) un ack publicado gana sobre el exit code (el bucle revisa `ack_path.exists()` antes de `process.poll()`), así que ack + muerte -15 es handoff válido, no fallo. El arreglo pendiente (rama fix/cron-dispatch-ack-ledger, spec en spec-F7.md) es consumir el instante programado al fallar el dispatch pre-ack; NO introducir reintentos automáticos sin causa raíz.
7. **Forense de dispatch fallido: dónde están las pruebas y cómo leerlas**: (a) cada perfil tiene su propio ledger — default en `/opt/hermes-agent-data/cron/executions.db`, los demás en `/opt/data/profiles/<perfil>/cron/executions.db`; cruzar el job_id del error contra TODOS los ledgers antes de concluir que "no corrió"; (b) `scheduled_instant` se guarda en UTC y `started_at` en hora local: un disparo de 06:00 (-05) aparece como instante `T11:00` — correlacionar sumando 5 h, no comparando a ojo; (c) para desmentir o confirmar hipótesis sobre el handoff, escribir pruebas sonda modeladas en `tests/cron/test_restart_safe_worker_death_evidence.py`: worker falso que adopta/escribe ack/muere con SIGTERM + monkeypatch de `tools.process_registry.restart_safe_gateway_child_argv` devolviendo `GatewayChildDispatch("degraded", [sys.executable, str(worker), *flags])`; correr con `scripts/run_tests.sh tests/cron/<archivo>.py`; (d) en la rama de fallo el scheduler borra el stderr del worker (`stderr_path.unlink`): si necesitas la causa del TERM, capturarla ANTES de que el incidente se cierre o instrumentar la conservación del tail en el incidente.
9. **Store muerto: un job creado sin contexto de perfil puede quedar en un store que ningún ticker reclama y nunca correr** (verificado en vivo, incidente informe de pagos 20:00): `hermes cron create` ejecutado desde la sesión default registró el job en el store central (`/opt/data/cron/jobs.json`), pero los jobs que sí tickean viven en `profiles/<perfil>/cron/jobs.json`; `hermes cron tick` NO ejecuta el job del store muerto (confirma el diagnóstico, no lo repara). Síntoma: job activo en el store, sin línea de ejecución ni en logs ni en ledger, indefinidamente. Protocolo: (a) localizar en cuál jobs.json vive el job antes de culpar al script; (b) recrear el job con el perfil dueño en el entorno del comando (`HERMES_PROFILE=<perfil> hermes cron create ...`), manteniendo la entrega al hilo destino en la config del job; (c) borrar el duplicado del store muerto; (d) verificación final = esperar el primer slot real y confirmar la entrega en el chat (un job puede estar 'correcto' y no haber corrido nunca: su primer vencimiento puede ser futuro). Variante verificada post-fix: un job creado con `HERMES_PROFILE=helmer` puede terminar en el store central Y tickear — lo determinante es la env del comando creador, no solo la ruta del archivo; ante la duda, la prueba de verdad es el primer disparo real, no la ubicación del JSON.
8. **Variante `exit -15` POST-ack ("after adopting this execution… whether side effects ran is unknown") = worker muerto a mitad de corrida, no arranque en frío**: el worker SÍ adoptó y publicó ack y luego recibió SIGTERM externo. Protocolo de triaje verificado en vivo (incidente sync-connections-map 15:00): (a) descartar doble despacho contando los scopes `hermes-worker-cron-<job>-exec-*` arrancados en ese segundo con `journalctl --user -S <t1> -U <t2>` SIN filtro de grep (el ERROR del gateway aparece ~11 s después del "Started" del scope y el scope sigue consumiendo CPU ~10 s más: el wrapper muere antes que el cgroup); (b) descartar reinicio del gateway: `systemctl show hermes-agent -p NRestarts -p MainPID` — 0 reinicios + PID estable = el killer es EXTERNO a Hermes (ni `cron/` ni `gateway/` envían TERM a estos workers, confirmado por grep exhaustivo); (c) descartar OOM: systemd-oomd inactivo + RAM libre; (d) efectos: revisar `cron/output/<job_id>/` (status "silent (empty output)" = sin cambios) y los mtimes de los archivos que el script escribe; si el script es idempotente, el siguiente tick se auto-repara y NO re-ejecutar a mano. Límite duro: identificar QUIÉN envía la señal exige evidencia de kernel (regla auditd sobre la syscall `kill` o bpftrace) que requiere root — como uid 10000 no es posible sin sudo. El RuntimeWarning `<frozen runpy>:130 … 'cron.scheduler' found in sys.modules` en el stderr es cosmético, no la causa.
