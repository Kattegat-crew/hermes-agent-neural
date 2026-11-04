---
name: hermes-latency-diagnosis
description: "Use when a bot is slow on short tasks (context, 429)."
tags: [latencia, diagnostico, 429, rate-limit, contexto, bot, flota]
version: 1.0.0
author: Ragnar
metadata:
  hermes:
    tags: [latencia, diagnostico, rate-limit, contexto, 429, slow-bot, fleet]
    category: devops
    related_skills: [hermes-bot-fleet-ops, hermes-multiprofile-model-config, hermes-team-ops]
---

# Hermes Latency Diagnosis — Bots lentos en tareas cortas

Procedimiento de diagnóstico cuando el Admin reporta que un bot/perfil tarda demasiado en
responder tareas simples. Regla de oro: **medir antes de culpar al modelo** — las causas reales
suelen ser contexto, rate-limit por llave compartida y overhead, no "la API está lenta".

## When to Use

- "Los bots tardan mucho en responder" / "algo anormal con la velocidad de X bot".
- Antes de culpar al proveedor LLM: hay que descartar las 5 causas estructurales primero.
- Tras rotar modelos o activar bots nuevos en la flota (verificar que no golpeen rate-limit).

## Las 5 causas (ordenadas por impacto, caso real Bragi 27/08/2026)

1. **Contexto gigante del canal** — cada llamada API reenvía TODO el historial del chat.
   Síntoma medible: entradas de 33-55K tokens por llamada (sesión sana: <10K). Una tarea de
   6-8 pasos de herramienta a ~20 s/llamada = 2-4 min, aunque "el modelo responda rápido".
   Fix: `/clear` del canal + que el bot lea archivos (campaign.yaml, fichas) bajo demanda en vez
   de absorber el contexto por chat ("agarra contexto" en el canal lo empeora, no lo arregla).
2. **Rate limit por LLAVE, no por modelo** — NaN limita `max_parallel_requests: 5` POR API KEY.
   Rotar modelos entre bots NO alivia: los 12 perfiles + llamadas auxiliares
   (`auxiliary.compression/vision/web_extract/title_generation`) + bg-review automático comparten
   el MISMO bucket. Golpea cuando varios bots corren en paralelo (crons escalonados + chats).
   Fix estructural: mover auxiliares a otro proveedor (ej. B.AI deepseek-v4-flash gratis).
3. **Modelo sin fallback** — litellm solo tiene grupos de fallback para algunos modelos: si el
   upstream falla con uno sin fallback (ej. glm5.3-flash: "No fallback model group found"),
   quedan reintentos a ciegas con backoff.
4. **Caché de agente invalidada por turno** — `gateway.log: "Agent cache invalidated ... possible
   cross-process write"` en cada mensaje → el gateway reconstruye el agente y recarga todo el
   historial desde state.db en vez de reusar caché.
5. **Overhead por turno** — MCP servers que fallan conexión inicial (3 intentos → parked:
   segundos), `auth.json` root-owned (PermissionError en cada arranque de turno).

## Receta de medición (5 minutos)

```bash
# Identificar la sesión del perfil (NO la state.db central: la del perfil multiplexado)
sqlite3 /opt/data/profiles/<perfil>/state.db "SELECT id, session_key, message_count,
  api_call_count, input_tokens, cache_read_tokens FROM sessions
  ORDER BY started_at DESC LIMIT 5;"

# Latencia y tamaño de entrada por llamada de esa sesión
grep "SESION_ID" /opt/data/logs/agent.log | grep "API call #" | \
  grep -oE "in=[0-9]+ out=[0-9]+ total=[0-9]+ latency=[0-9.]+s"
# Media + cuántas lentas
... | grep -oE "latency=[0-9.]+" | cut -d= -f2 | \
  awk '{s+=$1;n++;if($1>30)x++}END{print "media:",s/n,"s | >30s:",x,"de",n}'

# 429 y su tipo de límite (paralelo-por-llave vs tokens)
grep "429" /opt/data/logs/errors.log | grep -oE "Limit type: [a-z_]+" | sort | uniq -c

# Invalidaciones de caché y overhead por turno
grep "cache invalidated" /opt/data/logs/gateway.log | tail
grep "failed initial connection" /opt/data/logs/agent.log | tail
ls -la /opt/data/auth.json   # owner root = PermissionError por turno

# Fallbacks disponibles del modelo que sufre
grep "No fallback model group" /opt/data/logs/agent.log | tail
```

## Interpretación y fixes (D-I-V-E: backup de config antes de tocar)

| Dato medido | Causa | Fix |
|---|---|---|
| in=30-55K por llamada | Contexto de canal inflado | `/clear` + lectura de archivos bajo demanda |
| 429 `max_parallel_requests` | Bucket de llave compartido | Auxiliares a otro proveedor; escalonar crons |
| "No fallback model group" | Modelo sin fallback | Configurar fallback o cambiar modelo del perfil |
| "cache invalidated" por turno | Recarga completa del historial | Reportar a Chucho (puede ser bug/condición de carrera) |
| PermissionError auth.json / MCP parked | Overhead por turno | `chown` del archivo; desactivar MCP no usado |

## Pitfalls

- **Diagnosticar mirando solo la ventana del usuario**: en el caso real no hubo 429 durante su
  sesión — el dominante fue el contexto (#1). Los 429 son intermitentes y dependen del paralelismo.
- **Culpar al modelo recién rotado**: la rotación de modelos no cambia el bucket de rate-limit
  (es por llave) ni el tamaño del contexto del canal.
- **Buscar la sesión en la state.db central**: con multiplex, cada perfil tiene su propio
  `profiles/<p>/state.db`. La central muestra la sesión como vacía (1 mensaje session_meta).
- **bg-review invisible**: el revisor automático de Hermes gasta llamadas del mismo bucket
  (caso real: 7 llamadas / 685K tokens por una sola respuesta de Bragi). Contarlo al explicar
  lentitud cuando hay varios bots activos.

## Verification

- Tras `/clear`: nueva sesión en `profiles/<p>/state.db` con `input_tokens` bajo en la primera
  llamada API del canal.
- Tras mover auxiliares a otro proveedor: 429 `max_parallel_requests` dejan de crecer en
  `errors.log` en horas de crons paralelos.

## References

- `references/caso-bragi-2026-08-27.md` — evidencia completa del caso real: tablas de causas,
  comandos ejecutados, métricas de la sesión (171 llamadas, media 21,8 s, máx 104 s).
