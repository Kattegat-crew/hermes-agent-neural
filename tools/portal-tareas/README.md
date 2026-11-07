# Portal de tareas

Tablero de pendientes de la flota, servido en `https://reels.neuralcrewlabs.com/tareas/`
detrás del SSO (Pocket ID, grupo `admins`).

Tres listas por dueño — **Jonathan**, **Chucho** y **Compartido** — más un mensaje
fijado en Telegram que se reescribe solo cuando cambia algo.

## Por qué existe

El store canónico de pendientes (`brain/tasks/pending.jsonl`) ya era la fuente de
verdad, pero solo se podía leer por CLI. Este portal da una vista operable sin
crear un segundo sistema: **lee y escribe el mismo archivo** que usa
`scripts/pending_tasks.py`.

## Arquitectura

```
navegador ──HTTPS──> nginx-proxy-manager (PROD, :443, vhost reels)
                         │  auth_request /oauth2/auth  (Pocket ID)
                         │  location ^~ /tareas/
                         ▼
              http://100.86.8.81:8791   (DEV, red Tailscale)
                         │
                  server.py (systemd: portal-tareas.service)
                         │
                  brain/tasks/pending.jsonl  ← misma fuente que la CLI
```

El bloque `location ^~ /tareas/` vive en
`/opt/docker/nginx-proxy-manager/data/nginx/proxy_host/20.conf` (PROD). Se usa
`^~` para que gane sobre la regla de bypass de estáticos que ya tiene ese vhost.

## Invariantes del store

1. **Nada se borra.** «Quitar» en el portal cierra la tarea con evidencia y autor.
2. **Escritura atómica bajo lock.** `_store_lock()` en `pending_tasks.py` y
   `mutate()` aquí toman el mismo `pending.jsonl.lock`. Sin eso, el portal y un
   script que corran a la vez se pisan (cada uno lee-modifica-guarda el archivo
   entero y gana el último).
3. **Todo cambio deja rastro** en `brain/tasks/.portal-events.jsonl`.

## API

| Método | Ruta | Uso |
|---|---|---|
| GET | `/api/tasks` | Lista abiertas + contadores por dueño + `mtime` |
| GET | `/api/health` | Estado y actor detectado |
| POST | `/api/tasks` | Alta `{tarea, dueno, prioridad, area, nota}` · 409 si duplicada |
| PATCH | `/api/tasks/{id}` | `{estado, dueno, tarea, prioridad, nota}` |
| POST | `/api/tasks/{id}/close` | Cierre con `{evidencia}` |
| DELETE | `/api/tasks/{id}` | Cierre marcado como «quitada» |

El actor se toma de `X-Auth-Request-Email` (lo inyecta oauth2-proxy); en local cae
a `local`.

## Mensaje fijado de Telegram

`telegram_pin.py` mantiene **un solo mensaje** y lo edita en su sitio — no manda
uno nuevo por cada cambio. Usa un hash del contenido: si nada cambió, no llama a
la API. El `message_id` se guarda en `brain/tasks/.telegram-pin.json`.

Se dispara por dos vías:

1. **Inmediata:** el portal lanza el script en un hilo tras cada mutación.
2. **Respaldo:** `portal-pin.timer` cada 2 minutos, para los cambios hechos por
   la CLI o por otros agentes.

## Despliegue

```bash
# código canónico: este repo (rama feat/portal-tareas)
# runtime:
cp server.py telegram_pin.py /opt/hermes-agent-data/tools/portal-tareas/
cp -r static /opt/hermes-agent-data/tools/portal-tareas/

systemctl restart portal-tareas.service   # DEV
```

Variables: `PORTAL_STORE`, `PORTAL_EVENTS`, `PORTAL_PORT`, `PORTAL_BIND`.

## Reversión

- Portal: `systemctl disable --now portal-tareas.service portal-pin.timer` y borrar
  `/opt/hermes-agent-data/tools/portal-tareas/`.
- Ruta pública: restaurar el backup
  `20.conf.bak-portal-tareas-<ts>` y `docker exec nginx-proxy-manager nginx -s reload`.
- El store no se toca en ningún caso.
