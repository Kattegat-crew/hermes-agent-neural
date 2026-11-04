---
name: data-driven-team-reports
description: "Use when building verified team-activity reports."
tags: [informes, reports, discord, webhook, state-db, verificacion, cron]
---

# Data-Driven Team Reports

Generar informes de equipo realmente útiles = leer **datos verificados**, no títulos genéricos. Patrón hermes-paper-agent: los números vienen de código, el LLM solo narra, y un **gate de verificación** impide relleno/invención.

## Por qué el informe "por títulos" no sirve

Un informe que solo lista `title + message_count + tool_call_count` de cada sesión NO dice qué se hizo: solo que hubo una sesión. El usuario lo rechaza (04/09).

## Fuentes de verdad por agente (DEV .250 + PROD .222)

| Fuente | Qué da | Dónde |
|---|---|---|
| Hermes `state.db` sessiones | Lugar (`source`), título, #msg, #tools | `/opt/data/state.db` (default) · `profiles/<p>/state.db` (roshi/vigia/comms) |
| `messages.tool_name` | Herramientas REALES por sesión (terminal, write_file, patch…) | `state.db` |
| OpenCode `opencode.db` | Sesiones + `summary_additions/files`, `agent`, `cost` | snapshot refrescada `workspace/oc-snap/` |
| AGY (Antigravity) `brain` | Sesiones del día | `.250` `/root/.gemini/antigravity-cli/brain/` + `conversations/<id>.db` → leer vía `docker run -v /:/hostfs` |
| PROD `state.db` | Perfiles prod (default, helmer, jacqueline, nancy, yulieth, neural-admin-test) | lector vía `ssh root@100.73.30.29` |
| PROD `errors.log` | Errores del día | `.222` — SIEMPRE filtrar `day_str in line` |
| git log | commits del día | repos del equipo |

**Inputs clave:**

- `PLACE_LABEL = {discord:Discord, telegram:Telegram, whatsapp:WhatsApp, desktop:Desktop, ...}` — el `source` de state.db te da el lugar de la sesión.
- Agrupar por `profile_name` (separar Ragnar/roshi/vigia/comms) y luego por `source` (lugar).
- `sql()` wrapper read-only (`mode=ro`, uri) para consultas defensivas.

## Gate de verificación

Si un agente no tiene evidencia hoy (0 sesiones, 0 tools): escribir "_sin actividad verificada hoy._". NUNCA inventar relleno. El informe termina con la nota del gate.

## Envío a Discord vía webhook

Para crons en el host (fuera del gateway) `send_message` no sirve → publicar directo al webhook del canal. Dos pitfalls obligatorios:

1. **Cloudflare 403 (error 1010):** la API de Discord rechaza el User-Agent de Python (`urllib`). Enviar `User-Agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36`.
2. **Límite 2000 chars:** trocear el mensaje en bloques de 1900 chars y enviar cada uno.

```python
import json, urllib.request
WEBHOOK_URL = "https://discord.com/api/webhooks/<ID>/<TOKEN>"
ua = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
for chunk in [text[i:i+1900] for i in range(0, len(text), 1900)]:
    urllib.request.urlopen(urllib.request.Request(
        WEBHOOK_URL, data=json.dumps({"content": chunk}).encode(), method="POST",
        headers={"Content-Type":"application/json", "User-Agent": ua}), timeout=30)
```

## Script de referencia

`/opt/data/scripts/informe_diario_exacto.py` — implementación completa verificada (dev users + OpenCode + AGY + producción + envio webhook). Cron `informe-diario-exacto` (07:00, deliver local) lo ejecuta. Detalle extensible en `references/report-architecture.md`.

## Skills relacionadas / solapamiento

Esta skill cubre *cómo se arma* el informe con datos. `communications/admin-reporting` cubre el *formato al Admin*; `discord-reporter` cubre el envío puntual por `send_message`. Ambas son user-owned (requieren `hermes curator adopt`). Si se consolidan, el solapamiento con esta skill es escaso pero conviene revisarlo.
