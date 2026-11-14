# Feature Specification: HERMES-KILLGUARD — señalización con identidad verificada

* **Status**: Completed
* **Author**: Ragnar
* **Target Module**: `agent/`, `cron/`
* **Created**: 2026-11-14
* **Updated**: 2026-11-14

---

## 1. Problem Statement & Motivation

* **What is the problem?** `os.killpg(os.getpgid(pid), SIG)` sobre un PID ya muerto resuelve
  al grupo de quien **hoy** tiene ese número. Si ese proceso lidera su propio grupo, la señal
  mata a un grupo ajeno: así murieron scripts de cron de trabajos sin relación con SIGTERM
  (`Script exited with code -15`) el 17-18 oct 2026 y otra vez el 14-nov 2026.
* **Why solve it now?** El 10-nov 2026 se reconstruyó la imagen y `cron/scheduler_script.py` /
  `agent/deadline.py` quedaron sin el wrap y sin `agent/killguard.py` (`zz_check_killguard.sh`
  → "SIN parche" en los tres archivos). Cada actualización de imagen vuelve a borrar la
  protección si no vive en el repositorio. Costo del incidente: 6 trabajos caídos en PROD un
  14-nov (0.6% de ~1000 ejecuciones), recuperación ≤5 min por tick, alertas repetidas.
* **Evidencia**: `executions.db` en PROD (`exit -15` a las 08:42, 09:00, 09:42, 10:45, 11:10,
  12:25), `zz_patch_killguard.py`, `vigia_sigterm.py`, `escalation_watcher_gate.sh`.

---

## 2. Goals & Non-Goals

### Goals
- [x] Que ninguna señal de grupo/pid salga sin verificar que el líder sigue siendo el mismo
      (`starttime` del kernel, campo 22 de `/proc/<pid>/stat`).
- [x] Que el guard viva en el repositorio, de forma que un rebuild de imagen lo herede.
- [x] Que la muerte de un script con `-15` quede etiquetada en logs (`HERMES-SIGTERM-AUDIT`).
- [x] Que exista una prueba de regresión que falle si alguien vuelve a quitar el wrap.

### Non-Goals (Out of Scope)
- Identificar al **emisor** exacto de la señal en el incidente del 14-nov: la auditoría del
  04-nov no está instalada en PROD, así que no hay rastro de quién la mandó.
- Mover el emisor a `escalation_watcher`/`vigia` (trabajo separado, ya documentado en scripts).
- Despliegue a PROD, reinicio del gateway y hook de boot (van post-merge del PR).

---

## 3. User Stories & Functional Requirements

* **US-1**: Como operador de la flota, quiero que un cron no muera por señal de otro trabajo,
  para que las alertas de "fallo" solo muestren fallos reales.
  * **Requirement 1.1**: `safe_killpg` debe rechazar el kill si `starttime` del líder no
    coincide con el capturado en el sitio de llamada.
  * **Requirement 1.2**: `safe_kill` debe aplicar la misma verificación en la rama `os.kill(pid)`.
  * **Requirement 1.3**: Los grupos protegidos (init, grupo propio, pid<=1) nunca se señalan.
* **US-2**: Como técnico revisando un `-15`, quiero saber si la señal fue del runner o externa.
  * **Requirement 2.1**: Al morir con `-15`, loguear `cron.sigterm_audit: script=… pid=…
    pgid=… origen=… duracion=… gateway_pid=…`.

---

## 4. Acceptance Criteria & Invariants

* **Scenario 1 — líder reciclado**: Dado un hijo que lidera su grupo, cuando se llama
  `safe_killpg(pgid, SIGTERM, expected_starttime=live+1)` entonces devuelve `False`, el
  registro loguea `REFUSED … leader recycled` y el grupo ajeno no recibe nada.
* **Scenario 2 — entrega legítima**: Dado el mismo hijo con el `starttime` correcto, cuando se
  llama `safe_killpg` entonces devuelve `True` y el hijo sale con `-SIGTERM`.
* **Scenario 3 — presencia**: Dado el árbol del repo, cuando se ejecuta
  `pytest tests/cron/test_killguard_signal_guard.py` entonces los tests fallan si
  `agent/killguard.py` desaparece o si alguno de los dos sitios de señalización pierde el wrap.
* **Invariantes**: `-15` reportado por el runner solo puede salir del bloque de auditoría si la
  señal vino de fuera (los caminos timeout/cancel devuelven antes con su propio mensaje).

---

## 5. Security, VPS & Operational Considerations

* Sin variables de entorno nuevas, sin puertos, sin cambios de límites.
* Los logs nuevos (`killguard: …`) van por el logger existente (`cron.scheduler`) y pasan por
  el redactor de Hermes; no escriben secretos ni PII.
* Impacto en prompt-cache/token-latency: cero (no toca prefijos de conversación ni toolsets).
* Rollback: `git revert` de los 4 archivos; ningún estado persistido se migra.

---

## 6. Applicable Project Skills

- [x] `.skills/code-review-and-quality/SKILL.md` — revisión por dos ejes (estándares +
      especificación), veredicto APROBADO/CAMBIOS REQUERIDOS citando el SHA.
- [x] `.skills/systematic-debugging/SKILL.md` — descarte de OOM, timeouts, watchdog y reinicios
      antes de aceptar la hipótesis de reciclaje de PID.
