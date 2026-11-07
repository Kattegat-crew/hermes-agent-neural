---
name: portal-tareas
description: Use when asked about pendientes or the pinned list.
version: 1.0.0
author: Ragnar
license: proprietary
metadata:
  hermes:
    tags: [kanban, pendientes, telegram, nginx, sso]
    related_skills: [hermes-agent, hermes-config-integrity]
---

# Portal de tareas (kanban de pendientes)

## When to Use

- El Admin pregunta por pendientes, la lista de tareas, el tablero o «qué falta».
- Hay que añadir, cerrar, reasignar o reabrir un pendiente.
- El portal no carga, no deja añadir, o el enlace `/tareas` da 404.
- Hay que tocar el mensaje fijado de Telegram de pendientes.

Tablero vivo de pendientes de la flota, en `https://reels.neuralcrewlabs.com/tareas/`
(detrás del SSO Pocket ID, grupo `admins`: entran Jonathan y Chucho).

## La regla que manda

**Hay UN solo store.** `brain/tasks/pending.jsonl`. El portal, la CLI
(`scripts/pending_tasks.py`) y los agentes leen y escriben el mismo archivo.
Nunca crear un segundo sistema de pendientes, ni una copia, ni un espejo.

Si un pendiente aparece en el chat y no en el store, el store es el que manda:
se añade allí.

## Invariantes

1. **Nada se borra.** Chulear cierra; «Quitar» cierra con evidencia. Todo se
   puede reabrir desde la sección «Cerradas» de su columna.
2. **Un dueño por tarea**: `jonathan`, `chucho` o `compartido`. Si hay duda, al
   dueño que ejecuta, no al que decide — pero la palabra del Admin manda.
3. **Escritura atómica bajo lock compartido** (`pending.jsonl.lock`).
   `_store_lock()` en la CLI y `mutate()` en el server toman el mismo lock. Sin
   eso, dos escritores se pisan: cada uno lee-modifica-guarda el archivo entero
   y gana el último.
4. **Todo cambio deja rastro** en `brain/tasks/.portal-events.jsonl`.

## Arquitectura

```
navegador → nginx-proxy-manager (PROD :443, vhost reels)
              auth_request /oauth2/auth  (Pocket ID)
              location ^~ /tareas/
                → DEV por Tailscale, puerto 8791
                    → server.py (portal-tareas.service)
                        → brain/tasks/pending.jsonl
```

- Código canónico: repo `hermes-agent`, rama `feat/portal-tareas`,
  worktree en `fleet/worktrees/hermes-agent/portal-tareas/tools/portal-tareas/`.
- Runtime: `/opt/hermes-agent-data/tools/portal-tareas/`.
- Servicios en DEV: `portal-tareas.service` (server) y `portal-pin.timer`
  (cada 2 min refresca el fijado de Telegram).
- Bloque nginx: `/opt/docker/nginx-proxy-manager/data/nginx/proxy_host/20.conf`
  en PROD, con backups `.bak-portal-tareas-<ts>`. Se usa `^~` para ganar sobre
  la regla de bypass de estáticos del vhost.
- La IP de Tailscale de DEV está en memoria (#2). El backend escucha solo en ella,
  nunca en 0.0.0.0.

## Pitfalls que ya costaron un bug

- **Rutas relativas siempre.** La página se sirve en `/tareas/`, así que
  `fetch('/api/tasks')` pega en la RAÍZ del dominio (404 de reels-web), no en el
  backend. Va `fetch('api/tasks')`. Si el portal carga vacío y no deja añadir,
  es esto.
- **`location ^~ /tareas/` no casa con `/tareas` sin barra** → hace falta
  `location = /tareas { return 301 /tareas/; }`.
- **Nginx Proxy Manager puede regenerar `20.conf`** si alguien edita ese host en
  su interfaz: la regla `/tareas/` desaparece y el enlace da 404. Se vuelve a
  poner con el mismo bloque.
- **La prueba mínima de UI es la ruta del cliente.** Un `curl` 200 a un
  endpoint cercano solo prueba que el servidor responde, no que la interfaz
  funcione (los bugs de rutas los encontró el Admin, no el curl, porque el
  backend loguea 200 y el error ocurre en el fetch del navegador). Antes de dar
  un cambio de frontend por bueno: abrir la página servida o pedir exactamente
  la ruta que hace el `fetch()` del JS desde el origen de la página.
- **Cerrar algo debe verse, no desaparecer.** Cualquier acción que saque un ítem de la
  vista (chulear, quitar) necesita un lugar visible adonde ir y un aviso que lo diga.
  «Se borró» y «se movió a Cerradas» se sienten idénticos si no se muestra el destino.
- **Markdown de Telegram rompe** con `_` y `*` en los nombres de tarea: el
  fijado usa `parse_mode=HTML` con escape.

## Mensaje fijado de Telegram

Un solo mensaje (`message_id` guardado en `brain/tasks/.telegram-pin.json`) que
se **edita en su sitio**, nunca se reenvía. Contenido: abiertas por dueño
arriba, «✅ Cerradas hoy» abajo, y el enlace al portal.

Se dispara por dos vías: el portal lo lanza en un hilo tras cada mutación, y
`portal-pin.timer` cada 2 min como respaldo (para cambios hechos por CLI u otros
agentes). Usa hash del contenido: si nada cambió, no llama a la API.

Bot: `@Ragnarsson_lothbot` (el de Ragnar, no el NCA). Token en
`state-snapshots/20261005-165034-pre-update/.env`.

## API

| Método | Ruta | Uso |
|---|---|---|
| GET | `api/tasks` | Abiertas + `cerradas` (40 últimas) + contadores + `mtime` |
| POST | `api/tasks` | `{tarea, dueno, prioridad, area, nota}` · 409 si duplicada |
| PATCH | `api/tasks/{id}` | `{estado, dueno, tarea, prioridad, nota, evidencia}` |
| POST | `api/tasks/{id}/close` | Cierre con evidencia |
| DELETE | `api/tasks/{id}` | Cierre marcado como «quitada» |

El actor sale de `X-Auth-Request-Email` (lo inyecta oauth2-proxy).

## Desplegar un cambio

1. Editar en el worktree.
2. Copiar `server.py`, `telegram_pin.py` y `static/index.html` a
   `/opt/hermes-agent-data/tools/portal-tareas/`.
3. `ssh dev 'systemctl restart portal-tareas.service'`.
4. Verificar de verdad contra el backend: pedir la MISMA ruta relativa que
   hace el `fetch()` del frontend (`api/tasks`), no una absoluta adivinada —
   un 200 de `/api/tasks` en la raíz del dominio no prueba nada del portal.
   Comprobar que devuelve las abiertas y las cerradas.
5. Toda corrección de UX que reporta el Admin queda registrada como requisito
   o pitfall en esta skill, no solo como fix en el código: el fix sin regla se
   repite en el siguiente cambio.

El usuario trabaja en Windows con Chrome: tras un cambio de HTML hay que decirle
**Ctrl+Shift+R**, porque si no ve la versión vieja y reporta un bug que ya no existe.

## Reversión

- Portal: `systemctl disable --now portal-tareas.service portal-pin.timer` y
  borrar `/opt/hermes-agent-data/tools/portal-tareas/`.
- Ruta pública: restaurar `20.conf.bak-portal-tareas-<ts>` y
  `docker exec nginx-proxy-manager nginx -s reload`.
- El store no se toca en ningún caso.
