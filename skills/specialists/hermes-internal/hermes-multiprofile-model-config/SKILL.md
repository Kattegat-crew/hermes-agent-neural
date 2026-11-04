---
name: hermes-multiprofile-model-config
description: "Use when per-profile models or 401 keys break."
tags: [hermes, modelos, perfiles, provider, gateway, discord]
version: 1.0.0
author: Ragnar
triggers:
  - modelos: modelo por bot / perfil / qué modelo usa cada bot / matriz de modelos / smart_model_routing / auxiliary compression vision web_extract
  - 401: compression aborted / invalid api key / 401 en hermes / keys cruzadas / provider key
  - hot reload: config en caliente / reiniciar gateway / cambios config sin reinicio
  - discord bots: multiplex / un bot varios canales / bot independiente / apps discord / almacenamiento por perfil / state.db
metadata:
  hermes:
    tags: [hermes, models, profiles, provider, gateway, discord]
---

# Hermes Multiprofile Model Config — modelos por bot, 401 y hot-reload

Cómo asignar modelo a N perfiles Hermes especializados, diagnosticar fallos de auth de provider en auxiliares, y saber qué cambios de config necesitan reinicio. Construido y verificado 26/08/2026 al configurar los 8 perfiles de NeuralCrew (hermodr, brokkr, bragi, freyja, ullr, vili, heimdall, sindri) con su matriz de modelos y al reparar el error `Context compression aborted (401 Invalid API key)`.

## Config en caliente: qué requiere reinicio y qué no

- El gateway relee `config.yaml` **por turno**: `read_raw_config()`/`load_config()` cachean por `(mtime_ns, size)` del archivo (`hermes_cli/config.py:3240`). Editar el archivo invalida la caché → los cambios (keys, `model`, `auxiliary.*`, smart routing) se aplican en la siguiente lectura **sin reiniciar**.
- Verificación sin reinicio (dice el valor que verá el proceso):
  ```bash
  python3 -c "import sys; sys.path.insert(0,'/opt/hermes'); from hermes_cli.config import read_raw_config; print(read_raw_config()['auxiliary']['compression']['api_key'][:6])"
  ```
- **Sí requiere reinicio** lo que se carga una vez al boot del gateway: la tabla `gateway.profile_routes` (sin hot-reload). Patrón seguro: cron one-shot `no_agent` con script que reinicia s6 `main-hermes`, programado ~3–4 min después del mensaje final para no cortar el turno en curso (ver skill `hermes-gateway-s6-ops`).
- Si un cron de reinicio "no hizo nada" (mismo PID): primero comprobar si el cambio era de hot-reload; muchas veces el reinicio era innecesario.

## Diagnóstico: 401 en auxiliares = keys cruzadas entre providers

Síntoma exacto (log):
```
Auxiliary compression: using custom (deepseek-v4-flash) at https://api.nan.builders/v1/
Failed to generate context summary: Error code: 401 - {'error': {'message': 'Invalid API key.', ...}}
```
Causa típica: el bloque `auxiliary.<rol>` fue copiado de otra config/plantilla y arrastra la `api_key` de OTRO provider contra la `base_url` de este (p. ej. key de B.AI `sk-5gt…` + base NaN-Builders).

Pasos (ciclo D-I-V-E reducido):
1. D: leer `logs/agent.log` → el mensaje `Auxiliary <rol>: using custom (<modelo>) at <base_url>` ya delata base+modelo. Comparar en `config.yaml` la `api_key` del bloque con la del provider canónico (`providers.<nombre>.api_key`). El error aparece solo cuando la sesión crece (disparo automático de compresión), no al arrancar.
2. I: backup `cp config.yaml config.yaml.bak-<motivo>`; poner la key del provider que corresponde a esa `base_url`.
3. V: releer con `read_raw_config` (ver arriba) — si devuelve el valor nuevo, el fix está vivo sin reinicio.
4. E: documentar en `brain/tasks/pending.md` (causa, fix, verificación).

**No usar probes HTTP crudos como veredicto de auth**: NaN-Builders exige User-Agent propio (Cloudflare) y un `urllib`/`curl` genérico recibe 403 aunque la key sea válida. Fuente de verdad = logs de Hermes, `hermes model`/`hermes chat`, `read_raw_config`. Ver skill `nan-builders-api`.

## Matriz de modelos por perfil (patrón)

```yaml
model: {provider: NaN-Builders, default: <principal>, base_url: "https://api.nan.builders/v1", api_key: <key>}
smart_model_routing:
  enabled: true
  max_simple_chars: 160
  max_simple_words: 28
  cheap_model: {provider: custom, model: qwen3.6, base_url: "https://api.nan.builders/v1", api_key: <key>}
auxiliary:
  compression:    {provider: custom, model: <comp>,   base_url: "...", api_key: <key>, timeout: 120}
  vision:         {provider: custom, model: qwen3.6,  base_url: "...", api_key: <key>, timeout: 120}
  web_extract:    {provider: custom, model: <web>,    base_url: "...", api_key: <key>, timeout: 360}
  title_generation: {provider: custom, model: qwen3.6, base_url: "...", api_key: <key>}
```

Reglas de dedo (catálogo NaN-Builders: deepseek-v4-flash 1M, mimo-v2.5 1M, qwen3.6 262K):
- Conversacional / latencia crítica (Connect, Social) → `qwen3.6`.
- Razonamiento, código, analítica (Web, Leads, Ads, Analytics, Producer) → `deepseek-v4-flash`.
- Documentos largos / redacción extensa (Content) → `mimo-v2.5`.
- Compresión barata → `qwen3.6`; excepción: bot que resume docs largos (Analytics) → `mimo-v2.5`.
- `web_extract` pesado (bots que procesan web) → `mimo-v2.5`; bots conversacionales puros → `qwen3.6`.

Verificación por perfil:
```bash
hermes config --profile <slug> get model.default
hermes config --profile <slug> get auxiliary.compression.model
```
Script de aplicación masiva con backup automático por perfil (`config.yaml.bak-models`): `/opt/data/scripts/apply_model_matrix.py`. `smart_model_routing` es el "cambio de modelo según tarea" nativo: respuestas ≤160 chars → cheap_model; tareas profundas → modelo principal. Override manual siempre posible por turno.

## Identidad: multiplex vs. bots independientes (Discord)

`gateway.profile_routes` canal→perfil = **multiplex**: un solo bot conectado (una cara) sirve N canales; el cerebro que responde es el perfil destino (SOUL, skills, memoria, modelo aislados). "Cara compartida, cerebro aislado". Consecuencias: sin DM directo por bot (el DM va al perfil default), autor visible siempre el bot del servidor.

Independencia total = N aplicaciones en el Discord Developer Portal (token por app) + `discord.token` por perfil + invitar cada bot + `profile_routes` a sus canales. Parte humana: crear apps y entregar tokens; el resto (conexión, invitación, mapeo, validación sin fugas) lo ejecuta el agente.

**Almacenamiento por perfil (verificado en código):** `_open_session_db_for_profile(profile)` abre `profiles/<name>/state.db` (`hermes_cli/web_server.py:12156`); la clave de sesión del gateway es `platform:chat_id` (`gateway/run.py:23731`) → hilo persistente por canal y transcripts aislados entre perfiles. Memoria explícita en `profiles/<name>/MEMORY.md` + `memories/`. Un bot no lee los transcripts de otro.

**Discord 40333:** desde IP de datacenter, TODAS las escrituras de moderación PATCH (renombrar canales, nick del bot) devuelven `403 {"message":"internal network error","code":40333}` aunque crear canales y leer funcionen. No insistir con reintentos; fallback = renombrar a mano en la UI.

## Pitfalls

- No documentar/reportar "requiere reinicio" sin comprobar si el setting se lee por turno (mtime cache) o al boot.
- No prometer "8 bots con nombre propio en Discord" con solo `profile_routes` — eso da multiplex, no independencia.
- Al verificar rutas `profile_routes`: confirmar canales únicos, perfiles únicos, perfiles existentes (0 duplicados/compartidos/inexistentes) antes de declarar "sin fugas".
- Tras regenerar un informe grande con secciones ensambladas: verificar el orden físico (`grep -n "^## [0-9]"`) — las secciones reubicadas por script pueden quedar con encabezados pegados (`---##`) o fuera de orden si no se revisa.

## Referencias

- `references/aux-401-y-matriz-modelos.md` — transcript del error, matriz completa por bot y scripts usados.
- Brain: `concepts/plan-agentes-especializados.md` · informe final `workspace/Informe_Final_Agentes_Especializados_NeuralCrew_Labs.md` (secciones 10 y 11).
- Skills hermanas (user-owned; recomendar `hermes curator adopt` para actualizarlas desde sesiones cura): `devops/hermes-admin-operations` (ciclo D-I-V-E, provider/gateway), `autonomous-ai-agents/hermes-profile-routing` (semántica bot↔perfil), `devops/hermes-provider-configuration`.