---
name: hermes-gateway-ops
description: "Use when changing the Hermes gateway model or allowlists."
tags: [hermes, gateway, whatsapp, allowlist, modelo, docker]
license: Apache-2.0
metadata:
  author: "neuralcrew-ops"
  version: "1.2"
---
# Hermes Gateway Ops (Ragnar)

Operación del gateway de Hermes que corre Ragnar (WhatsApp + Telegram) en Docker.

## Activation Contract

- Cambiar el modelo/proveedor de Ragnar (ej. deepseek contra NaN Builders).
- Actualizar allowlists de WhatsApp/Telegram (números y grupos).
- Reiniciar el gateway o diagnosticar crash loop.
- Ver `data/skills/devops/whatsapp-bridge-operations` (dentro del contenedor) para operaciones del bridge y `devops:nan-builders-api` para la API.

## Hard Rules

- El servicio s6 real es `gateway-default`. `main-hermes` es dummy — NUNCA reiniciar main-hermes.
- El bridge de WhatsApp lee el env AL ARRANCAR: tras cambiar `.env`/config, reiniciar gateway para aplicar.
- El allowlist REAL del bridge viene de `WHATSAPP_ALLOWED_USERS` en `/opt/hermes/.env` (env_file del docker-compose, NO de `/opt/hermes/data/.env`). `docker restart hermes-agent` NO recarga el env_file: hay que recrear con `cd /opt/hermes && docker compose up -d`. Gotcha: la imagen local está taggeada `hermes-agent-hermes:v0.20.4-ncl` y compose busca `:latest` — correr antes `docker tag hermes-agent-hermes:v0.20.4-ncl hermes-agent-hermes:latest` (si no, compose intenta pull y falla).
- En perfiles secundarios pinar `platforms.whatsapp.enabled: false` ADEMÁS de `platforms.api_server.enabled: false`. Si whatsapp queda enabled en un secundario, se cargan DOS adapters que pelean por el bridge (puerto 3000) y se PIERDEN mensajes.
- El CLI `hermes` sin `-p` resuelve al perfil sticky (`/opt/data/active_profile` = jacqueline en prod). Para operar otro DB usar `HERMES_HOME=/opt/data/profiles/<nombre>` explícito.
- No editar config.yaml vía herramientas del agente Hermes (guarda lo bloquea). Editar el archivo directamente como operador.
- No imprimir secretos (tokens/API keys) en outputs ni reportes.

## Decision Gates

| Necesidad | Acción |
|---|---|
| Cambiar modelo | Editar sección `model:` de `data/config.yaml` (api_key + base_url) + restart |
| Actualizar allowlist WhatsApp | Editar `.env` (`WHATSAPP_ALLOWED_USERS`) + `config.yaml` (`whatsapp.allowed_users`) + restart |
| Configurar grupo WhatsApp | No hace falta grupo por ID: `group_policy=open` + `require_mention=true` basta, solo etiquetar |
| Crash loop gateway | Leer `docker logs --tail 30`: PermissionError → chown hermes; open policy sin opt-in → `WHATSAPP_ALLOW_ALL_USERS=true` |
| Crear perfil multiplex (v0.20.4) | `hermes profile create <nombre> --clone-from <origen> --no-alias`; perfiles en `/opt/data/profiles/<nombre>/`; pinear en el secundario `platforms.api_server.enabled: false` Y `platforms.whatsapp.enabled: false`; chown -R hermes:hermes si lo creó root |
| Ruta contacto → perfil | `gateway.profile_routes` en config.yaml: match exacto por LID / JID / número plano; sin match → default. **El bridge entrega chat_id en formato LID (`<lid>@lid`)** — la ruta LID es la que de verdad enruta. Rutas por persona: JID + número + LID. Capturar LID: `grep "inbound message" /opt/data/logs/gateway.log` cuando la persona escribe su primer mensaje |
| Instalar plugin de usuario | Copiar dir del plugin a `/opt/data/plugins/<nombre>/` (chown hermes:hermes) + `plugins.enabled:` en config.yaml + restart gateway-default |
| **Plugin soul_survey (/soul)** | Encuesta 29 preguntas → SOUL.md. `plugins.enabled` DEBE decir `soul-survey` (guion; el loader usa `name` del plugin.yaml como key — con `soul_survey` guion bajo NUNCA carga). Copia user `/opt/data/plugins/soul_survey/` gana sobre bundled. Fallback de perfil: `main`. Guarda con MERGE: conserva el SOUL custom del perfil y agrega/actualiza la sección `## 📋 Encuesta /soul — Perfil Operativo (6 bloques)`. TTL 30 min (`SOUL_SURVEY_TTL_SECONDS`). Triggers: `/soul`, `comienza la encuesta`, `perfilame`, `configurar mi agente`, `quiero mi soul`. Corregir: `corregir Q0.1`. Cancelar: `/salir`. Los mensajes de la encuesta NO quedan en el historial (hook skip, by design). Detalle: `hermes plugins list` es engañoso — verificar con `get_plugin_manager().list_plugins()`; los mensajes del API server NO pasan por el hook `pre_gateway_dispatch` (E2E por API = falso positivo) |
| STT voz (whisper) | `faster-whisper==1.1.1` en `/opt/hermes/.venv` (capa de imagen: se pierde al recrear container) + sección `stt:` en config raíz (`enabled: true, provider: local, language: es`). `/opt/data/home` debe ser owner 10000:10000 (root-owned rompe uv cache) |
| Desktop SSH (servidor) | Wrapper `/usr/local/bin/hermes` (docker exec) + flags `serve --isolated --profile X --ssh-session-token-file <path> --ssh-owner-nonce <n>`; llave del equipo en `/root/.ssh/authorized_keys` |

## Execution Steps

1. Rutas: config `data/config.yaml` (host `/root/hermes-agent-legacy-docker/data/`), env `data/.env`, script reporte `data/scripts/allowlist_report.py`. En contenedor son `/opt/data/...`. VPS prod: /opt/hermes (host) = /opt/data (contenedor); SSH root@169.58.189.222; wrapper /usr/local/bin/hermes.
2. Modelo: sección `model:` (primeras 6 líneas). NaN Builders: api_key `sk-JzB...ohYw`, base_url `https://api.nan.builders/v1`, default `deepseek-v4-flash`.
3. Allowlist WhatsApp: `WHATSAPP_ALLOWED_USERS` en `.env` + `whatsapp.allowed_users` en `config.yaml` (ambos, iguales). Verificar LIDs 15 dígitos vía `lid-mapping-*.json` (pueden ser redundantes con números).
4. Restart: `docker exec hermes-agent /package/admin/s6/command/s6-svc -r /run/service/gateway-default`. Esperar 30-60s; verificar PID del gateway cambió y se estabiliza, bridge respawneó, `curl -s http://127.0.0.1:3000/health` → connected, y en `bridge.log` aparece `Allowed users: <lista>`.
5. Troubleshooting crash loop: `docker logs hermes-agent --tail 30`. `Permission denied: /opt/data/...` → `chown -R hermes:hermes` sobre el dir afectado. `Refusing to start ... open ... WHATSAPP_ALLOW_ALL_USERS` → agregar `WHATSAPP_ALLOW_ALL_USERS=true` a `.env`.
6. Comando `/allowlist` del chat ya existe (quick_command type:exec). Validar con `docker exec hermes-agent python3 /opt/data/scripts/allowlist_report.py`.
7. Perfiles multiplex: crear con `hermes profile create <nombre> --clone-from <origen> --no-alias`. En perfiles secundarios pinear `platforms.api_server.enabled: false` y `platforms.whatsapp.enabled: false` (api_server evita warnings de port-binding; whatsapp evita el bug de DOBLE adapter que pelea por el bridge y pierde mensajes). El env del gateway cachea el del primer perfil: usar un proyecto Engram ÚNICO compartido entre perfiles (proyecto `neuralcrew`: `.env` ENGRAM_PROJECT + `mcp_servers.engram.args --project` + `home/.engram/config.json`) para evitar leak de contexto/memoria entre agentes.
8. Reset de sesión contaminada (el bot dice "soy default" aunque la ruta esté bien): el historial viejo vive en el state.db RAIZ y en el del perfil (mismo session_id, historial fusionado). Borrar mensajes+sessions en ambos DBs (`/opt/data/state.db` y `/opt/data/profiles/<perfil>/state.db`) + entradas en `sessions/sessions.json` + tabla `gateway_routing`, y restart gateway-default. Ojo: usar `HERMES_HOME=/opt/data` explícito para el DB raíz.
8. Plugin de usuario: copiar a `/opt/data/plugins/<nombre>/`, agregar `plugins.enabled: [<nombre>]` en config.yaml, restart s6 gateway-default, verificar carga en `docker logs hermes-agent --tail 60` (buscar nombre del plugin; sin tracebacks).
9. Desktop SSH: el Desktop spawnea `hermes serve --isolated --profile X` por SSH y tunnea el puerto; verificar que `bash -lc 'command -v hermes'` devuelva el wrapper en shell no interactivo y que la llave pública del equipo esté en authorized_keys. Token files en `/opt/data/home/.hermes/desktop-ssh/`.

## Pitfalls v0.21 (gateways standalone + api_server trap)

- **Gateways standalone y flags "down" (03/09):** un gateway standalone (p. ej. roshi con `gateway run` propio) NO se reinicia con `s6-svc -r` si el init regenera un flag `down` en cada recreate del contenedor. El standalone no resucita solo: la persistencia real va en un hook `cont-init.d` (ver skill `hermes-fleet-lifecycle`). **Si el slot s6 está "down a propósito" NO es un bug** — el init lo regenera; no hay que forzarlo con `-u` a menos que el standalone deba correr bajo s6.
- **API_SERVER trap v0.21 (solo perfiles MULTIPLEX):** una `API_SERVER` key residual en el `.env` de un perfil reactiva `api_server` aunque `platforms.api_server.enabled: false` diga false → el gateway default imprime "Skipping secondary profile". Fix estable: pinear `platforms.api_server.enabled: false` en config.yaml (Desktop lo borra al re-guardar; reponer tras cada re-guardado con backup `.bak-api-pin-*`) + quitar la key del `.env`. Si el perfil está en modo standalone, reconsiderar esos pines.
- **LEGITIMIDAD de topología:** verificar contra el repo VIVO (log del perfil propio, `grep chat_id` en log del default), NUNCA desde memoria ni desde `s6-svstat` — el service state del supervisor no refleja si un standalone corrió y atendió sesiones.

## Output Contract

Reportar: qué cambió (archivo + línea), PID nuevo del gateway, estado del bridge (allowed users del log), resultado del health check, y resultado del `allowlist_report.py`. Sin secretos.

## References

- `data/skills/devops/whatsapp-bridge-operations/SKILL.md` — bridge, allowlist, grupos, voz, debug.
- `data/skills/devops/nan-builders-api/SKILL.md` — API NaN Builders, UA Cloudflare, modelos.
- `docs/superpowers/plans/2026-08-19-ragnar-allowlist-model.md` — plan completo del setup.
- `/root/Migracions/plan-agentes-hermes-prod-20260820.md` — plan de despliegue prod (perfiles por persona, rutas, fases) + sección "Sesión 2026-08-21 (tarde)" con el historial de ruteo LID, perfiles cogollosour/nancy y lecciones aprendidas.
- `/root/Migracions/estado-plugin-soul-survey-20260821.md` — estado completo del plugin soul_survey: fixes, verificación, merge de SOUL.md, STT whisper, análisis de conversación y operación.
