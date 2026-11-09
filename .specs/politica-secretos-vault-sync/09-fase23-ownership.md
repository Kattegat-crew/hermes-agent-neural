# Verificación Fase 2.3 — ownership: `atomic_write` preserva uid/gid + owner explícito en mapa PROD

- **Fecha de verificación:** 2026-11-09 (America/Bogota; lecturas host 15:55–16:00 -05)
- **Verificador:** Brokkr · **Implementador del fix:** run anterior de Brokkr (crash 2026-11-07) · **Re-review independiente:** Ragnar (2026-11-09)
- **Estado:** fix YA DESPLEGADO y verificado funcionalmente; **commit del informe pendiente de autorización explícita** (`commit_status=not_authorized`).
- **Alcance:** cierre documental y evidencia. No se reimplementó el fix, no se tocó código Python, no se hizo deploy, ni rotaciones, ni chmod/chown de destinos, ni sync manual.

## 1. Versión y superficie del fix

- **Rama:** `feat/politica-secretos-vault-sync` · **Commit:** `df25cad5ebdfdab65d867f9852de214bca9b05d5`
  - Mensaje: `fix(vault-sync): preservar uid/gid del .env existente en atomic_write (F2.3)`
  - Diff: `scripts/vault-timer/sync-env.py` (+48/−5) y `tests/scripts/test_vault_sync_env.py` (+124)
- **Worktree:** `/opt/hermes-agent-data/fleet/worktrees/hermes-agent/politica-secretos` — árbol **limpio** antes y después de la suite (`git status --porcelain` vacío; `git diff --check` exit 0, verificado 2026-11-09 15:53 -05).
- **Comando:** `git log -1 --stat`, `git status --porcelain`, `git diff --check` (salidas íntegras y sanitizadas).
- **Función afectada:** `atomic_write(path, text, mode="0600", owner=None, warn=None)` (línea 204) + helper `_explicit_owner_ids` (línea 182) + `import pwd`.
- **Semántica implementada (F2.3):**
  1. Sin `owner` en el mapa → se **preserva** el uid/gid actual del archivo existente (`os.stat` antes del `os.replace`).
  2. `owner` en el mapa → **override explícito** (nombre vía `pwd.getpwnam` o uid numérico; el numérico cubre contenedores sin entrada en passwd del host).
  3. Archivo inexistente → uid del escritor (comportamiento previo).
  4. `owner` no resoluble → WARNING y preservación del ownership actual.
- **`.atl/skill-registry.md`:** **AUSENTE en este checkout** (verificado `ls .atl` → no existe). Se usó solo como enrutamiento el manifiesto canónico `/opt/hermes-agent/.atl/skill-registry.md`, sin copiarlo ni arreglarlo. Skills cargadas desde `.agents/skills/`: `python-testing-patterns`, `code-review-and-quality`.

## 2. Pruebas RED históricas (verificables, con discrepancia declarada)

- **Mensaje del commit** afirma RED como «3 failures + 1 error» (el error = `NameError` por `import pwd` faltante) y GREEN «51/51 OK».
- **Re-review independiente (Ragnar, 2026-11-09, en scratch):** reprodujo **3 failures y 0 errors** contra el código base. El alegado cuarto `NameError` **NO se reprodujo**.
- **Decisión documental:** se registra la discrepancia como evidencia no verificada; este informe **no afirma** el cuarto error. RED verificado hoy reproducible: 3 failures de ownership contra el código base del commit anterior (`bad72745218`). La atribución de `import pwd` como fix latente es correcta por lectura del código (sin el import, `_explicit_owner_ids` no puede resolver owners por nombre), pero la forma exacta en que falló la corrida RED original no se reproduce hoy.

## 3. Pruebas GREEN — reejecución de hoy (2026-11-09 15:53–15:54 -05)

- **Comando (el único permitido):**
  ```
  cd /opt/hermes-agent-data/fleet/worktrees/hermes-agent/politica-secretos
  env -u PYTHONPATH \
      HERMES_HOME=<scratch>/f23-evidence/home \
      HERMES_RUNTIME_DIR=<scratch>/f23-evidence/runtime \
      XDG_CACHE_HOME=<scratch>/f23-evidence/cache \
      TMPDIR=<scratch>/f23-evidence/tmp \
      PYTHONDONTWRITEBYTECODE=1 \
      scripts/run_tests.sh tests/scripts/test_vault_sync_env.py -q
  ```
  (scratch = `/opt/hermes-agent-data/profiles/brokkr/cache/scratch/`; no pytest/unittest directos, sin instalar deps, sin suite global.)
- **Resultado: `49 passed, 0 failed, 2 skipped` (51 tests coleccionados) — exit 0.** Los 2 skips son los casos root-only (el usuario de pruebas no es root). **NO se presenta esto como «51 ejecutadas con éxito».**
- Tests de ownership incluidos en la suite (clase `OwnershipTests` y afines, 9 casos: `test_atomic_write_preserves_current_owner_without_map_owner`, `test_atomic_write_missing_file_keeps_writer_uid`, `test_atomic_write_map_owner_overrides`, `test_atomic_write_numeric_owner_without_passwd_entry`, `test_sync_target_preserves_owner_end_to_end`, `test_sync_target_map_owner_wins_over_preservation`, `test_sync_target_preserves_foreign_owner_on_disk`, `test_atomic_write_numeric_owner_real_without_passwd_entry`, `test_missing_owner_warns_but_writes`).
- Fixtures: solo temporales ficticios en scratch con limpieza controlada; **cero secretos reales como fixtures**.

## 4. Hash del script — SSOT idéntico en las 3 superficies

SHA-256 de `scripts/vault-timer/sync-env.py` / `/opt/vault/timer/sync-env.py`:

| Superficie | SHA-256 | Fecha lectura |
|---|---|---|
| Worktree (df25cad5) | `bd22abe795177c833b9d39b7eb042fe58d27a658573c3ad8ca969d45799e6166` | 2026-11-09 15:50 -05 |
| DEV (`vmi3151337`, 147.93.3.250) | `bd22abe795177c833b9d39b7eb042fe58d27a658573c3ad8ca969d45799e6166` | 2026-11-09 15:55 -05 |
| PROD (`vmi3513784`) | `bd22abe795177c833b9d39b7eb042fe58d27a658573c3ad8ca969d45799e6166` | 2026-11-09 15:55 -05 |

`stat` script (ambos hosts): `755 root:root`, 16233 bytes, mtime 2026-11-07 19:42 (deploy de F2.3).

## 5. Mapas y stat de destinos (paths/owner/mode; sin valores de claves)

### DEV — `/opt/vault/timer/vault-to-env-map.json` (2 targets, 644 root:root, mtime 2026-11-07 19:06)

| Target | owner en mapa | stat observado |
|---|---|---|
| `/opt/hermes-agent-data/.env` | `hermes` | `600 hermes:hermes` |
| `/root/.config/cloudflare/credentials.env` | (sin owner → preservación) | `600 root:root` |

### PROD — `/opt/vault/timer/vault-to-env-map.json` (20 targets, 644 root:root, mtime 2026-11-07 19:42)

- **18 targets sin `owner`** (activepieces, formbricks, langfuse, twenty, outline, paperless, pocket-id, webhook-gateway ×3, nginx-proxy-manager ×2, infra, twenty/.redis, paperless/.redis, outline/.redis, `/opt/hermes/.env`) → stat observado `600 root:root` en los 18: **preservación funcionando** (el escritor es root y los archivos ya eran root:root).
- **2 targets nuevos con `owner: 10000`**: `/opt/hermes/data/.env` (9 mappings) y `/opt/hermes/data/profiles/golden-game/.env` (6 mappings) → stat observado **`600 UNKNOWN:UNKNOWN`** (uid/gid = 10000 sin entrada en passwd del host — exactamente el caso que motiva el owner numérico; contenedor Hermes uid 10000 con acceso de lectura garantizado).

## 6. Timer, servicio y último SUMMARY (lectura 2026-11-09)

| | DEV | PROD |
|---|---|---|
| `vault-sync.timer` | `active` (última corrida 15:44:52, próxima 16:14:52 -05) | `active` (última 15:50:04, próxima 16:20:04 -05) |
| `vault-sync.service` Result | `success`, `ExecMainStatus=0` (15:45:17) | `success`, `ExecMainStatus=0` (15:50:32) |
| Último SUMMARY (`/var/log/vault-sync.log`) | `SUMMARY: ok=2 skipped=0 failed=0` — `DONE` en ambos targets, repetido en cada corrida de hoy | `SUMMARY: ok=20 skipped=0 failed=0` — `DONE` en los 20 targets, incluidos `/opt/hermes/data/.env` y `/opt/hermes/data/profiles/golden-game/.env` |

No se disparó sincronización manual ni se forzó el timer: la evidencia proviene de las corridas programadas de hoy.

## 7. Backups / rollback existentes

- **DEV** `/opt/vault/backups/`: `pre-fase2-20261107/` y `pre-fase23-20261107/` (creado 2026-11-07 19:42), además de históricos `sync-env.py.bak-20260915*` y `vault-to-env-map.json.bak-20260915*` / `bak-20260929-pre-nca-removal`.
- **PROD** `/opt/vault/backups/`: `pre-fase2-20261107/` y `pre-fase23-20261107/` (2026-11-07 19:42).
- No se crearon backups nuevos (no hubo deploy en esta verificación).

## 8. Aceptaciones host-side SIN evidencia directa (declaración explícita)

1. **Escritura real controlada sobre un destino con owner preservado en PROD:** no se ejecutó ninguna prueba de escritura deliberada contra destinos reales (prohibido por la tarjeta). La evidencia de preservación en hosts es **indirecta**: 18 corridas `DONE` sobre targets root:root que siguen `600 root:root` tras ≥6 corridas de hoy, y los 2 targets owner-10000 que conservan uid/gid 10000 desde el deploy de F2.3. Solo la suite aislada (scratch) ejercita el camino de escritura directamente.
2. **RED histórico completo (4 fallos):** no reproducible hoy; se conserva solo «3 failures, 0 errors» (ver §2).
3. **Restart de servicios tras cambio:** no se observó ninguna rotación de clave real en las corridas de hoy (los `.env` no cambiaron de mtime por contenido nuevo), por lo que la ruta `restart:` de PROD no se ejercitó en vivo; su verificación unitaria sí está en la suite.

## 9. Límites respetados y estado del commit

- No se modificó ningún código Python ni mapa; no `pull`/`rebase`/`cherry-pick`; no se tocó el repo principal ni otras ramas.
- Sin rotaciones, sin sync manual, sin chmod/chown de destinos, sin cambios de servicios/gateway/config, sin tocar cuentas Vault, WhatsApp, Langfuse o APIs pagas. No se leyeron valores de claves, tokens, `.env` ni sesiones (solo hashes, stat, paths y owners).
- **Commit del informe: PENDIENTE de autorización explícita** (`commit_status=not_authorized`). Este archivo está en el árbol de trabajo sin trackear; no se hizo `git add`/`commit`/`push`/`merge`.
- `future_spend_authorized=false`. F3 permanece dependiente; F4/F5 siguen aparcadas.
