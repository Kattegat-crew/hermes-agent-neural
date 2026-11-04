# Carrusel / multi-foto en Composio — datos verificados

Verificado 2026-09-12 en el host DEV, justo antes del primer carrusel de la campaña bingo-sep2026
(primer estreno de ese tipo de pieza: los slugs no se habían ejercitado nunca).

## Slugs confirmados

`composio tools list instagram | grep -i carousel`

- `INSTAGRAM_CREATE_CAROUSEL_CONTAINER` — "Create a draft carousel post with multiple images/videos
  before publishing. Instagram requires carousels to have between 2 and 10 media items. Container
  creation_ids expire in under 24 hours, so publish promptly after creation."
- `INSTAGRAM_CREATE_MEDIA_CONTAINER` — marcado **DEPRECATED** (sugiere `INSTAGRAM_POST_IG_USER_MEDIA`)
  pero sigue operativo; es el que usa el flow para reel/post/story.
- `INSTAGRAM_CREATE_POST` — marcado **DEPRECATED** (sugiere `INSTAGRAM_POST_IG_USER_MEDIA_PUBLISH`)
  pero sigue operativo; trae retry con backoff exponencial (~44 s) cuando el contenedor no está listo.
- `INSTAGRAM_GET_POST_STATUS` — poll de estado del contenedor (FINISHED/ERROR).
- `INSTAGRAM_GET_IG_MEDIA_CHILDREN` — verificación posterior del carrusel (nº y orden de slides).

`composio tools list facebook | grep -i multi_photo`

- `FACEBOOK_CREATE_MULTI_PHOTO_POST` — existe. Nota: `composio search "facebook multi photo post"`
  NO lo lista entre sus slugs relacionados (propone `FACEBOOK_UPLOAD_PHOTOS_BATCH` + `FACEBOOK_CREATE_POST`)
  — la búsqueda semántica no es un catálogo; confirmar con `tools list`.
- `FACEBOOK_CREATE_PHOTO_POST`, `FACEBOOK_CREATE_VIDEO_POST`, `FACEBOOK_CREATE_PHOTO_ALBUM` — existen.
- `FACEBOOK_GET_POST` — verificación posterior (nº de subattachments).

## Pitfalls de la doc de Composio aplicables a nuestro flow

- Carousel: **todos los child containers deben alcanzar FINISHED** antes de publicar el padre.
  El flow crea el padre y publica enseguida → depende del retry interno de `INSTAGRAM_CREATE_POST`.
  Ante `OAuthException 9007` (HTTP 400): poll con `INSTAGRAM_GET_POST_STATUS` cada 3-5 s con backoff
  (evita 613 / code 4 / HTTP 429) y re-publicar. `creation_id` es de un solo uso; si el contenedor
  quedó en `ERROR`, recrearlo.
- `INSTAGRAM_CREATE_CAROUSEL_CONTAINER` → HTTP 400 "media could not be fetched" con URLs no públicas,
  expiradas o con redirect: por eso los assets se sirven desde el portal público (sin SSO).
- Fallback del plan de Composio: crear cada slide con `INSTAGRAM_POST_IG_USER_MEDIA` y reintentar el
  padre con los `children` ordenados.
- Ritmo: respetar `INSTAGRAM_GET_IG_USER_CONTENT_PUBLISHING_LIMIT` si se publican varias piezas seguidas.

## Cómo lo hace el flow del repo (planning/calendario-sep2026/publish.py)

```
tipo == 'carrusel'  →  files = [drive(s['drive_id']) for s in row['slides']]
                    →  _to_portal(files)            # URLs públicas
IG:  INSTAGRAM_CREATE_CAROUSEL_CONTAINER{ig_user_id, caption, child_image_urls, share_to_feed}
     → INSTAGRAM_CREATE_POST{ig_user_id, creation_id}
FB:  FACEBOOK_CREATE_MULTI_PHOTO_POST{page_id, message, photo_urls}
```

El orden del carrusel = el orden de `slides[]` en el JSONL, que viene del inventario de Drive
(`Carrusel 1/Carru-1..4.png` golden, `crr-1..4.png` lucky). El caption de carrusel suele abrir con
"Desliza: …", lo que confirma que la pieza es un carrusel y no N posts sueltos.
