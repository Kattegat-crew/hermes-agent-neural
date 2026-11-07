# Inventario Fase 2.0 — items y campos exactos del vault + claves reales en disco

- **Estado:** Completo (solo lectura; cero mutaciones en hosts, cero valores de secreto en este documento)
- **Autor:** Brokkr · **Fecha:** 2026-11-07 · **Fuente:** `docs/POLITICA-SECRETOS-Y-SERVICIOS.md` §6.1 y §6.2
- **Worktree:** `politica-secretos` · **Rama:** `feat/politica-secretos-vault-sync`
- **Método de verificación:** `vw list` + `vw get "<item>" --json` (PROD `100.73.30.29`, helper `/usr/local/bin/vw`), parseado server-side emitendo solo **nombre de campo + longitud del valor**. Lado disco: `grep -cE '^<KEY>='` sobre cada `.env` (solo nombres de clave, nunca valores). Las longitudes se documentan como fingerprint no-confidencial para detectar rotaciones.

## 1. Destinos auditados

| Host | Archivo | Claves (conteo verificado) |
|---|---|---|
| DEV `147.93.3.250` | `/opt/hermes-agent-data/.env` | 63 |
| PROD `100.73.30.29` | `/opt/hermes/data/.env` | 44 |
| PROD `100.73.30.29` | `/opt/hermes/data/profiles/golden-game/.env` | 33 |

## 2. Tabla de inventario (mapa del sincronizador)

Columnas: ¿vault? = item verificado con `vw list`/`vw get`; ¿en .env? = presencia de la clave verificada con `grep -cE '^KEY='`.

| env_key | item exacto (vault) | field exacto (vault) | ¿vault? | ¿en .env? | host(s) |
|---|---|---|---|---|---|
| `FAL_KEY` | `FAL - API key` | `FAL_KEY` (custom, len 69) | ✅ | DEV: no · PROD root: **sí** | DEV + PROD |
| `DOCUSEAL_MCP_TOKEN` | `DocuSeal - MCP token` | `DOCUSEAL_MCP_TOKEN` (custom, len 43) | ✅ | DEV: no · PROD root: **sí** | DEV + PROD |
| `FORMBRICKS_MCP_KEY_RO` | `Formbricks - MCP keys` | `FORMBRICKS_MCP_KEY_RO` (custom, len 47) | ✅ | DEV: no · PROD root: **sí** | DEV + PROD |
| `FORMBRICKS_MCP_KEY_RW` | `Formbricks - MCP keys` | `FORMBRICKS_MCP_KEY_RW` (custom, len 47) | ✅ | DEV: no · PROD root: **sí** | DEV + PROD |
| `STIRLING_MCP_KEY` | `Stirling-PDF - MCP API key` | `STIRLING_MCP_KEY` (custom, len 36) | ✅ | DEV: no · PROD root: **sí** | DEV + PROD |
| `PAPERLESS_MCP_TOKEN` | `Paperless - MCP token` | `PAPERLESS_MCP_TOKEN` (custom, len 40) | ✅ | DEV: no · PROD root: **sí** | DEV + PROD |
| `COOLIFY_MCP_TOKEN` | `Coolify - MCP API token` | `COOLIFY_MCP_TOKEN` (custom, len 48) | ✅ | DEV: no · PROD root: **sí** | DEV + PROD |
| `COMPOSIO_KEY` | `Composio - credentials - prod` | `COMPOSIO_KEY` (custom, len 23) | ✅ | DEV: no · PROD root: **sí** | DEV + PROD |
| `NAN_BUILDERS_API_KEY` | `Terceros/NAN - API Key` | `NAN_API_KEY` (custom, len 25) | ✅ | DEV: no · PROD root: **sí** · golden-game: **sí** | DEV + PROD (2 archivos) |
| `ML_CLIENT_ID` | — (no existe) | — | ❌ | no | DEV + PROD |
| `ML_CLIENT_SECRET` | — (no existe) | — | ❌ | no | DEV + PROD |
| `ML_REFRESH_TOKEN` | — (no existe) | — | ❌ | no | DEV + PROD |

Resumen del mapa: **9 env_keys resolubles hoy** contra 7 items del vault (Formbricks aporta 2, NAN aporta 1 con renombre). **3 env_keys `ML_*` pendientes** de crear el item en vault con las credenciales de la app de ML del Admin.

## 3. Resolución NAN: nombre real del item

- El documento §6.2 dice `Terceros/IA - NAN - API Key` → **NO existe**: `vw get "Terceros/IA - NAN - API Key"` → `ERROR: Item ... not found in vault.`
- El nombre real es **`Terceros/NAN - API Key`** (verificado, id `421d2c02-…`, tipo secureNote): aporta `NAN_API_KEY` (custom, len 25) más metadatos `DEEPSEEK_API_URL` y `DEEPSEEK_MODEL` (campos informativos, no secretos).
- Colisión resuelta: en PROD la clave ya existe con el nombre **`NAN_BUILDERS_API_KEY`** (root y golden-game, 1 ocurrencia cada uno). El mapa debe declarar `NAN_BUILDERS_API_KEY ← Terceros/NAN - API Key / NAN_API_KEY`; **nunca** crear una segunda clave `NAN_API_KEY=` en el `.env`.

## 4. Pendientes (Mercado Libre)

- **No existe ningún item de Mercado Libre en el vault** (búsqueda en `vw list` y probe directo: `not found`).
- `ML_CLIENT_ID`, `ML_CLIENT_SECRET`, `ML_REFRESH_TOKEN`: ausentes en los 3 `.env` auditados (0 ocurrencias).
- Acción posterior (fuera de F2.0, requiere mutación de vault): crear el item (sugerencia de nombre: `Mercado Libre - App credentials`) con esos 3 campos, y entonces el mapa del sincronizador ya los declara.

## 5. Discrepancias con el documento (corregir en §6.1/§6.2)

1. **NAN:** el doc dice `Terceros/IA - NAN - API Key`; el item real es `Terceros/NAN - API Key` (§3).
2. **Formbricks:** el doc §6.1 lista la env_key `FORMBRICKS_API_KEY` — **no existe** ni en vault ni en disco. Las claves reales son `FORMBRICKS_MCP_KEY_RO` y `FORMBRICKS_MCP_KEY_RW` (item `Formbricks - MCP keys`), ya presentes en PROD root. El mapa de DEV debe usar esos nombres.
3. **Doble item FAL:** en el vault conviven `FAL - API key` (campo `FAL_KEY`, el que mapea el sincronizador) y `FAL - API Key (billing/usage)` (key en `login.password`, len 72, con metadata `proveedor`/`scopes`/`fecha_alta`/`campana`; no aporta env_key al mapa). Decisión pendiente del Admin: cuál es la canónica y retirar/deshabilitar la otra para evitar rotar la equivocada.
4. **Renombre NAN:** field del vault (`NAN_API_KEY`) ≠ env_key real en PROD (`NAN_BUILDERS_API_KEY`); el mapa lo declara explícitamente (§3).
5. **Confirmaciones solicitadas por el doc §6.2** («falta confirmar Stirling, Paperless, Coolify MCP, Composio»): los 4 items **existen** con los nombres exactos de §2 y sus campos coinciden con las env_keys ya desplegadas en PROD root.
6. **Distribución actual invertida respecto al doc:** §6.1 describe DEV como destino y PROD ya lo tiene hecho — las 8 claves MCP/servicio existen en `/opt/hermes/data/.env` (44) y **ninguna** en `/opt/hermes-agent-data/.env` (63). F2.1 solo añade en DEV; en PROD el mapa debe apuntar a los nombres ya existentes.
7. **Observación colateral (fuera de alcance F2.0):** DEV `.env` contiene 10 claves `AMAZON_SPAPI_*` en texto plano, sin item propio en el vault (`Terceros/Amazon SP-API - NeuralCrew` existe pero se auditará aparte). Candidato a fase futura del sincronizador.

## 6. Evidencia (comandos ejecutados, sin valores)

```
ssh root@100.73.30.29 '/usr/local/bin/vw list'                      # 68 items listados
ssh root@100.73.30.29 "vw get 'Terceros/IA - NAN - API Key'"        # exit=1 not found
ssh root@100.73.30.29 "vw get 'Mercado Libre - API keys'"           # exit=1 not found
# 9 items -> vw get --json -> parse server-side (solo field names + len)
ssh root@147.93.3.250  'grep -cE "^[A-Za-z_][A-Za-z0-9_]*=" /opt/hermes-agent-data/.env'            # 63
ssh root@100.73.30.29  'grep -cE "^[A-Za-z_][A-Za-z0-9_]*=" /opt/hermes/data/.env'                  # 44
ssh root@100.73.30.29  'grep -cE "^[A-Za-z_][A-Za-z0-9_]*=" /opt/hermes/data/profiles/golden-game/.env'  # 33
# Presencia por clave: grep -cE '^<KEY>=' (0/1 por clave, ver §2)
```

Los JSON crudos de `vw get` se descargaron a scratch efímero y fueron destruidos tras el parseo; ningún valor de secreto aparece en este documento, en la salida de comandos ni en el commit.
