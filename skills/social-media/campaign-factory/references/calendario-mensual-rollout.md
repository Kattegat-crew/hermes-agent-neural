# Rollout mensual del calendario de campañas (m-c-g)

Procedimiento verificado E2E el 08-oct-2026 (sep→oct, expediente «Sorteo del Terror», 62 piezas). Se repite cada mes para el expediente nuevo.

## Pasos
1. **Replicar expediente**: copiar `planning/calendario-<mes-prev>/` completo → `planning/calendario-<mes-nuevo>/` (~12 scripts: publish.py, cron_publish_due.py, cron_daily_package.py, cron_harvest.py, sync_from_drive.py, drive_xlsx.py, approve_ids.py, republish_ig.py, repair_drift_publicado.py, build_xlsx.py).
2. **Repoint interno**: en cada script del expediente nuevo reemplazar el nombre del directorio anterior en los TARGET hardcodeados (p. ej. `calendario-sep2026` → `calendario-oct2026`). Verificar con py_compile.
3. **Wrappers de cron**: repuntar los 3 de `/opt/data/scripts/` (`calendario_publish_due.sh`, `calendario_daily_package.sh`, `calendario_harvest.sh`) — tienen el directorio fijo. Backup `.bak-<fecha>` de cada uno antes.
4. **XLSX**: generar con `build_xlsx.py` (el nombre de HOJA hereda del mes anterior por el builder — corregirlo). Subir a las 2 carpetas canónicas de Drive del mes (una por marca) con la credencial de la cuenta DUEÑA de las carpetas; verificar con `files().get` leyendo de vuelta.
5. **Cablear IDs** de los XLSX nuevos en `drive_xlsx.py` y `sync_from_drive.py` del expediente nuevo.
6. **Prueba E2E**: correr `sync_from_drive.py` (esperado: 0 cambios) + un tick completo de `cron_publish_due.py` con salida y código de salida visibles (exit 0 sin publicar = correcto si todo está `listo_para_aprobacion`).
7. **Pre-flight git**: `find <repo>/.git -not -user hermes | wc -l`; si hay objetos root → `ssh root@147.93.3.250 'chown -R hermes:hermes <repo>/.git'`. NOTA: `docker exec` desde el contenedor falla (socket denegado) y el alias `ssh dev` puede colgar — usar la IP directa. Commit + push con verificación hash local == `git ls-remote`.
8. **Lint de copys antes de activar**: montos (`$\d+(\.\d{3})+`), vocabulario vetado del campaign.yaml, frases requeridas (`+18`, nombre de la campaña). Lint determinista ANTES de cualquier gate LLM.

## Reglas duras aprendidas
- El publicador NO tiene catch-up: un calendario que arranca en fechas ya pasadas pierde las piezas vencidas. Re-fecharlas ANTES de activar, dejando ventana suficiente para la aprobación del paquete diario (7:30 am) antes de cada slot.
- Formato JSONL: carrusel usa `slides`; story usa `asset_drive_id` único con slots 12:00; los IDs deben ser estrictamente únicos (un duplicado rompe sync/publicación).
- Circuito Drive↔JSONL: el Admin edita el XLSX directo en Drive; `sync_from_drive` solo aplica Estado/Copy/Hashtags/Portada/Nota y SUS ediciones mandan (difflar antes de regenerar y subir).
- Guiones de reels: espina 30 s de 4 beats (HOOK 0-3 / PROBLEM 3-8 / SOLUTION 8-22 / CTA 22-30), ≤85 palabras de narración, sin montos, +18 en cierre, tuteo colombiano. Entregable: MD por marca en el expediente + copia en la subcarpeta `02-Guiones` de Drive.
- Todo flujo que toque el repo como root debe restaurar ownership `hermes:hermes` al terminar (patrón del 28-sep: archivos root tumbaron el publicador).
