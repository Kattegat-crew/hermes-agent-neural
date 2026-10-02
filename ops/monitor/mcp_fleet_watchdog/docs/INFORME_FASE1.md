# FASE1 — Watchdog MCP: clasificación veraz (informe de implementación)

Fecha: 2026-09-29 · Autor: subagente FASE1 · Base: main @ `40cfea3792a83343d743725a9079254df1bd6295`
Estado: **implementado y probado, SIN desplegar** (runtime activo intacto, espera revisión).
Segunda iteración: corrige FAIL del revisor (F1–F4, 2026-09-29) — ver sección
"Corrección post-revisión FAIL" más abajo.

## Alcance cumplido (y límites respetados)

Implementa SOLO FASE1 sobre una copia nueva en el subtree git dedicado
`ops/monitor/mcp_fleet_watchdog/`. No se tocó: el script cron activo
(`/opt/hermes-agent-data/scripts/mcp_fleet_probe.py` y su wrapper), cron
11f0076ce55c, config, gastos, conexiones reales, ni lógica de heal. Sin fase 2.

## Preflight (verificado con comandos reales)

- Repo `/opt/hermes-agent`: rama `main`, HEAD `40cfea3` (completo arriba), remoto
  `origin = /root/hermes-agent-legacy-docker`. `git status` previo: solo `?? ops/`.
- `ops/monitor/vps_dev_guardian` (AJENO): no tocado, no staged — sigue sin trackear.
- Backups FASE0 (`/opt/hermes-agent-data/home/monitor_state/fase0_watchdog_backup/20260929_2103/`)
  vs discos actuales:
  - `mcp_fleet_probe.py`: `32f24fe7…835afe17e83b39f48770e6c0f2b0e7820e43a806e59b5c16` (idéntico backup/actual)
  - `mcp_fleet_watchdog.sh`: `68872961…bac47a2d0ce3f76bd81cb7d8622d291b9c0a9d068` (idéntico backup/actual)
- Copia inicial al subtree con los mismos hashes (trazabilidad 1:1 con FASE0).

## Archivos del subtree (SOLO FASE1, nuevos, aún untracked)

| Ruta | Qué es |
|---|---|
| `ops/monitor/mcp_fleet_watchdog/mcp_fleet_probe.py` | Copia FASE0 + cambios FASE1 (único archivo modificado respecto al original) |
| `ops/monitor/mcp_fleet_watchdog/mcp_fleet_watchdog.sh` | Copia idéntica al original (sin cambios; se conserva interfaz para fases 2/3) |
| `ops/monitor/mcp_fleet_watchdog/tests/__init__.py` | Paquete de tests |
| `ops/monitor/mcp_fleet_watchdog/tests/test_mcp_fleet_probe.py` | 42 tests unitarios SIN red real (24 originales + 18 de regresión adversarial F1–F4) |
| `ops/monitor/mcp_fleet_watchdog/docs/fase1_diff_vs_original.patch` | diff `--no-index` original→FASE1 (516 líneas, regenerado tras fix revisión) |
| `ops/monitor/mcp_fleet_watchdog/docs/fase1_test_output.txt` | Salida completa de la suite (42/42 OK) |
| `ops/monitor/mcp_fleet_watchdog/docs/INFORME_FASE1.md` | Este informe |

## Clasificación FASE1 (reglas implementadas y testeadas)

`STATES = HEALTHY | DEGRADED | FAILED | UNVERIFIED`; función pura `classify()` (línea ~77)
+ `validate_args_against_schema()` + `apply_verdict()` + `call_tool_checked()` +
`evaluate_on_session()` + `probe()` reescrito. Reglas (todas cubiertas por tests):

- **R1** Error de la tool de sonda → NUNCA HEALTHY. `APP_ERROR` → DEGRADED.
- **R2** Sonda ausente en el catálogo real → UNVERIFIED (nunca HEALTHY).
- **R3** Args de sonda validados con `jsonschema` contra el `input_schema` REAL que
  anuncia el server; inválidos → UNVERIFIED (no se llama la tool).
- **R4** `pg_ro`: `execute_sql {"sql": "select 1 as ok"}` es OBLIGATORIA
  (`REQUIRED_PROBES`); su éxito con EVIDENCIA del resultado (fila con valor 1,
  ver `REQUIRED_EVIDENCE`) es condición necesaria para HEALTHY. Si el server
  responde con error de tool → DEGRADED (nunca HEALTHY); sin llamada posible →
  UNVERIFIED; protocolo OK pero cuerpo sin evidencia (vacío, no-JSON, `ok=0`)
  → DEGRADED (nunca HEALTHY).
- **R5** Fallo de conexión/`initialize`/`list_tools`, o catálogo con 0 tools → FAILED.
- **R6** Auth rota (regex AUTH_RE sobre el texto del error, incl. `APP_ERROR`
  con 401/403/expired) → FAILED.

Robustez adicional: `timeout` de `call_tool` → FAILED; excepción de la propia
sonda → FAILED (`CRASH`); resultado sin veredicto explícito → UNVERIFIED (jamás
se asume HEALTHY por defecto). Errores de teardown del transporte (TaskGroup mcp 2.x)
post-veredicto no contaminan el resultado. Ruta OAuth-vía-CLI: handshake OK →
UNVERIFIED (sin sonda operativa no hay HEALTHY; fallo de handshake → FAILED).

## Corrección post-revisión FAIL (2026-09-29, segunda iteración)

El revisor independiente (INFORME_REVISION_FASE1.md en
`/opt/hermes-agent-data/home/monitor_state/fase1_review_20260929/`) confirmó 4
falsos HEALTHY estructurales. Correcciones aplicadas (todas cubiertas por tests
de regresión en la clase `TestAdversarialFASE1Fix`):

- **F1** `call_tool_checked()`: además de `is_error`, el CUERPO textual se
  analiza como JSON semántico (`_analyze_body_text` + `_walk_ok_false`):
  `{"ok": false}` / `{"success": false}` / envelope con `error` explícito →
  AUTH (si el error es 401/auth) o APP_ERROR. Conservador: nunca por regex
  amplia — datos legítimos del cliente (`{"ok": 0, "count": 0}`, texto que
  menciona "error", 401 en un comentario) NO se marcan.
- **F2** `REQUIRED_EVIDENCE` (por nombre de tool): para `execute_sql` el cuerpo
  debe evidenciar la fila del SELECT 1 con valor 1 (`_evidence_select1`).
  Cuerpo vacío / no-JSON / 0 filas / `ok=0` → sin evidencia → DEGRADED,
  NUNCA HEALTHY. `{"rows":[{"ok":1}]}`, `{"ok":1}`, `[[1]]` sí son evidencia.
- **F3** `structuredContent` con error tiene PRIORIDAD sobre content textual
  (`_structured_error`, con alias snake `structured_content` del SDK mcp 2.x):
  un server con `structuredContent={"ok":false}` + content "ok" + is_error
  False sale FAILED/DEGRADED, jamás HEALTHY.
- **F4** `main()` ruta OAuth-vía-CLI: handshake OK → UNVERIFIED (jamás
  HEALTHY); fallo de handshake → FAILED. Extraído a función pura
  `_oauth_handshake_verdict()` testeable sin red.

Resultados post-fix: suite oficial 42/42 OK; `adversarial2.py` del revisor
5/5 ok (0 falsos HEALTHY); `adversarial_probe.py` 8/9 (el único hallazgo es
su caso A9 con `/bin/true`, que no es un server MCP y mide conexión-fallida
pre-catálogo — la preservación de veredicto ante teardown-error está cubierta
por `test_a9_teardown_error_preserva_veredicto` con `/bin/false`, PASS).

## Tests (SIN red real)

24 tests originales + 18 de regresión adversarial = **42 tests**: 12 de
`classify()` (pura), 5 de `validate_args_against_schema()`,
7 end-to-end de `evaluate_on_session()`/`probe()` contra un servidor MCP
**en memoria** (`MCPServer` + `InMemoryTransport` de mcp 2.x — sin sockets ni
procesos; el único subprocess es `/bin/false` para el caso conexión-fallida),
y 18 de regresión de los vectores adversariales del revisor (F1–F4, clase
`TestAdversarialFASE1Fix`).

Comando y resultado:

```
cd /opt/hermes-agent/ops/monitor/mcp_fleet_watchdog
MCP_PROBE_CONFIG=/tmp/fase1_fix_empty_config.yaml \
  /opt/hermes-agent/.venv/bin/python -m unittest discover -s tests -v
...
Ran 42 tests in 0.963s
OK
```

Salida completa: `docs/fase1_test_output.txt`.

## Diff / evidencia para el revisor

- Diff completo original→FASE1: `docs/fase1_diff_vs_original.patch`
  (generado con `git diff --no-index /opt/hermes-agent-data/scripts/mcp_fleet_probe.py mcp_fleet_probe.py`).
- Wrapper `.sh`: sin diferencias (`git diff --no-index` vacío).
- Runtime activo verificado INTACTO tras todos los cambios:
  `sha256sum /opt/hermes-agent-data/scripts/mcp_fleet_probe.py` → `32f24fe7…` (igual a backup FASE0)
  `sha256sum /opt/hermes-agent-data/scripts/mcp_fleet_watchdog.sh` → `68872961…` (igual a backup FASE0)
- `git status --porcelain` al cierre: solo `?? ops/` (todo el subtree untracked;
  nada stageado, ningún commit hecho, ningún archivo ajeno tocado).

## Notas para fases siguientes (sin implementar nada aquí)

- Interfaces conservadas: `--verbose/--json/--only/--no-heal`, estado en
  `/opt/hermes-agent-data/state/mcp-watchdog-state.json`, `verdict`/`reason`
  como campos nuevos aditivos (compatibles con el wrapper y el cron actual).
- Despliegue al runtime (copiar subtree→`/opt/hermes-agent-data/scripts/`), cron,
  heal y conexiones reales quedan explícitamente FUERA de FASE1.

---

# FIX3 (post-revisión2) — 2026-09-29

Corrige los 2 bloqueantes del informe `INFORME_REVISION_FASE1_REVISION2.md` (solo eso; sin desplegar, sin fase2):

## B-F1: `_walk_ok_false` — error explícito como señal independiente
`'error'` no vacío (`!= None/""/[]/{}/False`) ahora detecta fallo en cualquier nivel, aunque el envelope no declare `ok:false` (credenciales muertas con envelope de error puro). `'error': null`, `""`, `[]`, `{}` y `{"errors": []}` siguen sin contar. `{"error": "boom"}` → DEGRADED; `{"error": {"code": 401, ...}}` → FAILED.

## B-F2: `_evidence_select1` — clave `ok` entero EXACTO 1
Helper `_es_uno(v)`: `type(v) is int and v == 1`. bool `true` NO cuenta (ni top-level ni en fila); `"1"`/`1.0` tampoco. Sólo la clave `ok` es evidencia (campos arbitrarios `page`/`total`/`count` no); contradicción explícita `ok: 0/false` rechaza aunque exista otro 1. `{"rows":[{"ok":1}]}`, `{"ok":1}` y `[[1]]` siguen siendo evidencia.

## Regresiones (+11 → 53 tests)
Los 6 vectores falsos-HEALTHY de revisión2 + 3 controles legítimos, en unit y E2E (server MCP en memoria), más 2 tests unitarios de borde (`"1"`, `1.0`, bool, contradicciones). El test A9 antiguo (excepción simulada dentro de evaluate, medio débil) fue REEMPLAZADO por la variante válida del revisor2: server MCP stdio REAL con teardown explosivo del TaskGroup tras aplicar el veredicto — DEGRADED se preserva, control HEALTHY también.

## Verificación (fresca, sin red)
- Suite: **53/53 OK** (`python -m unittest discover -s tests`, 3.0s; cero URLs http en código y tests).
- 6 vectores reviewer2: 0 falsos HEALTHY (unit + E2E); controles 3/3 HEALTHY sin falsos FAILED.
- A9 válido: 2/2 PASS.
- Runtime `/opt/hermes-agent-data/scripts/` intacto (`32f24fe7…`), repo `main` sin commit, staged=0, único cambio `?? ops/monitor/mcp_fleet_watchdog/`.

## Evidencia
`/opt/hermes-agent-data/home/monitor_state/fase1_fix3_evidencia_20260929/` — `INFORME_FIX3_FASE1.md`, diffs vs backup pre-patch (`../fase1_fix3_backup_20260929_2230/`), salidas postfix E2E/A9/suite, checksums.
