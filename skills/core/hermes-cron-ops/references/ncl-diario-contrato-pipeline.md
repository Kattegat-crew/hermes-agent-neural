# Pipeline de contrato cross-host DEV→PROD: NCL-DIARIO (validado 03-nov-2026)

Patrón reutilizable para un informe diario consolidado que ensambla bloques de varios hosts sin LLM (0 tokens) y publica un solo mensaje en Discord.

## Piezas

| Rol | Host | Ruta | Disparo |
|---|---|---|---|
| Emisor (bloque DEV) | DEV | `/opt/hermes-agent-data/scripts/ncl_diario_emisor_dev.py` | Job Hermes `50 6 * * *`, `no_agent`, `deliver: local`, `failure_deliver: discord:<hilo-fallos>` (job `b0f1a7318c5b`) |
| Receptor/gate | PROD | `/opt/data/scripts/ncl_diario_receptor.py` (`--check --json`) | invocado por el emisor tras cada push |
| Ensamblador | PROD | `/opt/data/scripts/ncl_diario_ensamblador.py` | Job Hermes `15 7 * * *`, `no_agent`, entrega a hilo `NCL Hoy` (job `10852bff65f4`) |
| Contrato SSOT | PROD | `/opt/data/docs/ncl-diario-contrato-json-v1-SSOT.md` | schema `ncl-diario/dev/1` |
| Intercambio | PROD | `/opt/data/reports/ncl-diario/` (`dev-<jornada>.json`, `dev-latest.json`, `prod-<jornada>.json`, `destino.json`) | |

## Receta del emisor (script puro, sin agente)

1. Recolectar de fuentes locales (jobs.json para crons con `failure_streak`/`last_status` anómalos, `shutil.disk_usage`, `/proc/meminfo`, archivo de pendientes). Reglas de redacción: viñetas `- `, negrita solo en la primera palabra, cap duro 1200 chars (el mensaje total sale <2000).
2. Payload: `{schema, jornada (ayer, TZ America/Bogota), generated_at (con offset -05:00), host, ok, markdown, meta}`.
3. Escritura atómica local: tmp + `os.replace` → `dev-<jornada>.json`, luego symlink relativo `dev-latest.json`.
4. Push a PROD (4 intentos, 300 s entre ellos): `scp` a `.incoming-dev.json` → `ssh` con `mv` atómico al nombre final + `ln -sfn` del symlink + `chown 10000:10000` (el contrato exige owner uid 10000).
5. **Gate obligatorio antes de declarar éxito**: `ssh prod 'python3 <receptor> --check --json'` y exigir `valido: true`; exit 2 si falla (el `no_agent` convierte exit != 0 en alerta al `failure_deliver`).
6. `--dry-run` y `--sin-push` para probar sin efectos.

## Validaciones del receptor (gate)

`schema` correcto, `jornada` == ayer respecto del receptor, `host` esperado, `generated_at` fresco, `markdown_chars` dentro de límites, mtime reciente. Responde `--check --json` con `{valido, motivo, detalle}`.

## Ensamblador (PROD)

Lee `prod-<jornada>.json` + `dev-latest.json` (vía receptor), arma el mensaje único por secciones (Negocio / Flota PROD / Hoy / DEV), entrega a `discord:<thread_id>` y guarda `destino.json` con canal/hilo para auditoría.

## Verificación E2E (lo que se comprobó en vivo)

- Push + gate OK al primer intento; receptor: `valido: true`, `markdown_chars: 79`, `mtime_edad_s: 13`.
- Informe completo ensamblado: 534 chars con bloque DEV real.
- Job disparado con `cronjob_manage action=run`: el archivo se regeneró (`generated_at` nuevo) → el scheduler ejecuta el script de verdad.

## Pitfalls de contexto (ver §20-21 del SKILL.md)

- Probar el ensamblador desde el HOST de PROD da falso positivo: `/opt/hermes/.venv/bin/python3` y los gateways 3000-3002 solo existen/responden DENTRO del contenedor `hermes-agent`. Verificar con `docker exec hermes-agent sh -lc '...'`.
- `failure_deliver` apuntando a un hilo de watchdog genérico mezcla fallos del informe con alertas de infra: usar hilo dedicado.

## Cierre Fase 1: job armado, evidencia y hashes (validado 03-nov-2026)

Protocolo al auditar el pipeline cuando el job ensamblador ya está ARMADO para publicar a futuro:

1. **Estado real del gate de publicación**: leer el job en vivo (`jobs.json`, no el POST): `id 10852bff65f4`, `enabled`, `cron`, `next_run_at`, `script`, `deliver`/`failure_deliver`. Un job con `next_run_at` futuro y `last_run: null` publicará solo — si el OK humano (gate de publicación) no está firmado, PAUSARLO (`enabled=false`, definición intacta): reversible en un comando, a diferencia de un mensaje ya publicado en el canal del cliente.
2. **Qué publicaría, sin publicarlo**: `docker exec hermes-agent /opt/hermes/.venv/bin/python3 /opt/data/scripts/ncl_diario_ensamblador.py --jornada <ayer> --dry-run` — imprime el mensaje y el meta real. NUNCA probar con `--publish` (publica de verdad). El `.sh` del cron solo funciona dentro del contenedor: desde el host da exit 127 (falso negativo, §20 del SKILL.md).
3. **Evidencia y selftests**: tras cualquier fix, re-ejecutar selftest y suite en vivo con exit code explícito (`python3 selftest.py; echo EXIT=$?` — un pipe con `tail` enmascara el código) y regenerar el archivo de evidencia; un `evidencia-fix-*.txt` heredado puede contener el traceback del estado pre-fix (ver §23 del SKILL.md).
4. **Hashes SSOT**: distinguir contrato (`docs/ncl-diario-contrato-json-v1-SSOT.md`) de implementación (`scripts/ncl_diario_ensamblador.py`) — bytes y sha256 se reportan POR ARCHIVO; si no coinciden con lo vivo, revisar mtime antes de gritar corrupción (ver §24 del SKILL.md).
