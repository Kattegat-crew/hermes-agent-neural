# Migración DeepSeek → GLM en la flota (24/09/2026)

Orden del dueño (Jonathan/Admin, DM Discord): *"cambia de deepseek a glm en todas las sesiones"*.
Ejecutada y verificada en vivo sobre **12 configs** (`/opt/data/config.yaml` + 11 perfiles:
bragi, brokkr, comms, freyja, heimdall, hermodr, roshi, sindri, ullr, vigia, vili).
Scripts: `/opt/data/profiles/roshi/workspace/tmp_migrar_glm.py` (dry-run/--apply) y
`tmp_verificar_glm.py` (auditoría post-cambio).

## Qué se cambió (rutas de SELECCIÓN, no definiciones)

| Ruta | Antes | Después |
|---|---|---|
| `model.default` | `deepseek-v4-flash` | `glm5.3-flash` (main ya lo tenía) |
| `auxiliary.*.model` (9-10 bloques: vision, compression, skills_hub, approval, mcp, title_generation, curator, session_search, flush_memories) | `deepseek-v4-flash` | `glm5.3-flash` |
| `delegation.model` | `deepseek-v4-flash` | `glm5.3-flash` |
| `cron.model` / `cron.model_provider` | deepseek / ausente | `glm5.3-flash` + `NaN-Builders` (los perfiles NO tenían la llave: se añadió para que las sesiones de cron no hereden otro modelo) |
| `custom_providers[NaN-Builders].model` | `deepseek-v4-flash` | `glm5.3-flash` (solo el proveedor NaN; B.AI se dejó intacto: solo sirve deepseek) |
| catálogo `providers.NaN-Builders.models.glm5.3-flash` | ausente en brokkr/vigia; sin `supports_vision` | añadido (ctx 131072) y `supports_vision: true` en toda la flota |

**Intacto a propósito**: definiciones deepseek dentro de los catálogos (siguen disponibles como
respaldo), proveedor `B.AI`, `fallback_model` (OpenCode-Go/mimo-v2.5), `smart_model_routing.cheap_model`
(qwen3.6), `max_tokens` (no se tocó sin orden).
Backups: `<config>.bak-glm-20260924-201719` en cada perfil.

## Orden de verificación (repetible)

```bash
# 1) el runtime resuelve el modelo (no basta leer el YAML)
for p in roshi vili vigia brokkr bragi comms freyja heimdall hermodr sindri ullr; do
  printf '%-9s ' "$p"; /opt/hermes/.venv/bin/hermes -p $p config get model.default; done
# 2) prueba end-to-end real (crea sesión y gasta tokens mínimos)
/opt/hermes/.venv/bin/hermes -p roshi -z "Responde exactamente: GLM OK"
# 3) telemetría del modelo REALMENTE usado (incluye tareas auxiliares)
sqlite3 -readonly /opt/data/profiles/roshi/state.db \
  "select id,model,source from sessions order by started_at desc limit 3"
sqlite3 -readonly /opt/data/profiles/roshi/state.db \
  "select * from session_model_usage order by rowid desc limit 5"
```
La corrida de prueba (sesión `20260924_201911_a31af0`) registró `glm5.3-flash` tanto en la llamada
principal como en la auxiliar `title_generation` → config + auxiliares resueltos.

## Aprendizajes (gotchas)

1. **Editar configs con `ruamel.yaml` round-trip, no `yaml.safe_dump`**: safe_dump reescribe el archivo
   entero y pierde comentarios/orden/formato. `from ruamel.yaml import YAML; yaml.preserve_quotes=True`.
   Disponible en `/opt/hermes/.venv` (no en `/usr/bin/python3`, que no tiene ni `yaml`).
2. **`supports_vision` hay que DECLARARLO** en `providers.<prov>.models.<modelo>`: el ruteo de imágenes
   (`agent/image_routing.py`, `_supports_vision_override`) lo consulta antes de mandar imágenes al modelo
   principal; sin la bandera las imágenes se van por el auxiliar de visión (o se pierden) aunque el
   modelo SÍ vea. Verificado en vivo: glm5.3-flash respondió "Rojo" a un PNG rojo base64.
3. **glm5.3-flash es modelo de razonamiento**: 107 `reasoning_tokens` para un prompt trivial
   ("di OK"). El presupuesto de `max_tokens` cubre razonamiento + texto: revisarlo al migrar.
4. **Sin reinicio**: `hermes_cli/config.py` cachea por `(path, mtime_ns, size)` (`_LOAD_CONFIG_CACHE`),
   así que al guardar el YAML el gateway recarga en el siguiente turno.
5. **Sesiones con pin**: quien corrió `/model` guarda `model_config.model` y ese override GANA sobre
   la config. Tras una migración hay que listar las sesiones con pin (abiertas y cerradas) y decidir:
   los pins no se borran solos. Ej.: sesión TUI roshi `20260825_190243_7fd8db` quedó pinneada a deepseek.
6. **NaN API**: `GET /v1/models` y `GET /v1/models/<id>` → 403; y `urllib` sin User-Agent de navegador
   → `403 error code: 1010` (Cloudflare), que NO es fallo de key. Probar el modelo puntual con
   `POST /chat/completions` + UA de navegador.
7. **Estado de sesión ≠ config**: los perfiles con sesiones de cron heredan `cron.model`; si el perfil
   no declara la llave, conviene añadirla para que no dependa de la raíz.
8. **Escribir skills**: `/opt/hermes/skills` y `/opt/data/skills` son el MISMO directorio
   (`/root/hermes-agent-legacy-docker/skills`), pero `HERMES_WRITE_SAFE_ROOT=/opt/data:/host` bloquea la ruta
   `/opt/hermes/...`: crear/editar referencias por `/opt/data/skills/...`.
