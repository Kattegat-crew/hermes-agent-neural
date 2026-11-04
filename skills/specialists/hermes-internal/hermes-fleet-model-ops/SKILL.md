---
name: hermes-fleet-model-ops
version: 1.0.0
author: curator-ragnar
license: Apache-2.0
description: "Use when setting models/compression across a Hermes fleet."
tags: [hermes, flota, modelos, compresion, multiperfil, perfiles, config]
---

# Hermes Fleet Model Ops — configuración de flota multiperfil

Clase de tarea: asignar/migrar modelos, auxiliares, compresión y razonamiento a través de N perfiles Hermes, y operar ciclos de vida de perfiles (borrado, skew de código, zombies). Construida 02/09/2026 con la migración v2 de 12 perfiles en Hermes v0.21.0, verificada en código y en vivo.

**Hermanas user-owned (no editables por curador; recomendar `hermes curator adopt`)**: `devops/hermes-multiprofile-model-config` (matriz por bot, 401 keys cruzadas, hot-reload), `hermes-gateway-ops` (s6, allowlist, ruteo WhatsApp), `devops/hermes-bot-fleet-ops`. Tras adopt, este skill queda como índice de clase.

## Semántica v0.21 (verificada en código)

- **Compresión**: bloque RAÍZ `compression:`; `threshold` = **fracción de la ventana del modelo** (`_compute_threshold_tokens`, `agent/context_compressor.py:3365`). Piso 0.75 para ventanas <512K — valores menores (0.25/0.55) se clampan SILENCIOSAMENTE a 0.75. Con `threshold: 0.75` un solo número sirve para toda la flota: qwen 262K→~197K, glm5.3 400K→300K, deepseek 1M→~786K. `threshold_tokens` en configs viejas = legacy, limpiar.
- **Dos knobs distintos**: `agent.reasoning_effort` (none…ultra) = cuánto PIENSA el modelo; `display.show_reasoning: false` + `display.interim_assistant_messages: false` = si se VE en el chat. Configurar ambos por separado — "razonamiento encendido en medio" ≠ "mostrar razonamiento".
- **`web_extract` ya NO es tarea auxiliar** (v0.21 no usa LLM ahí): borrar el bloque de las configs, no poblarlo.
- **Auxiliares v0.21**: vision, compression, skills_hub, approval, mcp, title_generation, curator.
- **Fallback**: llave raíz `fallback_model:` lista `[{provider, model}]` (ej. cadena NaN → OpenCode-Go/mimo-v2.5; B.AI puede quedar en `providers:` sin uso como reserva).
- **Inventario real ≠ config:** el catálogo vivo se lista con `GET {base_url}/models` (Bearer real de `/opt/data/.env` — la key de config.yaml viene ENMASCARADA y da 403/401). Ollama-Local (PC Admin) NUNCA en camino crítico: solo último fallback y con `/api/tags` verificado antes. Snapshot y política: `references/catalogo-proveedores-20260926.md`.
- **Duplicado en dropdown**: `model.provider: custom:nan-builders` (alias deprecado desde v0.20.4) + provider real `NaN-Builders` en `providers:` = dos entradas para la misma API. Reescribir al nombre canónico.
- **Visión**: NO confiar en catálogos — verificar EN VIVO: POST imagen base64 a chat/completions con UA de NAVEGADOR (urllib sin UA → 403 Cloudflare, no es fallo de key). A la fecha en NaN: qwen3.6 SÍ ve; qwen3.8-flash → HTTP 400 con imagen.

## Ciclo de vida de perfiles

| Problema | Causa | Fix |
|---|---|---|
| Perfil borrado RESUCITA cada minuto (solo `cron/` + state.db) | `hermes --profile <p> serve --isolated` huérfano del Desktop (SSH, sobrevive días) recrea el esqueleto con su ticker de cron aunque served_profiles ya no lo tenga | `pgrep -af "profile <p>"` → kill PID → `rm -rf` → verificar 90s sin recreación (caso rochi 02/09/26, PID vivo desde 22/08) |
| Banner 'running old code' en Desktop | Backend compara fingerprint git de ARRANQUE vs repo en disco (`gateway/code_skew.py`); típico cuando el update corre en paralelo con el reinicio (el ref git se movió después del arranque) | Terminar el update ANTES de reiniciar; si ya pasó: repo estable + reiniciar hermes-serve una vez más |
| Reinicio corta mi propia sesión | hermes-serve es el backend que sirve al propio agente | Desacoplar: `systemd-run --on-active=10 --unit=nc-restart-serve systemctl restart hermes-serve`; verificar al reconectar |
| Doble gateway en un VPS | hermes-serve (systemd, host) + gateway s6 (contenedor) comparten data dir — reiniciar uno NO limpia served_profiles/tickers del otro | Tras borrar perfil o cambiar config, verificar AMBOS procesos |

## Patrón de migración masiva (12+ configs)

1. Diagnóstico primero: script read-only que lee TODOS los configs y produce tabla (modelo, auxiliares, compresión, reasoning).
2. Backup por perfil: `config.yaml.bak-<motivo>-<fecha>` (nunca sobrescribir sin backup).
3. Transformar con yaml.safe_load → mutar dict → yaml.dump → **validar releído** antes de tocar el siguiente perfil.
4. Plan con pasos numerados y aprobación del usuario ("ejecuta") antes de escribir.
5. Reinicio ÚNICO al final (desacoplado) + verificación: configs releídos, served_profiles, health check, dropdown en Desktop.

## Verificación por perfil

```bash
/opt/hermes-venv/bin/python -c "import yaml; d=yaml.safe_load(open('data/profiles/<slug>/config.yaml')); print(d['model']['default'], d['compression']['threshold'], d['agent'].get('reasoning_effort'))"
```

## Referencias

- `references/migracion-v2-20260902.md` — caso completo de la migración v2: cambios P0–P6, purga de rochi, verificación de visión en vivo.
- `references/migracion-deepseek-a-glm-20260924.md` — migración deepseek→glm en 12 configs (24/09/26): rutas de selección vs catálogo, `supports_vision` obligatorio para el ruteo de imágenes, ruamel round-trip para no perder comentarios, verificación con `hermes config get` + telemetría de `session_model_usage`, y pins de `/model` que sobreviven a la config.
- Hermana user-owned `devops/hermes-multiprofile-model-config` — matriz por bot y diagnóstico 401 (keys cruzadas).