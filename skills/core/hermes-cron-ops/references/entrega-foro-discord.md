# Informe recurrente en un foro de Discord + entrega por cron

Patrón verificado (03-nov-2026): estudio semanal de actualizaciones de Hermes
entregado los lunes 6:30 al hilo `📦 Actualizaciones de Hermes — estudio
semanal` del foro `🖥️・sistema-servers`.

## 1) Crear el post del foro con el primer informe ya dentro

Un `POST /channels/{forum_id}/threads` con `message` crea el hilo **y** publica
el informe de la primera corrida como mensaje raíz. Los tags van en el mismo
body: nada de PATCH posterior si los IDs son correctos.

```python
body = {
    "name": "📦 Actualizaciones de Hermes — estudio semanal",
    "auto_archive_duration": 10080,          # 7 días
    "applied_tags": [TAG_SERVICIO, TAG_DEV], # IDs reales del foro
    "message": {"content": informe_markdown},
}
# POST https://discord.com/api/v10/channels/{forum_id}/threads
# headers: Authorization: Bot <token>, User-Agent: DiscordBot (https://..., 1)
```

El `id` de la respuesta **es** el `thread_id`. Leer los IDs de tag desde
`GET /channels/{forum_id}` → `available_tags[]` (nombre → id), nunca a ojo.

## 2) Apuntar el cron al hilo

```bash
hermes cron create "30 6 * * 1" --script <script>.py --no-agent \
  --deliver "discord:<thread_id>" --name <nombre-del-job>
```

- `--no-agent`: el stdout del script es el mensaje. Sin LLM de por medio →
  determinista y barato.
- Verificar en `jobs.json` que quedaron `deliver`, `schedule.expr`, `script`,
  `enabled: true` y un `next_run_at` futuro y correcto (aquí: lunes 06:30
  → `2026-11-09T06:30:00-05:00`).

## 3) Reglas de contenido del script

- **≤1900 chars de stdout**: es un único mensaje de Discord. El detalle largo va
  a un archivo (`/opt/data/logs/<job>-latest.md`) y el mensaje solo lleva lo
  accionable: estado, veredicto, y la frase de autorización.
- **Imprimir siempre**: envolver `main()` en `try/except` que imprima el error
  como primera línea del informe. Un script que revienta sin stdout deja el job
  en verde y el canal en silencio.
- **Cerrar con la acción**: el último bloque del informe dice qué responder para
  autorizar el siguiente paso (p.ej. `AUTORIZO ACTUALIZAR v0.22.6`) y aclara qué
  NO se hace sin un segundo OK (despliegue).

## 4) Verificación de cierre

```python
GET /channels/{thread_id}          # name, parent_id == forum_id, applied_tags, auto_archive_duration
GET /channels/{thread_id}/messages?limit=5   # el informe está y empieza como se espera
```

Y limpiar cualquier archivo temporal con el token (`/tmp/.dtok`) al terminar.

## Pitfalls

- **`deliver` espera el `thread_id`, no el `forum_id`**: entregar al foro crea
  posts sueltos por corrida en vez de mantener el histórico en un hilo.
- **Un hilo de foro sin actividad se archiva**: 10080 s (7 días) cubre la
  cadencia semanal sin reabrir; si la cadencia es mensual, subir a 43200 (30 d)
  o aceptar el unarchive.
- **`applied_tags` con un ID de otro foro** devuelve 400 y el hilo no se crea:
  validar contra `available_tags` del foro destino.
