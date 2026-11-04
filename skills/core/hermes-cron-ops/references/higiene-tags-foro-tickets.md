# Higiene de tags — foro tickets-tecnicos (fix manual)

Contexto del job cron `higiene-tags-tickets-semanal` (script `/opt/data/scripts/higiene_tags_tickets.py`).
El cron es SOLO reporte: nunca corrige tags. Cuando diverge, el fix es manual vía API del bot.

## Convención del foro
- Foro `1554957746980261938`, guild `1493354289266167808`. Hilo excluido: `1554964120003027005` (prueba de menciones).
- Regla: exactamente UNA tag de estado por hilo activo (Pendiente, En curso, En revisión, Cerrado, Bloqueado). Cero o dos = divergencia.
- El estado nominal vive en el mensaje raíz como `**Estado:** <valor>`. Hilos creados antes de esta convención NO tienen la línea: no hay fuente de verdad, decidir por inspección de actividad (plan sin trabajo iniciado ni respuesta humana = Pendiente).
- Al crear un ticket nuevo, incluir `**Estado:**` en el mensaje raíz.

## Receta de fix (verificada 28-oct-2026, 5 hilos PATCH 200 + 0 divergencias)
1. Reusar helpers del script sin ejecutar su main: `src = open("higiene_tags_tickets.py").read().replace("\nmain()", "")` + `exec(compile(src, ...))` → da `_req`, `ESTADOS`, `GUILD` con el token ya resuelto.
2. Hilos activos: `GET /guilds/{GUILD}/threads/active` → `threads[].applied_tags`.
3. Mensaje raíz: `GET /channels/{id}/messages?after=0&limit=1` (el más antiguo) y parsear `**Estado:**`.
4. Aplicar: GET previo de `GET /channels/{id}` para conservar tags existentes, luego `PATCH /channels/{id}` con `applied_tags` = existentes + tag de estado; GET de verificación después.
5. Cierre: re-corrida del script → silencio en stdout = 0 divergencias.

## Pitfalls
- `/guilds/.../threads/active` OMITE la clave `applied_tags` cuando está vacía (dict.get devuelve None); `GET /channels/{id}` del hilo es la lectura fiable.
- `after=0&limit=1` es la única forma fiable de pedir el mensaje más antiguo (el endpoint devuelve newest-first).
- Los IDs de tags de estado están hardcodeados en el script; nunca adivinarlos desde el front-end.