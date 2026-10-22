# Mapa de fuentes: state.db, logs y cron

## state.db (perfil default: `/opt/data/state.db`; perfiles: `/opt/data/profiles/<p>/state.db`)

Abrir siempre en solo-lectura: `sqlite3.connect("file:/opt/data/state.db?mode=ro", uri=True)`.

Tablas útiles:

| Tabla | Para qué |
|---|---|
| `sessions` | PK `id` (= `messages.session_id`); `source` (whatsapp/telegram/discord/cron/local), `chat_id`, `display_name`, `started_at`, `ended_at`, `end_reason`, `message_count`, `tool_call_count`, `title`, `last_activity_at`, `profile_name`, `archived`, `hidden` |
| `messages` | `id`, `session_id`, `role`, `content`, `tool_name`, `tool_calls`, `timestamp`, `display_kind`, `compacted`, `active` |
| `messages_fts` | búsqueda FTS5 sobre el contenido |
| `delivery_obligations` | obligaciones de entrega pendientes (mensajes que debían salir) |
| `async_delegations` | subagentes lanzados en background |
| `gateway_routing` | mapeo ruta (agente:plataforma:chat) → sesión |

Recetas:

```sql
-- últimos mensajes de usuario de todo el perfil (referente de una sesión expirada)
SELECT id, session_id, substr(content,1,300), timestamp FROM messages
WHERE timestamp > ? AND role='user' ORDER BY timestamp DESC LIMIT 25;

-- todo el contenido de una sesión, sin filtrar roles
SELECT id, role, tool_name, content FROM messages WHERE session_id=? ORDER BY id;

-- sesiones de un chat concreto, más recientes primero
SELECT id, chat_id, source, last_activity_at FROM sessions
WHERE chat_id=? ORDER BY last_activity_at DESC LIMIT 10;
```

## Logs

| Ruta | Contenido |
|---|---|
| `/opt/data/logs/gateway.log` | `inbound message:` (plataforma/usuario/chat/texto), `response ready:` (tamaño y tiempo), `Session expiry:`, reconexiones de Discord, errores de entrega |
| `/opt/data/logs/errors.log` | errores agregados |
| `/opt/data/whatsapp/bridge.log` | nivel bridge (conexión Baileys, `link-preview`, `stream errored out`, `url generation failed` con `msgId`) |
| `/opt/data/logs/agent.log` | trazas del agente/tools |

## Crons

- `cronjob_manage(action='list')` → `last_run_at`, `last_status`, `deliver`, `script`, `no_agent`, `enabled`.
- Salida por corrida: `/opt/data/cron/output/<job_id>/<fecha>.md`. `Status: silent (empty output)` = el job NO envió mensaje (watchdog callado); que el job diga `ok` no significa que el usuario recibió algo.
- Definición de jobs: `/opt/data/cron/jobs.json`.
- Esos archivos pueden ser `root:root` → leer con `docker exec hermes-agent cat <path>`.

## Verificación de una entrega

1. `cronjob_manage(action='list')` → confirmar `last_status: ok` y el `deliver` correcto.
2. Leer el archivo de salida de esa corrida y ver si tiene texto (texto = mensaje enviado; vacío = silencio).
3. Cruzar con `gateway.log` cuando la entrega pasa por el gateway.

## Receta de continuidad multi-canal («¿en qué nos quedamos?»)

Cuando el usuario pregunta por un hilo que vivió en OTRO canal (Telegram/WhatsApp/Discord):

1. **Identificar el canal real por el JSON de origen** embebido en el `content` del mensaje del usuario (`{"platform": "telegram", "chat_id": "8709909260", "chat_type": "dm", ...}`) — no asumir el canal actual de la sesión.
2. **Listar las sesiones DM de ese chat:**
   ```sql
   SELECT id, chat_id, source, chat_type,
          datetime(started_at,'unixepoch','-5 hours') AS inicio, message_count
   FROM sessions WHERE chat_id=? AND chat_type='dm'
   ORDER BY started_at DESC;
   ```
   La sesión viva es la de `message_count` alto con `ended_at` NULL. Las columnas de época (`timestamp`, `started_at`) vienen en UTC: convertir SIEMPRE con `datetime(x,'unixepoch','-5 hours')` para Bogotá antes de citar horas.
3. **Leer el último intercambio user→assistant del tema** y barrer por palabras clave para confirmar que no hubo respuestas posteriores del usuario (si las hubo, los pendientes listados ya no están vigentes):
   ```sql
   SELECT id, datetime(timestamp,'unixepoch','-5 hours'),
          substr(replace(content,char(10),' '),1,160)
   FROM messages WHERE role='user' AND timestamp > strftime('%s','YYYY-MM-DD')
     AND (content LIKE '%<tema>%' OR content LIKE '%<sinónimo>%');
   ```
4. **Reportar citando sesión `id` + fecha/hora Bogotá**, separando explícitamente lo ya acordado de lo pendiente de respuesta del usuario. No inventar el estado: si el último turno fue del asistente, decir que no hubo respuesta.
