# Migración v2 de modelos — 02/09/2026 (12 perfiles, Hermes v0.21.0)

Orden de Jonathan tras actualizar a v0.21.0: auxiliares solo NaN, fallback mimo de OpenCode, B.AI reservado sin uso, razonamiento medium, compresión ligada a ventana, borrar rochi dejando solo al configurado.

## Cambios aplicados (P0–P6)

| # | Cambio | Alcance |
|---|---|---|
| P0 | `model.provider: custom:nan-builders` → `NaN-Builders` | default (único con alias; duplicaba entrada en dropdown Desktop) |
| P1 | `agent.reasoning_effort: medium` | 12 configs (ninguno lo tenía) |
| P2 | Auxiliares 100% NaN: vision=qwen3.6, resto=deepseek-v4-flash; bloques `web_extract` ELIMINADOS; `fallback_model=[main, OpenCode-Go/mimo-v2.5]`; B.AI queda en providers sin uso | 12 |
| P3 | `compression` raíz `{enabled, threshold: 0.75, target_ratio: 0.2, protect_last_n: 20}`; `threshold_tokens` legacy limpiado | 12 |
| P4 | `display.show_reasoning: false` + `interim_assistant_messages: false` | comms, vigia |
| P5 | Purga dir fantasma `profiles/rochi/` | ver abajo |
| P6 | Reinicio hermes-serve desacoplado + verificación | final |

## Semántica de compresión (leída del código v0.21)

- `threshold` = **fracción de la ventana del modelo** (default 0.50). `_compute_threshold_tokens` en `agent/context_compressor.py:3365`.
- Piso 0.75 para ventanas <512K → los 0.25/0.55 previos ya disparaban en 75% silenciosamente.
- Efecto con 0.75: qwen 262K→~197K · glm5.3 400K→300K · deepseek 1M→~786K.
- `hygiene_hard_message_limit` existe como campo opcional (default 400).

## Verificación de visión en vivo contra NaN

1. Leer key del provider desde config (nunca hardcodear).
2. POST a `{base_url}/chat/completions` con imagen base64 (data URL) + pregunta "what color".
3. **UA de navegador obligatorio** — urllib sin UA → 403 Cloudflare (no es fallo de key).
4. Resultado 02/09: qwen3.6 → OK ("Red"); qwen3.8-flash → HTTP 400 Invalid request con imagen.
5. Conclusión: visión → `NaN-Builders/qwen3.6` es la única opción NaN válida a la fecha.

## Purga de perfil que resucita (rochi)

- Síntoma: borrado + reinicio → el dir reaparece con solo `cron/` (ticker files, executions.db) + `state.db`. served_profiles ya NO lo lista.
- Causa raíz: proceso huérfano `hermes --profile rochi serve --isolated` (PID 76123, arrancado 22/08 vía SSH del Desktop) cuyo ticker de cron recrea el esqueleto CADA MINUTO.
- Los reinicios de gateway NO lo matan (proceso aparte del gateway).
- Receta: `pgrep -af "profile <slug>"` → `kill <pid>` → `rm -rf profiles/<slug>` → esperar 90s → confirmar que no existe y sin procesos.
- Contexto: en el VPS dev conviven gateway s6 (contenedor, HERMES_HOME=/opt/data) y hermes-serve (systemd, host) sobre el MISMO data dir — reiniciar uno no limpia al otro.

## Estado final verificado

12 configs válidos · served_profiles=12 (sin rochi) · backend activo health 302 · un solo NaN en dropdown.
Backups: `config.yaml.bak-models-v2-20260902` por perfil + tar de rochi en data/backups/.
Script transitorio: /tmp/migrar_modelos_v2.py (patrón: yaml.safe_load → mutar dict → yaml.dump → validar releído).