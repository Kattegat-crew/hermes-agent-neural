# Session-expiry recovery — caso real y cadena de comandos

Caso (10-sep-2026): el usuario escribió `Listo guarda` por WhatsApp a las 17:00. La sesión de WhatsApp había
expirado a las 16:23 (auto-reset por inactividad, 120 min) y el trabajo vivo estaba en la sesión de Telegram
(última actividad 16:21). El agente arrancó en frío con una sola palabra y tuvo que reconstruir el referente
antes de guardar nada.

## 1 — Sesiones recientes

```
session_search()          # sin query = browse, ordenado por actividad
```

Manda `last_active`, no el inicio de conversación. Anotar `session_id` y `source`.

## 2 — Leer la sesión candidata

```
session_search(session_id="20260910_154928_b1c42439")
```

Si es grande, el volcado completo queda en `/opt/data/cache/spillover/<file>.txt` y hay que procesarlo con
`execute_code` (`json.loads` sobre el bloque que empieza en `{"success": true`). No re-pedirlo por API.

## 3 — DB directo

```python
import sqlite3, time
con = sqlite3.connect("file:/opt/data/state.db?mode=ro", uri=True)
cur = con.cursor()
cur.execute("""SELECT id, session_id, substr(content,1,300), timestamp
                FROM messages WHERE timestamp > ? AND role='user'
                ORDER BY timestamp DESC LIMIT 25""", (time.time() - 4*3600,))
```

`messages.session_id` = id lógico de la sesión (`20260910_170028_bf83f812`); `sessions.id` es la PK.

## 4 — Timeline real de canales

```bash
grep 'inbound message' /opt/data/logs/gateway.log | tail -25
grep -n 'Session expiry'  /opt/data/logs/gateway.log | tail -5
```

Da `platform=`, `user=`, `chat=` y texto por mensaje; incluye lo que NO llegó a sesión (voz `[ptt received]`,
audios que no se descargaron, enlaces). Las líneas de expiración confirman qué canal se cerró y cuándo
(`Session expiry: 1 sessions to finalize (whatsapp:1)`). Al recrear la sesión el gateway deja:
`routing key … is ended in state.db but still live in sessions.json; dropping stale entry`.

## 5 — Responder

1. Decir qué se reconstruyó y de dónde (sesión, canal, hora).
2. Referente claro → ejecutar. Ambiguo → UNA pregunta con opciones concretas (`clarify`).
3. Incluir siempre la salida "era otra cosa / algo que dije en un audio que no llegó".

Lección: preguntar con opciones una vez es aceptable; guardar documentación inventada sobre un referente
supuesto NO lo es.
