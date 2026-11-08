# Fase 2.2 (PROD) — verificación

- **Estado:** COMPLETADA · **Host:** PROD `100.73.30.29` (`vmi3513784`) · **Fecha:** 2026-11-07
- **Tarjeta kanban:** `t_593dffc2` (worker `brokkr`) · Parent verificado: F2.1 DEV (`t_45411461`, APROBADO)
- **Alcance:** deploy de `sync-env.py` del SSOT, 2 targets nuevos en el mapa PROD, verificación completa. `vault-sync.sh` sin cambios.

## 1. Backup (D-I-V-C) — `/opt/vault/backups/pre-fase2-20261107/` (0700, root)

`SHA256SUMS` registrado:
```
fe6549fff4a8…  sync-env.py.pre-fase2        (script pre-Fase-1)
d3b34ae2c12c…  vault-to-env-map.json.pre-fase2
56ccf455e538…  hermes-data.env.pre-fase2    (/opt/hermes/data/.env, 44 claves)
9c6766601dcb…  golden-game.env.pre-fase2    (profiles/golden-game/.env, 33 claves)
```

## 2. Deploy del SSOT

- `/opt/vault/timer/sync-env.py` → sha256 `4b7b2ad27310…` **idéntico** al worktree (`scripts/vault-timer/sync-env.py`) y a DEV.
- `python3 -m py_compile` → OK. Suite del worktree: 43 tests OK antes del deploy.
- `vault-sync.sh` sin cambios (sha `91fc59367925…` antes y después).

## 3. Mapa PROD (`/opt/vault/timer/vault-to-env-map.json`)

- Edición atómica (tempfile en el mismo dir + `os.replace`), JSON validado antes y después (`python3 -m json.tool` OK).
- `targets`: 18 → **20** (append al final; verificado `STRUCTURAL_18_UNCHANGED: True` — los 18 preexistentes byte-idénticos por dump JSON canonico).
- **Target nuevo 1:** `/opt/hermes/data/.env` — `mode 0600`, sin `owner`, `restart: null` — 9 mappings del inventario F2.0 (§2, excluye `ML_*`): `FAL_KEY`, `DOCUSEAL_MCP_TOKEN`, `FORMBRICKS_MCP_KEY_RO/RW`, `STIRLING_MCP_KEY`, `PAPERLESS_MCP_TOKEN`, `COOLIFY_MCP_TOKEN`, `COMPOSIO_KEY`, `NAN_BUILDERS_API_KEY ← Terceros/NAN - API Key / NAN_API_KEY`. Las 9 ya existían en el archivo → los mappings reescriben el MISMO nombre (verificado: el conteo quedó en 44).
- **Target nuevo 2:** `/opt/hermes/data/profiles/golden-game/.env` — mismas condiciones — 6 mappings `TWENTY_MCP_KEY_{GOLDEN,GOLDEN_WRITER,LUCKY,LUCKY_WRITER,NC,NC_WRITER}` ← item `Twenty - credentials - prod` (campos custom verificados server-side: nombres exactos, len 444 c/u).
- `note` del mapa: se añadió una línea con fecha/motivo (solo adición).

## 4. Corridas y verificación

| Métrica | 1ª corrida (19:17, wrapper manual) | 2ª corrida (idempotencia) |
|---|---|---|
| `WRAPPER_RC` | 0 | 0 |
| `SUMMARY` | `ok=20 skipped=0 failed=0` | `ok=20 skipped=0 failed=0` |
| `Changed, restarting` | **0** | **0** (20× `No changes, skipping restart`) |

Integridad por hash de línea (sha256 por `KEY=...`, calculado server-side; cero valores impresos):

| Archivo | Claves pre | Intactas | Modificadas | Añadidas | Perdidas |
|---|---|---|---|---|---|
| `/opt/hermes/data/.env` | 44 | **44** | 0 | 0 | 0 |
| `/opt/hermes/data/profiles/golden-game/.env` | 33 | **33** | 0 | 0 | 0 |

Los `Updated:` del log son informativos (se emiten por mapping); el texto final resultó byte-idéntico (los valores en disco ya coincidían con el vault) → el sync confirmó paridad, no introdujo cambios. Modo/owner tras el sync: `0600 10000` en ambos archivos.

## 5. Servicios (sin reinicios provocados)

- Contenedores `Up` sin recrear: ActivePieces (`ap-app/ap-db/ap-redis/ap-worker` Up 2 weeks), Twenty (`twenty-server/redis/db` healthy), `webhook-gateway` y `webhook-paradise` (Up 5 days, healthy), `hermes-agent` (Up 2 days).
- Los 2 `Changed, restarting: webhook-paradise` del log son históricos (líneas 41199/41281 de 202k); ninguna corrida de hoy reinició servicios.

## 6. Desviaciones y notas

1. **Timer no detenido durante el deploy:** el sandbox bloquea `systemctl stop` (comando peligroso sin usuario). Mitigación: escritura atómica del mapa, orden script→mapa (estado intermedio compatible), y el fuego de las 19:14:48 ocurrió antes del deploy. Sin efectos.
2. **`owner` omitido en los 2 targets nuevos:** PROD no tiene entrada passwd para uid 10000 (DEV sí: `hermes`); el script solo advierte si el owner no existe y los archivos ya son `0600 10000`. Diferencia documentada vs. mapa DEV.
3. Temporal de deploy `/tmp/sync-env.py.new` (copia pública del script, sin secretos) quedó en disco — el sandbox también bloquea el `rm`; limpieza pendiente trivial.

## 7. Rollback

```bash
B=/opt/vault/backups/pre-fase2-20261107
cp -a $B/sync-env.py.pre-fase2 /opt/vault/timer/sync-env.py
cp -a $B/vault-to-env-map.json.pre-fase2 /opt/vault/timer/vault-to-env-map.json
cp -a $B/hermes-data.env.pre-fase2 /opt/hermes/data/.env
cp -a $B/golden-game.env.pre-fase2 /opt/hermes/data/profiles/golden-game/.env
chown 10000:10000 /opt/hermes/data/.env /opt/hermes/data/profiles/golden-game/.env
chmod 600 /opt/hermes/data/.env /opt/hermes/data/profiles/golden-game/.env
sha256sum -c $B/SHA256SUMS   # (rutas relativas al dir de backup)
```

`ML_*` sigue excluido (no existe el item en vault — pendiente del Admin, ver `05-inventario-fase2.md` §4).
