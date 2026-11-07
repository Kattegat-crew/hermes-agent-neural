# Design — Fase 1: `scripts/vault-timer/sync-env.py` (SSOT + merge preservativo)

- **Estado:** Approved (2026-11-07) · Spec `01-spec.md` · Tareas `03-tasks.md`

## 1. Ubicación canónica

```
scripts/vault-timer/sync-env.py        # SSOT en Git → se despliega a /opt/vault/timer/ (DEV y PROD)
tests/scripts/test_vault_sync_env.py   # tests deterministas, stdlib unittest (el entorno no trae pytest)
```

`/opt/vault/timer/` **no es un repo** en ninguno de los dos hosts (verificado). El artefacto desplegado
conserva su nombre exacto `sync-env.py` (path duro en `vault-sync.sh` y en docs).

## 2. Superficie del módulo (inyecciones para test)

| Símbolo | Responsabilidad | Inyectable |
|---|---|---|
| `split_eol(line)` | separa cuerpo/terminador (`\n`, `\r\n`, `''`) | — |
| `parse_kv(body)` | regex `^\s*(export\s+)?KEY\s*=` → prefix/key/rest | — |
| `split_value_comment(rest)` | valor vs comentario en línea, **consciente de comillas** | — |
| `merge_env_text(text, updates)` | RF-1..RF-4, función pura | — |
| `extract_field_value(item, field)` | login / campos custom / notes + fallback / card / identity | — |
| `build_updates(target, item_map, warn)` | mappings → dict + warnings | — |
| `atomic_write(path, text, mode, owner, warn)` | RF-6 | `os.replace`, `os.chown` |
| `sync_target(target, item_map, warn, restart_fn)` | 1 target → `ok\|skipped\|failed` | `restart_fn`, `warn` |
| `fetch_items(session, runner)` | `bw list items --session` → `VaultFetchError` | `runner` |
| `main(argv, mapfile, fetch, err, restart_fn)` | ciclo + `SUMMARY` + exit code | todo |

Carga en tests por path (`importlib.util.spec_from_file_location`), porque el archivo desplegado
lleva guion y debe llamarse igual que hoy.

## 3. Algoritmo de merge

```
por línea (con terminador original):
  vacía o comentario '#'                      -> copia literal
  no matchea ^\s*(export\s+)?KEY=             -> copia literal
  KEY no mapeada                              -> copia literal
  KEY mapeada                                 -> prefix + valor_nuevo + comentario_en_línea + eol
                                                 (ocurrencias duplicadas: todas, RF-4)
claves mapeadas ausentes                      -> append al final (añade '\n' previo si falta)
```

**Decisión:** el comentario en línea de una línea mapeada **se conserva**; solo cambia el valor (lo
mapeado). Es lo menos destructivo y cumple «solo cambia lo mapeado».

**Decisión:** escritura atómica con `tempfile.mkstemp(dir=dirname)` (nace 0600) → `chmod` al modo del
target → `chown` opcional → `os.replace`; `finally` desvincula el temporal si algo falla.

## 4. Flujo por target

```
¿existe y es dir el padre?  --no--> SKIPPED
texto = lee ("" si no existe)
updates = build_updates(...)          # item/field ausente = WARNING, no rompe
nuevo = merge_env_text(texto, updates)
¿idéntico?  -> ok, sin escritura ni restart
distinto    -> atomic_write -> FAILED si OSError -> restart_fn SOLO si cambió
```

## 5. Compatibilidad y rollback

- `vault-sync.sh` **no cambia** en ningún host.
- Salida conservada: `Processing:`, `WARNING:`, `Updated:`, `DONE:<file>`, `SKIPPED:`, `FAILED:` y `SUMMARY: ok=N skipped=N failed=N` (contrato de `/var_log/vault-sync.log`).
- Rollback: `cp /opt/vault/backups/sync-env.py.bak-<fecha>-pre-fase1 → /opt/vault/timer/` + `git revert` en la rama. En Fase 1 **no** se toca ningún host.

## 6. Riesgos

| Riesgo | Mitigación |
|---|---|
| Clave vieja residual por duplicado | RF-4 testeada (AC-6) |
| Temporal huérfano si matan el proceso | `finally` + unlink; prefijo `.env-sync-*` |
| DEV pasa de «reiniciar siempre» a «solo si cambió» | AC-5; menos reinicios = menos riesgo |
| Heurística de comentario en línea dentro de comillas | scan consciente de comillas, testeado |
| Secretos en fixtures | valores ficticios (02-vps-guardrails §2) |
| **H7 (riesgo aceptado):** un valor que contenga ` # ` o espacios extremos se escribe SIN quoting: un parser dotenv aguabajo podria truncarlo. No es regresión (el script viejo escribía crudo igual) y ninguno de los .env reales de PROD tiene valores así hoy; si aparece, se cotiza quoting por target. |
| **Symlink:** si el `.env` es un enlace, se escribe a través de él (`realpath`) — `os.replace` sobre el propio link lo reemplazaría por un archivo regular y rompería el mount (hallazgo H2, corregido con test `test_h2_symlink_env_is_written_through`). |

## 7. Observabilidad

Mismo contrato de log + `SUMMARY` también en PROD (hoy solo DEV): es la línea con la que se detecta
un run caído (lección del outage 04→15-sep-2026).
