# Fase 2.1 (DEV) — verificación y review

- **Estado:** COMPLETADA · **Host:** DEV `147.93.3.250` · **Fecha:** 2026-11-07
- **Tarjeta kanban:** `t_45411461` (worker `brokkr`, glm5.3-flash) · **Review:** Ragnar
- **Nota de proceso:** el worker sufrió 3 intentos (crash → «Kanban owner refused: Kanban execution unknown» → gave up). El trabajo sustantivo lo completó el intento 2; esta review cerró las 2 lagunas y la verificación final.

## 1. Backup (D-I-V-C)
`/opt/vault/backups/pre-fase2-20261107/`:
- `sync-env.py` (pre: sha256 `72ed81901d63…`)
- `vault-to-env-map.json` (pre: sha256 `7eb89c33c12c…`)
- `hermes-agent-data.env.pre-fase2` (copia del `.env` previo)
- `vault-to-env-map.json.pre-nota` (mapa tras el worker, previo a la corrección de nota)

## 2. Deploy del SSOT
- `/opt/vault/timer/sync-env.py` → sha256 `4b7b2ad27310` = **idéntico** al `scripts/vault-timer/sync-env.py` del worktree (SSOT confirmado).
- `python3 -m py_compile` → OK. `vault-sync.sh` sin cambios.

## 3. Mapa DEV (estado final)
- `targets` (2): `/opt/hermes-agent-data/.env` (`owner: hermes`, `mode 0600`, **9 mappings**) y `/root/.config/cloudflare/credentials.env` (1).
- Los 3 targets con padre inexistente (`/root/activepieces/.env`, `/data/coolify/source/.env`, `/root/marketing-campaign-generator/.env`) quedaron **retirados** y documentados en el campo `note` con fecha y motivo (desviación vs. «mover a `_disabled`» — las copias originales están en el backup; se optó por no reescribir de nuevo un mapa vivo para recuperar entradas inútiles).
- `_disabled` conserva sus 3 entradas preexistentes (golden/paradise landing, neuralcrew).
- JSON válido, temporales `.env-sync-*`: ninguno.

## 4. Integridad del `.env` (prueba por hash, cero valores impresos)
| Métrica | Antes | Después |
|---|---|---|
| Claves totales | 63 | **72** |
| Preexistentes modificadas | — | **0** |
| Preexistentes eliminadas | — | **0** |
| Añadidas (9, exactas del inventario) | — | `FAL_KEY`, `DOCUSEAL_MCP_TOKEN`, `FORMBRICKS_MCP_KEY_RO`, `FORMBRICKS_MCP_KEY_RW`, `STIRLING_MCP_KEY`, `PAPERLESS_MCP_TOKEN`, `COOLIFY_MCP_TOKEN`, `COMPOSIO_KEY`, `NAN_BUILDERS_API_KEY` |
| Modo / owner | 0600 / 10000 | 0600 / 10000 |
| `ML_*` | 0 | **0** (excluidas, sin ítem) |

## 5. Corridas del sincronizador
- 1ª corrida (intento 2): `SUMMARY: ok=2 skipped=0 failed=0`, 9 claves `Updated:`, cloudflare `No changes`.
- 2ª corrida (corrida de verificación vía wrapper, `WRAPPER_RC=0`, 19:07): `SUMMARY: ok=2 skipped=0 failed=0` + **`No changes, skipping restart` en ambos targets** → idempotencia demostrada y `bw logout` limpio.

## 6. Veredicto de review
**APROBADO con 1 desviación documentada** (targets muertos retirados en vez de `_disabled` + `note` no actualizado por el worker; corregido el `note` durante la review con backup previo). La prueba central de la política —que el merge no borra la configuración de Hermes— quedó demostrada: 0 de 63 claves alteradas.
