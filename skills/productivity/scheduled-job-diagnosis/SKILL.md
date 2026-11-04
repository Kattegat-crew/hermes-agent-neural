---
name: scheduled-job-diagnosis
description: "Use when a scheduled job did not run its expected action."
tags: [cron, scheduler, diagnostico, jobs, hermes, timezone]
version: 1.0.0
author: Ragnar
---

# Diagnóstico de un job programado que "no hizo su trabajo"

Aplicable a cualquier job recurrente (Hermes `cronjob_manage`, un script de cron, un daemon, un watchdog NO_AGENT) del que el usuario espera una acción y "no pasó nada". El objetivo es distinguir **timing/en-cola** de **falla real** con evidencia, antes de tocar o re-disparar.

## Regla mental: tick ≠ acción instantánea

Un job con disparo por **intervalo** (p. ej. `every 60m`) o por **hora de reloj** actúa en el PRIMER tick que (a) cumpla su condición Y (b) cuya ventana haya abierto. Entre el momento en que la condición se vuelve true y el tick que actúa puede pasar hasta **~1 intervalo completo**. Eso es diseño del scheduler, no un fallo.

Ejemplo real: pieza con `slot=12:00` y ventana `slot ± 2h` (12:00–14:00). El tick de las 11:22 no publica (ventana no abrió); el tick de las 12:22 sí. Se percibe como "1h de retraso". No es un bug.

## Checklist de diagnóstico (en orden)

1. **Lee el estado en el dato fuente** (JSONL/DB/archivo/estado del daemon). Mirar el campo de "acción hecha" (ej. `publicado_en`, `media_ids`, timestamp de última corrida):
   - Condición true + campo de acción ausente → en cola, o la ventana no abrió.
   - Campo de acción presente → ya actuó; el problema es otro (entrega, visualización).

2. **Lee el artefacto de corrida del tick** (en Hermes: `cron/output/<jobid>/<fecha>_<hora>.md`):
   - **Vacío (0 bytes)** → el agente respondió `NO_REPLY`, o el script no produjo salida = no había nada que hacer en ESA corrida. **Normal mientras la condición no se cumple. NO es una falla.**
   - **No vacío** → pasó algo real: un fix auto-aplicado, un `ERROR` con traceback, o una confirmación de acción. **Abre SIEMPRE los no-vacíos** — ahí viven los fallos. Un `ERROR`/excepción en el `.md` es falla real.

3. **Simula la condición SIN ejecutar la acción** (replica la lógica del job, no la dispares). Imprime si la condición "debería abrir" en el próximo tick. Si sí → es timing, no bug. No ejecutes el publish/dispatch para "probar".

4. **Verifica el periférico** (si el job depende de un servicio externo — Composio, una API, un túnel, OAuth):
   - Usa el shim/del contenedor, no el binario directo. En este stack: `data/.local/bin/composio` (SSH a `root@10.0.2.1`, el host) — el binario local `~/.composio/composio` NO lista conexiones útiles (ver `composio-cli`/`cron-runtime-verification` para el detalle del puente).
   - `connections list` → parsear el bloque relevante y mirar `status: ACTIVE`. Para el detalle por cuenta: `dev connected-accounts list`.
   - Conexión `EXPIRED`/`EXPIRING` = la acción corre pero el proveedor la rechaza → el `.md` muestra fallo aunque el código esté sano.

5. **Revisa el directorio de salida del cron** (`cron/output/<jobid>/`): si quedó `root:root 700`, el scheduler (uid 10000) no escribe → el job **muere en la entrega** con `Connection reset`/`Permission denied`, NO con un traceback en el `.md`. Reparar: `docker exec <ctr> chown hermes:hermes /opt/data/cron/output/<jobid>` y re-verificar con `touch` de prueba.

   **Causa raíz verificada (09/09/2026)**: los archivos `root:root` los deja el **`docker exec` del host, que entra al contenedor como root** (`docker exec hermes-agent id` → `uid=0`), mientras el gateway corre como hermes (s6 `s6-setuidgid hermes`). Fix estructural: correr esos execs del host con `docker exec -u hermes …` y normalizar `chown -R hermes:hermes /opt/data/cron`. Un mismo síntoma de "el job no hizo nada" tiene 2 formas de fallo: `[Errno 13] Permission denied … .output_*.tmp` (dueño mezclado) vs `can't open file '/opt/data/...': No such file` **aunque el archivo existe** (se disparó en contexto host, donde `/opt/data` no existe).

6. **Triage rápido de recurrencia** (`hermes cron`): `incidents` (incidentes agrupados por firma: error, first/last seen, estado), `history <job_id>` (corridas del job con error completo), `runs` (todas las recientes). Ojo: `hermes cron status` puede decir "ticker has not reported a heartbeat" aunque los jobs SÍ disparen — no es prueba de cron roto; confírmalo con `runs`/`incidents`.

## Esquema mental para responder

| Observación | Veredicto | Acción |
|---|---|---|
| Condición true, tick reciente vacío, ventana no abrió | Normal (en cola) | Reportar hora del próximo tick; NO forzar. |
| Condición true, tick DENTRO de ventana vacío | Sospechoso | Investigar `.md` del tick + periférico. |
| `.md` con `ERROR` + traceback | Falla real | Leer traceback, confirmar periférico ACTIVE, revisar tz. |
| Acción hecha + `media_ids`/links | Actuó | Dar identificadores/links; no re-ejecutar. |

## Pitfall de la zona horaria (recurrente, alta prioridad)

El dato fuente suele guardar timestamps **naive** (hora local `-05`) mientras el job calcula `now` **aware** con un `TZ`. Restar `now - naive` lanza `TypeError: can't subtract offset-naive and offset-aware datetimes` en cuanto hay una fila que cumple la condición → rompe TODO el job en ese tick, de forma determinista.

Patrón-fix (helper antes de la resta):
```python
def _slot_dt(s):
    d = datetime.fromisoformat(s)
    return d.replace(tzinfo=TZ) if d.tzinfo is None else d
```
Es la **primera causa** a revisar cuando un job de publicación "de repente" falla con TypeError. Si el tick muestra este traceback, el fix es del lado del job, no de los datos.

## Relacionadas

- `cron-runtime-verification` / `hermes-cron-runtime-verification`: verificación de que un cron PUEDE correr en el namespace del gateway (registro de rutas, permisos, deps). Este diagnóstico complementa cuando el cron corrió pero "no hizo lo esperado".
- `service-availability-forensics`: cuando el síntoma es un servicio que se cae o un fix de watchdog que se ve falso.
- `hermes-scheduled-jobs` / `cron-watchdog-scripts`: creación y watchdog de jobs Hermes.
