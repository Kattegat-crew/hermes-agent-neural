---
name: hermes-provider-ops
description: >-
  Configuración, rotación y resiliencia de proveedores LLM en Hermes. Gestión de proveedores en config.yaml, fallback automático ante rate-limits y actualización de modelos.
tags: [hermes, providers, modelos, fallback, config, api, resiliencia, devops]
version: 2.0.0
author: NeuralCrew / Hermes Fleet
---

# Operaciones de Proveedores y Modelos LLM en Hermes

Habilidad canónica para configurar, auditar y asegurar la resiliencia de los proveedores de inteligencia artificial (OpenRouter, Anthropic, B.AI, Nan Builders, OpenAI) en los perfiles de la flota Hermes, gestionando la rotación de modelos y cadenas de fallback automático.

---

## Cuándo usar esta Skill (Triggers y Síntomas)

Usa esta skill inmediatamente cuando se presente cualquiera de estas situaciones:
- Peticiones del usuario: *"agrega un nuevo proveedor a Hermes"*, *"el modelo está dando rate-limit o error 429"*, *"rota el modelo del agente a glm o sonnet"*, *"cambia la API key en el perfil"*, o *"configura un fallback automático"*.
- Diagnóstico de caídas en el runtime por proveedores sin saldo, tokens inválidos o modelos deprecados.
- Actualización de `config.yaml` en los perfiles de `/opt/hermes-agent-data/profiles/*/config.yaml`.

---

## 1. Configuración de Proveedores en `config.yaml`

Los proveedores se definen en el archivo de configuración de cada perfil (`~/.hermes/config.yaml` o `/opt/hermes-agent-data/profiles/<perfil>/config.yaml`):

```yaml
model: "custom:nan-builders/glm5.3-flash"

providers:
  custom:nan-builders:
    base_url: "https://api.nanbuilders.com/v1"
    api_key: "${NAN_BUILDERS_API_KEY}"
    models:
      - id: "glm5.3-flash"
        context_window: 128000
        supports_vision: true
        supports_tools: true
  openrouter:
    api_key: "${OPENROUTER_API_KEY}"
  anthropic:
    api_key: "${ANTHROPIC_API_KEY}"
```

**Regla de Oro**: Nunca hardcodear claves API dentro de `config.yaml`. Usar siempre interpolación de variables `${NOMBRE_VAR}` leídas desde el archivo `.env` del perfil o desde Vaultwarden (`vault-access`).

---

## 2. Resiliencia y Cascada de Fallback

Cuando un proveedor primario alcanza límites de tasa (HTTP 429), cuota agotada (HTTP 402) o error interno de servidor (HTTP 500/503), Hermes debe aplicar resiliencia por capas:

1. **Reintento con backoff exponencial**: Errores transitorios de red (1s, 2s, 4s).
2. **Cascada de Modelos (Fallback)**:
   * **Nivel 1 (Operación Económica/Rápida)**: `glm5.3-flash` o `gemini-2.0-flash`.
   * **Nivel 2 (Razonamiento Complejo/Fallback de Calidad)**: `claude-3-7-sonnet` o `deepseek-chat`.
   * **Nivel 3 (Contingencia Global)**: `openrouter/auto`.

---

## 3. Rotación Automatizada de Modelos

Esta skill incluye un script para actualizar masivamente el modelo activo en los perfiles sin editar YAMLs a mano ni arriesgar errores de indentación:

```bash
# Rotar modelo de un perfil específico
python3 /opt/hermes-agent/skills/core/hermes-provider-ops/scripts/rotate_model_yaml.py \
  --profile roshi \
  --model "custom:nan-builders/glm5.3-flash"

# Validar sintaxis del config tras la edición
python3 -c "import yaml; yaml.safe_load(open('/opt/hermes-agent-data/profiles/roshi/config.yaml'))"
```

---

## 4. OpenCode Zen (`OpenCode-Go`) — proveedor fallback de la flota

Configurado en DEV y PROD como fallback cuando NaN falla: `https://opencode.ai/zen/go/v1`
con 4 modelos (`mimo-v2.6-flash`, `qwen3.8-flash`, `deepseek-v4-flash`, `glm-5.3-flash`).

Al probar la API manualmente (curl/scripts), cuidado con estos tres comportamientos:
1. **Cloudflare bloquea por User-Agent**: un UA tipo `python-requests` recibe HTTP 403
   aunque la key sea válida. Probar con `curl` usando un UA de navegador.
2. **Header obligatorio `x-opencode-session`**: sin él el endpoint devuelve HTTP 400
   `MissingSessionID`. Hermes lo envía nativamente en cada request
   (`agent/opencode_affinity.py`), así que solo afecta a pruebas manuales.
3. **Key expirada**: responde HTTP 401 con cuerpo `api_key_expired` — distinguir del
   403 de Cloudflare (que no implica nada sobre la key).

### Rotación de key y recarga bajo s6 (verificado 19/10/2026)

Al rotar `${OPENCODE_GO_API_KEY}` en `/opt/data/.env`:
- El env del contenedor (`/run/s6/container_environment/`) queda **congelado con la key
  vieja** hasta recrear el contenedor — NO es la fuente efectiva.
- Hermes llama `load_hermes_dotenv()` al importar cada proceso y carga `HERMES_HOME/.env`
  con **`override=True`** (`hermes_cli/env_loader.py:506`), pisando el env heredado.
- Consecuencia: **basta un `s6-svc -r` del servicio** (no recreate del contenedor) para
  que el proceso nuevo cargue la key nueva.
- Verificación sin `/proc/<pid>/environ` (puede dar Permission denied dentro del
  contenedor): comprobar que el proceso arrancó DESPUÉS del mtime del `.env`
  (`s6-svstat` vs `stat -c %y /opt/data/.env`) + llamada real HTTP 200 a un modelo.

## Fuga de tool-call DSL como texto plano (fallo de proveedor)

Familia DeepSeek V4 puede emitir su DSL interno de tool-calls (bloques `｜｜DSML｜｜ ...`)
como texto plano en `content` en vez de `tool_calls` — el turno muere sin ejecutar nada.
Ver el procedimiento completo del guard de 3 capas (recuperación en intake a 0 tokens
extra, re-prompt acotado, cortafuegos anti-markup) en
`references/dsml-toolcall-leak-guard.md`.

## Gotchas y Errores Críticos con Proveedores

1. **Reinicio de procesos**: Modificar `config.yaml` no surte efecto inmediato si el daemon de Hermes ya está corriendo en memoria. Si el cambio es para un cron o servicio persistente, reiniciar el servicio o proceso afectado.
2. **Context Window realista**: Si declaras un context window mayor al que el proxy/proveedor soporta, la sesión morirá silenciosamente o truncará el prompt sin advertencia.
3. **Soporte de Tool Calling**: No todos los modelos soportan invocación de herramientas (`tools: true`). Antes de fijar un modelo por defecto para agentes operativos (Vigía, Roshi, Brokkr), verifica que ejecute herramientas de terminal y lectura de archivos.
