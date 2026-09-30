# VPS Dev Guardian v1.1.0 — Informe de implementación (para reviewer independiente)

Fecha: 2026-09-29 21:2x (-05, America/Bogota). Entorno: VPS Dev vmi3151337 (147.93.3.250) — este host es dev; el repo vivo /opt/hermes-agent es el árbol real.

Versión 1.1.0: corrige los hallazgos del primer reviewer independiente (informe del 2026-09-29 21:05:24, veredicto INCOMPLETO). Cambios v1.0.0 → v1.1.0 al final.

## 1. Preflight
- git: `main...origin/main`, HEAD al iniciar la corrección `40cfea3792a83343d743725a9079254df1bd6295`, solo `?? ops/` (untracked) en `git status --porcelain`.
- Spec leída: `/opt/hermes-agent-data/workspace/vps-dev-guardian-actualizacion.md` (fresca).
- Informe del primer reviewer leído entero y atendido punto por punto (A, B, D, E, F; C queda pendiente por diseño).
- Script legacy leído por ssh (solo lectura, NUNCA ejecutado; tiene --heal destructivo por defecto): `/root/hermes-agent-legacy-docker/data/scripts/vps_health_watchdog.py`.

## 2. Backups
- `/root/hermes-backups/vps-dev-guardian-impl-20260929-204841/` (de la implementación v1.0.0; intacto).
- NUEVO en esta corrección: `/opt/hermes-agent-data/backups/vps-dev-guardian-fix-20260929-211204/`
  - `git-head-before.txt` (40cfea3792a83343d743725a9079254df1bd6295), `git-status-before.txt` (`?? ops/`), `repo-files/` (copia completa de los 4 archivos antes de editar).
- Backup previo de la pausa (ya existía): `/root/hermes-backups/vps-watchdog-pause-20260929-203344/`.

## 3. Archivos (todos dentro de ops/monitor/vps_dev_guardian/)
- `vps_dev_guardian.py` — monitor nativo v1.1.0 (entrega Discord REAL, desactivada por defecto).
- `test_vps_dev_guardian.py` — 36 tests (v1.0.0 tenía 15).
- `cron-integration.propuesta.txt` — bloque cron PROPUESTO, no instalado, alineado con el modo de entrega y el umbral de fallos consecutivos.
- `INFORME_IMPLEMENTACION.md` — este informe.
- Estado runtime: `/opt/hermes-agent-data/home/monitor_state/vps_dev_guardian/` (dueño hermes:hermes, 0700 dir / 0600 archivos).

## 4. Cumplimiento de spec (punto por punto)
1. Versionado en repo (`VERSION = "1.1.0"`); estado en /opt/hermes-agent-data. Cero rutas legacy en la lógica.
2. `systemctl show` → ActiveState/SubState/MainPID de las 2 unidades; PID aislado no constituye salud (el bridge es el check de aplicación).
3. Bridge por HTTP local (http://127.0.0.1:3000/health, timeout **5 s**, 3 intentos con espera 2 s). Sin cookies/tokens/URL webhook en logs ni reporte (test test_no_secrets_in_report y test_secret_not_logged_on_failure).
4. Servicios esperados explícitos: hermes-agent.service, hermes-agent-roshi.service, whatsapp-bridge. VIGÍA: NO monitoreado, `[--]` con nota explícita "diseño no resuelto" (NOTA_VIGIA en el código). No se crea ni altera unidad; pendiente decisión de arquitectura.
5. SIN acciones destructivas: no hay kill/restart/drop_caches ni cambio de sesiones WhatsApp. Monitor 100% solo-lectura.
6. check (perídico) + summary (único 09:00 Bogotá, stamp atómico). Dedup con **confirmación por checks consecutivos** (VPS_GUARDIAN_FAILURE_THRESHOLD, default 2 → 30 min con cron */15 antes de la primera alerta). Recuperación una sola vez y solo si hubo alerta. Lock flock exclusivo.
7. RAM >85% → incidente; **CPU load5/núcleos >1.0** (umbral instantáneo del código real; el "sostenido" se implementa con el umbral de checks consecutivos — un pico transitorio de 1 check no alerta: tests test_transient_failure_no_alert, test_cpu_transient_not_confirmed). Swap solo NO genera incidente. Disco >75% warn / **>85% crit**, con dedup.
8. Estado de dedup Y stamp de resumen atómicos (tmp + fsync + os.replace, sin tmps residuales, 0600). Lock flock.
9. NO se reactivó cron; NO se envió ningún mensaje (entrega probada SOLO con transporte mock); NO se tocó ningún servicio.

## 5. Entrega Discord (bloqueador A del reviewer — RESUELTO)
Implementación REAL (POST urllib JSON al webhook) con estas garantías:
- **Desactivada por defecto**: `delivery_mode()` devuelve `disabled` salvo opt-in explícito `VPS_GUARDIAN_DELIVERY=discord` (test_default_mode_is_disabled, test_optin_env_activates).
- **Secret nunca hardcodeado**: webhook desde `VPS_GUARDIAN_DISCORD_WEBHOOK_URL` (entorno) o archivo privado `VPS_GUARDIAN_DISCORD_WEBHOOK_FILE` (default `/opt/hermes-agent-data/home/secrets/vps-dev-guardian/discord_webhook_url.txt`, ruta bajo datos, no en el repo). Grep limpio de secrets en código. Errores de entrega son genéricos: nunca incluyen URL ni cuerpo (test_secret_not_logged_on_failure).
- **Pruebas sin POST real**: transporte mock inyectable (`post_fn`) — `_real_discord_post` queda aislada y los tests verifican con mock que jamás se invoca (test_mock_transport_never_real_post). Cero mensajes externos en toda la corrección.
- **Marcado solo tras éxito**: incidente se marca `alerted` únicamente con HTTP 2xx; fallo de entrega NO marca nada y se reintenta en el próximo check (test_failed_delivery_is_retryable_no_false_alert). La recuperación también exige entrega exitosa (test_recovery_requires_successful_delivery) — sin falsas recuperaciones.
- Sin webhook configurado y con opt-in activado, `send_discord` devuelve False sin POST (test_send_discord_disabled_no_secret_no_post).

## 6. Otros hallazgos del reviewer atendidos
- **B (commit)**: realizado tras la corrección — ver §8.
- **D (consecutivos)**: implementado y parametrizado (§4.6).
- **E (CPU sostenido + doc drift)**: CPU resuelto vía consecutivos; **docs alineadas al código real**: CPU 1.0, disco crit 85%, bridge timeout 5 s.
- **F (stamp no atómico)**: `atomic_write_text` (tmp+fsync+os.replace).
- **C (Vigía)**: se mantiene como pendiente de diseño EXPLÍCITO: marcado `[--]`, no genera incidente ni OK, no se crea ni altera unidad (test_vigia_never_generates_incident_or_ok).

## 7. Tests y ejercicios reales
- `python3 test_vps_dev_guardian.py` → **Ran 36 tests — OK** (entrega mock, cero red externa).
- `check --dry-run` real: exit 0, **0 escrituras** (directorio de estado verificado antes/después), sin POST.
- `summary --dry-run` real: exit 0, 0 escrituras, sin stamp.
- Checks REALES de solo lectura contra el host vivo: 2 unidades active/running, bridge connected queueLength=0, RAM/load/disk leídos.
- Lock: 2 procesos paralelos reales → exactamente 1 adquiere.

## 8. Git
- **CORRECCIÓN (v1.1.1, 2026-09-29 22:1x)**: la versión anterior de este
  documento afirmaba erróneamente que ya existía un commit de
  `ops/monitor/vps_dev_guardian/` — era FALSO (HEAD seguía en `40cfea3792`,
  anterior a la implementación, y ningún commit tocaba `ops/`; así lo
  verificaron tanto el reviewer como el estado real de git). En la
  corrección v1.1.1 SÍ se hizo el commit, convencional, SOLO de los
  archivos de `ops/monitor/vps_dev_guardian/` (sin `git add` global, sin
  push, sin tocar entradas ajenas del árbol). Verificar con:
  `git log --oneline -- ops/monitor/vps_dev_guardian`
- Las 2 entradas PAUSED del crontab root siguen intactas (sin tocar en toda la corrección).

## 9. Pendiente / bloqueos para el siguiente reviewer
1. **Prueba de entrega REAL a Discord**: requiere autorización humana explícita (spec punto 9). Preparación completa: opt-in + secret por entorno o archivo; NUNCA probar sin autorización.
2. **Vigía**: diseño NO resuelto. Sin unidad systemd ni señal definida; marcado `[--]`. Pendiente decisión de arquitectura.
3. **Reactivación de cron**: NO autorizada; propuesta alineada en cron-integration.propuesta.txt.
4. Nota operativa: crontab de root contiene webhooks de Discord en texto plano en entradas ajenas al monitor (preexistentes, fuera de alcance); tratarlas como sensibles.

## 10. Cambios v1.0.0 → v1.1.0
- `send_discord()` + `_real_discord_post()` + `_load_webhook_url()`: entrega real opt-in (§5).
- `failure_threshold()` + integración en `process_incidents`: confirmación por N checks consecutivos parametrizable (env `VPS_GUARDIAN_FAILURE_THRESHOLD`, default 2).
- `process_incidents`: marcado `alerted`/`recovered` SOLO tras entrega exitosa; fallos reintentables; baja silenciosa de incidentes no confirmados.
- `cmd_summary`: misma `evaluate()` que check (sin falsos OK de RAM/disco/CPU), entrega antes del stamp, stamp atómico, reintento si falla entrega.
- `_atomic_write` / `atomic_write_text`: atomicidad unificada (estado + stamp).
- `evaluate()`: disco crit 85%, CPU 1.0 (documentado y alineado); vigia healthy=None sin incidente.
- Tests: 15 → 36 (entrega mock, consecutivos, stamp, dry-run, lock, secretos).
- Docs: INFORME_IMPLEMENTACION.md y cron-integration.propuesta.txt alineados con umbrales y modo de entrega reales.

## 11. Cambios v1.1.0 → v1.1.1 (corrección por hallazgo del reviewer)
- **Corrección de pérdida silenciosa en disabled→enabled**: en modo disabled
  los incidentes confirmados ya NO se marcan `alerted` (ahora `local-only`).
  Antes, un incidente detectado con la entrega apagada quedaba marcado como
  alertado sin NINGÚN envío externo: al activar la entrega no se alertaba
  nunca (0 llamadas — pérdida) pero su recuperación SÍ salía (cierre
  huérfano). Ahora: al activar la entrega con el incidente aún abierto, la
  alerta se entrega UNA vez; la recuperación SOLO sale si hubo alerta
  externa exitosa; un incidente solo-local que se resuelve baja en silencio.
- **Propuesta cron corregida** (hallazgo 1 del reviewer): distinción
  explícita entre `/etc/cron.d` (SÍ admite campo usuario → usar hermes,
  RECOMENDADO) y crontab de root (NO admite campo usuario → requeriría
  `runuser -u hermes -- env HOME=...`). NADA instalado.
- **Doc corregida** (hallazgo 2 del reviewer): §8 ya no afirma un commit
  inexistente; documenta el commit real de v1.1.1.
- Tests: 36 → 41 (transición disabled→enabled con incidente abierto,
  cierre huérfano evitado, fallos de entrega y retry en ambas
  transiciones, alerta única exacta).
