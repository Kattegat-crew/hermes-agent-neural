---
name: publish-once-integrity
description: Use when a retry could duplicate an external publish.
version: 1.0.0
author: Ragnar
---

# Integridad de publicación (efectos externos no idempotentes)

## Cuándo usar esta skill

Cuando un proceso automático (cron, worker, agente) ejecuta una acción **irreversible en un sistema de terceros**
y esa acción puede repetirse si algo falla después: publicar en redes, enviar email/WhatsApp/SMS, cobrar, crear un
registro externo, disparar un webhook. Señales típicas:

- el estado interno dice "no ejecutado" pero el objeto externo existe (o al revés);
- al final del día hay **duplicados** en la plataforma del cliente;
- hay **dos runtimes** que pueden correr la misma pieza (cron + sesión interactiva, dos perfiles Hermes, ticker del
  host + gateway);
- el paso de registro/commit/dashboard falla y la marca del hecho queda sin escribir;
- la ventana de reintento (`slot ± N horas`, reintento por tick, backoff) es a la vez el mecanismo de recuperación
  **y** la fuente del duplicado.

## Inmutables

1. **Un solo actor por elemento.** Decide quién ejecuta: si el cron puede publicar, la sesión interactiva no
   publica la misma pieza en paralelo (y viceversa). El fleet SÍ corre varios agentes a la vez (cron como agente
   con terminal + sesión del Admin, más perfiles): asume concurrencia y diseña para ella.
2. **El estado no prueba la ejecución; el hecho sí.** Decide con los campos de hecho (`publicado_en`, `media_ids`,
   `post_id`, `sent_at`, `external_id`) más el registry/log de eventos. La ausencia del campo de hecho **no**
   prueba que no se ejecutó.
3. **Nada de validaciones en el camino post-efecto.** Un validador de catálogo (formatos, tipos, enums) que lance
   excepción después de publicar deja el hecho sin registrar → el tick siguiente duplica. Valida **antes** o
   normaliza con alias (`FORMAT_ALIASES = {'carrusel': 'carousel'}`). Envuelve todo el post-proceso
   (XLSX, dashboards, commit, upload) en try/except: **post-publicar no aborta**.
4. **Parsea todas las formas del id que devuelve el provider.** Cada API tiene la suya: `data.id`, `data.post_id`,
   `data.creation_id`, `response.id`. Leer sólo una convierte una publicación exitosa en un "error" reportado
   (y en duplicado al reintentar).
5. **El guard anti-duplicado mira el hecho o la plataforma**, nunca sólo el campo de estado del elemento.
6. **Prevenir es el único control real.** Muchos providers **no** permiten borrar lo publicado por API con los
   tokens de la agencia. Un duplicado significa borrado manual del humano dueño de la cuenta, visible al cliente.

## Protocolo obligatorio antes de reintentar

> Antes de reintentar cualquier acción externa que "falló", lista el estado real en el sistema externo.

1. Lista los objetos del **día** (no del id que crees): `INSTAGRAM_GET_IG_USER_MEDIA`,
   `FACEBOOK_GET_PAGE_POSTS`, bandeja de enviados, `GET /orders?date=`.
2. Compara contra el registry interno: objetos externos vs hechos registrados.
3. Si el objeto externo existe → escribe el hecho (ids + timestamp) en el store y **no** republices.
4. Si no existe → ejecuta una sola vez, con un solo actor, y escribe el hecho de inmediato.
5. Documenta cualquier duplicado ya creado (permalink/ids) y pásalo al humano para borrado manual: nunca lo
   escondas ni lo omitas en el reporte.

## Verificación end-to-end (lo que acepta este usuario)

El Admin **no** acepta "quedó funcionando" por inferencia ni por las pruebas del propio agente: quiere el eslabón
probado en el runtime real y con ids/URLs observables.

- Prueba cada eslabón en el runtime del cron, no en tu namespace:
  `docker exec -u 10000 -e HOME=/opt/data hermes-agent bash /opt/data/scripts/<script>.sh`
  (`setpriv --reuid=10000` en el namespace propio da falsos verdes).
- El cron usa el PATH del `.sh`: invocar el `.py` directo puede dar `FileNotFoundError: 'composio'` aunque el cron
  funcione.
- Para probar la **entrega** a un canal: `docker exec hermes-agent hermes cron run <job>` y luego leer los mensajes
  del canal (`fetch_messages`). No basta `last_status: ok`: una ejecución puede quedar `unknown` con "efectos
  laterales desconocidos" si el owner muere a mitad.
- Cierra con ids y permalinks reales de la plataforma + contadores (p. ej. "31/31 piezas con métricas") y separa
  **medido** de **inferido**.
- Si un mensaje previo tuyo quedó obsoleto (pediste borrar algo que ya no existe), corrígelo explícitamente en el
  siguiente mensaje.

## Cómo reportar este tipo de trabajo (preferencias del Admin)

- Formato: **por eslabón** (fuente → aprobación → ejecución → registro → métricas → entrega), cada uno con una
  línea de evidencia (comando + resultado, o id/URL). Nada de "sistema OK" sin desglose.
- Bloqueadores y riesgos van **antes** del diseño, no después.
- Cierra con **una** recomendación y una sola pregunta de decisión, no una lista de opciones sin ganador.
- Discord/WhatsApp: sin tablas de markdown ni volcados de comandos; bullets y líneas etiquetadas.

## Casos documentados

- `references/composio-ig-fb-carousel.md` — publicar carrusel IG (4 fotos) + multi-foto FB vía Composio: receta
  verificada, matriz del error 400 del contenedor padre, verificación de hijos y el incidente de duplicado del
  12-sep-2026.
