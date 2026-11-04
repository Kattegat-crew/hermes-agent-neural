# Caso real: Bragi lento — diagnóstico del 27/08/2026

## Síntoma reportado por el Admin
"Me parece anormal la cantidad de tiempo que toma en responder" — trabajando con Bragi en los
canales de Discord de los bots, tareas cortas tardaban demasiado.

## Métricas medidas

### Sesión afectada (canal Discord campaña Bingo, agent:bragi:discord:group:1542126606900920340)
- Sesión `20260827_213224_6507f2ff` en `/opt/data/profiles/bragi/state.db`
- 345 mensajes, 146 llamadas API, 909K input tokens, 5.6M cache_read
- Latencia por llamada: **media 21,8 s** (171 llamadas), 40 llamadas >30 s, **máx 103,9 s**
- Entradas por llamada: 33-55K tokens (infladas por el historial del canal: "agarra contexto
  de la campaña" lo volvió a desplegar todo en el chat)

### 429 del bucket compartido (2 días de errors.log)
- 33 errores 429, pico de 13 en una hora (26/08 12:xx)
- Tipo de límite: `max_parallel_requests` — Current limit: 5 — **por API key, no por modelo**
- Modelos golpeados: deepseek-v4-flash (11), qwen3.8-flash (3) → la rotación de modelos
  NO alivia porque todos comparten la llave NaN

### Fallbacks
- 22:39 glm5.3-flash: `provider_unavailable` → "No fallback model group found for
  original model_group=glm5.3-flash. Fallbacks=[{'deepseek-v4-flash': ['qwen3.6']}]"
  (litellm del provider solo tiene fallback para deepseek)

### Caché e invalidaciones
- En CADA mensaje: `gateway.run: Agent cache invalidated for session agent:bragi:...:
  message_count changed (1 -> 284), possible cross-process write`
- Dos sesiones alternando el mismo canal (`6507f2ff` y `81a4dcf6`) — el ID en el log del turno
  no corresponde al canal del bot

### Overhead por turno
- MCP `gmail`: "failed initial connection after 3 attempts, parking" — repetido cada ~5 min
- `/opt/data/auth.json` root-owned: PermissionError + traceback en cada arranque de turno

### bg-review (revisor automático)
- 00:03-00:07: `Background review complete: calls=7 in=19947 out=11295 cache_read=685056`
  — 7 llamadas y 685K tokens del MISMO bucket de la llave, por una sola respuesta de Bragi

## Cargas del momento
- 12 perfiles bajo multiplex (default + 8 dioses + comms + roshi + vigia)
- 8 de ellos en qwen3.8-flash (misma llave), crons escalonados 00:00-00:48
- Todas las llamadas auxiliary (compression/vision/web_extract/title) contra NaN

## Lección principal
Durante la ventana activa del usuario NO hubo 429 — el factor dominante fue el contexto del
canal (#1) multiplicado por pasos de herramienta. Los 429 son un riesgo de paralelismo
(crons + varios chats), no explican todo. Medir por sesión ANTES de proponer fixes.

## Fixes propuestos al Admin (27/08, pendientes de OK)
1. Inmediato: `/clear` en el canal de Bragi; que el bot lea campaign.yaml/fichas bajo demanda.
2. Config (D-I-V-E con backup): mover auxiliary.* a B.AI deepseek-v4-flash (gratis) para
   liberar los 5 slots de NaN para los chats interactivos.
3. `chown` de auth.json + desactivar MCP gmail en perfiles que no lo usan.
4. Fallback para glm5.3-flash (o volver default a qwen3.8-flash); threshold de compresión más
   agresivo en canales Discord (con ventana 1M el umbral 0.25 nunca dispara).
