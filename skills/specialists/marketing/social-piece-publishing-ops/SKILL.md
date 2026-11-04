---
name: social-piece-publishing-ops
description: "Use when publishing or verifying social posts."
tags: [composio, instagram, facebook, publicacion, verificacion, social]
version: 1.0.0
author: Ragnar
---

# Social piece publishing ops (Composio)

Clase de trabajo: verificar el estado real de una pieza programada y/o publicarla en IG + FB vía
Composio, en cualquier campaña y cualquier marca. Nació del calendario bingo-sep2026 pero NO es
específico de esa campaña: los mismos chequeos aplican a octubre y a cualquier cliente.

> El calendario bingo-sep2026 (comandos, IDs de Drive, aprobaciones) vive en la skill
> `marketing-calendar-publishing` — esa skill es **user-owned**: para editarla hay que correr
> `hermes curator adopt marketing-calendar-publishing`. Esta skill es la capa de verificación /
> publicación reutilizable.

## Protocolo de verificación (antes de afirmar qué sale hoy)

Nunca responder "hoy sale X así" leyendo una sola fuente. Verificar **tres**:

1. JSONL canónico local: `<repo>/planning/<campaña>/calendario.jsonl`
2. XLSX espejo Golden (Drive)
3. XLSX espejo Lucky (Drive)

Si el espejo está atrasado o el humano escribió ahí, el local y Drive divergen y el sync aún no corrió.
Un solo comando: `scripts/check_calendar_rows.py <fecha|substring-del-id>` (imprime las tres).

Además, para piezas multi-imagen: el nº de slides y su orden están en `slides[]` del JSONL y son
el orden de publicación (IG y FB). Confirmarlo, no asumirlo.

## Pre-flight por tipo de pieza (estreno de un slug)

Antes de la PRIMERA vez que una campaña publica un tipo nuevo de pieza, comprobar que el slug de
Composio existe y leer su doc (los slugs cambian y algunos quedan deprecados):

```
composio tools list instagram | grep -i '<carousel|story|reel|container>'
composio tools list facebook  | grep -i '<multi_photo|photo|video>'
composio search "instagram carousel container" --toolkits instagram
```

Advertencia: `composio search` devuelve *planes semánticos*, no el catálogo — un slug válido puede
no aparecer entre sus `related_tool_slugs`. Para confirmar existencia, `composio tools list <toolkit>`.

## Mapa de publicación (flow vigente, verificado 12-sep-2026)

| Tipo | Instagram | Facebook |
|---|---|---|
| reel | container REELS (`share_to_feed`) → publish | `FACEBOOK_CREATE_VIDEO_POST` (`file_url` pública) |
| post 1:1 | container photo → publish | `FACEBOOK_CREATE_PHOTO_POST` |
| **carrusel (N slides)** | **`INSTAGRAM_CREATE_CAROUSEL_CONTAINER`** (`child_image_urls` en orden) → `INSTAGRAM_CREATE_POST` | **`FACEBOOK_CREATE_MULTI_PHOTO_POST`** (`photo_urls`, N URLs) |
| story | container STORIES → publish | sin API de stories de página → solo IG |

**Carrusel = UN solo post con las N fotos juntas**, nunca slide por slide. Si alguien pide "las 4
fotos al tiempo", la respuesta es ese mapa, con evidencia, no una promesa.

Detalle, slugs, pitfalls de la doc de Composio y fallback: `references/composio-carousel-publishing.md`.

## Verificación read-back (publicado ≠ verificado)

Después de publicar — y **antes** de decirle al Admin "salió" — leer el objeto desde la API real:
el JSONL, el XLSX y el log del script solo dicen lo que el script *creyó* hacer. Recetas y slugs en
`references/composio-readback-verification.md`; probe re-ejecutable en `scripts/verify_published_piece.py`.

- **Story** → `INSTAGRAM_GET_IG_USER_STORIES` (sin argumentos) devuelve las stories **vivas** con
  `permalink` + `timestamp`: es la única prueba de que la historia está arriba (y de a qué hora salió).
- **Post/carrusel IG** → `INSTAGRAM_GET_IG_USER_MEDIA` exige `ig_user_id` **numérico**, no el alias
  de la cuenta Composio.
- **Post FB** → `FACEBOOK_GET_PAGE_POSTS` exige `page_id`. Comparar `created_time` (UTC) contra el
  slot: dos posts del mismo copy el mismo día = **duplicado**.
- Cuentas: los alias Composio y los IDs numéricos (`IG_USER`, `FB_PAGE`) se leen de `publish.py` del
  repo de campañas, no de memoria.

### Pitfall que ya produjo un falso negativo — "0 filas" ≠ "no se publicó"

`composio execute` responde **inline** o **guardando la salida en archivo** (`"storedInFile": true` +
`outputFilePath`, payloads de decenas de miles de tokens). Un parser que solo lee el JSON inline
obtiene **0 filas** y parece que nada se publicó. Regla: si viene `outputFilePath`, leer ese archivo
(ruta del contenedor `/tmp/composio/...` = `/host/tmp/composio/...` desde el host) y parsear de ahí.
Verificado 12-sep-2026: la story estaba arriba y el primer parser dijo "0 stories".

### Falso negativo con curl a la URL pública

`https://www.instagram.com/p/<shortcode>/` responde **HTTP 200 exista o no** el post (login wall):
no sirve para verificar un borrado. La prueba válida es la **lista por API** — un post borrado
simplemente **no aparece** en `INSTAGRAM_GET_IG_USER_MEDIA`; en FB, la ausencia del `id` en
`FACEBOOK_GET_PAGE_POSTS`.

## Publicar fuera del tick (pieza ya aprobada, el Admin espera ahora)

El tick es horario y la ventana cierra a slot + 2 h, así que "aprobadas las historias para hoy" a
las 12:11 con slot 12:00 exige publicar ya, no esperar. Secuencia (sin duplicar y sin saltarse el
registro):

1. **Aprobar con el helper de la campaña** (`approve_ids.py <id>…`, primero `--dry-run` para
   confirmar que las filas son aprobables): marca estado, regenera XLSX, lo sube a **ambas** copias
   de Drive y commitea/pushea. Si no se sube el XLSX, el sync de la mañana revierte la aprobación.
2. **Ejecutar el MISMO wrapper que corre el cron** de publicación (no `publish.py` a mano ni un
   POST propio): así el camino de estado → registro → dashboards → XLSX → commit es idéntico al
   automático y se conserva la guardia anti-duplicado (`media_ids` presente ⇒ no republicar).
3. **Read-back por API** (sección de arriba) y recién entonces reportar, con los permalinks.

Correr estos scripts como el uid del gateway (`hermes`, 10000) desde su vista del repo, no como
root: root deja artefactos y compite con el gateway por el mismo JSONL.

## Ventanas de publicación (asimetría real — no documentarla mal)

El cron de publicación usa `0 <= ahora - slot <= 2 h`: solo publica **desde** el slot y hasta 2 h
después. Otro helper (`publish.py --due`) usa `abs(ahora - slot) < 2 h`.
Consecuencia práctica: **aprobar después de slot + 2 h = la pieza no sale ese día** (no hay catch-up).
Al pedir aprobación, dar la hora límite junto al slot (slot 11:00 → límite 13:00) y decir que el
tick es horario, no instantáneo.

## Peticiones cortas del Admin ("modificar las publicaciones para hoy…")

El Admin encarga por frases cortas sin contexto y a veces en otro canal/día. Protocolo:

1. Reconstruir el referente con datos vivos (`scripts/check_calendar_rows.py`), nunca preguntar a ciegas.
2. Responder con el estado verificado (piezas, slots, estado, nº de slides).
3. Hacer **UNA** pregunta de desambiguación, ofreciendo la opción más probable primero.
4. Distinguir explícitamente **aprobación/publicación** de **cambio de contenido** (fotos nuevas,
   orden, copy). "Modificar" NO significa automáticamente aprobar; publicar es de alto impacto y
   exige confirmación explícita igual.
5. Cada afirmación con su artefacto: comando + salida, no "ya está".

## Pitfalls

1. **`OAuthException 9007` al publicar carrusel:** los child containers deben llegar a `FINISHED`
   antes de publicar el padre. Poll con `INSTAGRAM_GET_POST_STATUS` (3-5 s, backoff) y re-publicar;
   un `creation_id` es de un solo uso — si el contenedor quedó en `ERROR`, recrearlo (no re-subir assets).
2. **HTTP 400 "media could not be fetched"** en contenedores cuando la URL no es pública o redirige:
   hostear los assets en el portal y publicar desde URL pública.
3. **`notify` en tools de FB:** bool/list, nunca el string `"True"`.
4. **Insights:** el media_id de Facebook va **con prefijo de página** (`<page_id>_<post_id>`); con el
   id pelado Meta responde `400 · code 200 · subcode 1504029 "Permissions error"` — engañoso, es
   resolución de objeto, no scopes, y la pieza queda con 0 vistas. Los insights de carrusel se
   consultan en el **padre** (los children no soportan insights).
5. **Ruta de credenciales Drive:** `_first_existing()` con candidatos host (`/root/hermes-agent-legacy-docker/data/secrets/…`)
   y contenedor (`/opt/data/secrets/…`); `scopes` puede venir como string → envolver en lista
   antes de `Credentials(...)`. `Path.exists()` sobre rutas del contenedor desde el host puede
   LANZAR PermissionError en vez de devolver False.
6. **Entorno dual host/gateway:** los crons corren en el contenedor (uid 10000); un `setpriv` en mi
   namespace da falsos verdes — validar con `nsenter` al namespace del gateway.
7. **Composio desde el contenedor:** el shim `/opt/data/.local/bin/composio` **sí funciona** desde
   el uid del gateway (10000) — pero hay que ponerlo en `PATH` (`export PATH=/opt/data/.local/bin:$PATH`);
   no viene en el PATH por defecto y `command -v composio` falla. El binario nativo hace core dump
   dentro del contenedor: usar el shim, no reinstalar nada.
8. **`composio search` no es catálogo:** devuelve 0 resultados con frases normales ("instagram list
   stories" → vacío). Para confirmar que un slug existe, `ls <HERMES_HOME>/.composio/tool_definitions/`
   o `composio tools list <toolkit>`. Y leer el schema antes de ejecutar: los tools de solo-lectura
   también exigen parámetros (`page_id`, `ig_user_id`) — el error de validación dice cuál falta.

## Soporte

- `references/composio-carousel-publishing.md` — slugs verificados, plan y pitfalls de Composio, fallback.
- `references/composio-readback-verification.md` — comprobar qué quedó REALMENTE publicado (IG stories/media, FB posts) y los falsos negativos conocidos.
- `scripts/check_calendar_rows.py` — estado de una pieza en las tres fuentes (JSONL + ambos XLSX Drive).
- `scripts/verify_published_piece.py` — read-back por API: stories vivas, media reciente y posts de la página FB de una marca (resuelve inline vs `outputFilePath`).
