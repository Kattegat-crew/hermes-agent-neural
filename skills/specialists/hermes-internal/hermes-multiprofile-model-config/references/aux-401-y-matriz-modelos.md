# Transcript del 401 y matriz de modelos aplicada (26/08/2026)

## Error original (log real)

```
2026-08-26 06:50:13 INFO agent.auxiliary_client: Auxiliary compression: using custom (deepseek-v4-flash) at https://api.nan.builders/v1/
2026-08-26 06:50:14 WARNING agent.context_compressor: Failed to generate context summary: Error code: 401 - {'error': {'message': 'Invalid API key.', 'type': 'auth_error', 'param': 'None', 'code': '401'}}. Further summary attempts paused for 60 seconds.
2026-08-26 06:50:14 INFO agent.conversation_compression: ... "aux_model":"deepseek-v4-flash", "commit_status":"aborted", "failure_class":"summary_generation_aborted", "current_estimated_tokens":296311 ...
```

Lo que decía config.yaml (incorrecto):

```yaml
auxiliary:
  compression:
    provider: custom
    model: deepseek-v4-flash
    base_url: https://api.nan.builders/v1      # ← base NaN-Builders
    api_key: sk-5gt…fluw                       # ← key de B.AI (CRUZADA)
```

La key correcta de NaN-Builders (`sk-JzB…`) ya estaba en `model` y en `providers.NaN-Builders.api_key`.

## Fix aplicado

1. Backup: `cp config.yaml config.yaml.bak-compression-401`
2. `auxiliary.compression.api_key` → key de NaN-Builders (la de `providers.NaN-Builders.api_key`).
3. Verificación (sin reinicio, gracias a la caché por mtime):
   ```bash
   python3 -c "import sys; sys.path.insert(0,'/opt/hermes'); from hermes_cli.config import read_raw_config; print(read_raw_config()['auxiliary']['compression']['api_key'][:6])"
   # → sk-JzB...
   ```
4. El cron one-shot de reinicio que se había programado resultó innecesario (mismo PID antes/después) — el gateway releyó la config por turno.

## Matriz por bot aplicada (perfiles de NeuralCrew)

| Bot | Principal | Cheap (routing) | Compresión | Web extract |
|---|---|---|---|---|
| hermodr (Connect) | qwen3.6 | qwen3.6 | qwen3.6 | qwen3.6 |
| brokkr (Web) | deepseek-v4-flash | qwen3.6 | qwen3.6 | mimo-v2.5 |
| bragi (Content) | mimo-v2.5 | qwen3.6 | qwen3.6 | mimo-v2.5 |
| freyja (Social) | qwen3.6 | qwen3.6 | qwen3.6 | qwen3.6 |
| ullr (Leads) | deepseek-v4-flash | qwen3.6 | qwen3.6 | mimo-v2.5 |
| vili (Ads) | deepseek-v4-flash | qwen3.6 | qwen3.6 | mimo-v2.5 |
| heimdall (Analytics) | deepseek-v4-flash | qwen3.6 | mimo-v2.5 | mimo-v2.5 |
| sindri (Producer) | deepseek-v4-flash | qwen3.6 | qwen3.6 | qwen3.6 |

Regla: conversacional → qwen3.6 · razonamiento → deepseek-v4-flash · texto largo/extracción web → mimo-v2.5 · compresión barata → qwen (mimo si el bot resume docs largos).

## Scripts y artefactos

- `/opt/data/scripts/fix_compression_key.py` — auditoría de keys/base_url por bloque (informativo).
- `/opt/data/scripts/fix_compression_key2.py` — escribe `auxiliary.compression.api_key` correcta con backup (final).
- `/opt/data/scripts/apply_model_matrix.py` — aplica `model` + `smart_model_routing` + `auxiliary.*` a los 8 perfiles con backup `config.yaml.bak-models` por perfil.
- Verificación: `hermes config --profile <slug> get model.default` / `get auxiliary.compression.model` en los 8.

## Contexto de identidad Discord (mismo despliegue)

- 8 canales → 8 perfiles vía `gateway.profile_routes` (multiplex: 1 bot Ragnar, cerebros aislados).
- Perfil almacena: `profiles/<name>/state.db` (sesiones), `MEMORY.md` + `memories/` (memoria), clave de sesión `platform:chat_id`.
- PATCH de moderación bloqueado `40333` desde IP de datacenter → renombrar canales a mano en UI; topics con el personaje ya puestos.