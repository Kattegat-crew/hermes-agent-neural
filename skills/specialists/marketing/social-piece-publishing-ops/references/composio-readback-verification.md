# Read-back por API: qué quedó realmente publicado (IG + FB)

Verificado en vivo el 12-sep-2026 (campaña bingo-sep2026: Golden Game / Lucky Brothers).
Sirve para cualquier campaña: solo cambian cuentas e IDs.

## Por qué existe

El JSONL del calendario, el XLSX de Drive y el stdout del script registran lo que el **script**
creyó hacer. La única prueba de que el objeto está arriba es leerlo por la API. Regla de casa:
nada se reporta como publicado sin read-back.

## Slugs y parámetros (los que funcionan)

| Objeto | Tool Composio | Parámetros mínimos | Qué devuelve |
|---|---|---|---|
| Stories vivas IG | `INSTAGRAM_GET_IG_USER_STORIES` | **ninguno** (la cuenta va en `--account`) | `id`, `media_type`, `timestamp`, `permalink` de la story |
| Media reciente IG | `INSTAGRAM_GET_IG_USER_MEDIA` | `ig_user_id` (**numérico**), `limit` | `id`, `media_type` (incl. `CAROUSEL_ALBUM`), `timestamp`, `permalink` |
| Posts de página FB | `FACEBOOK_GET_PAGE_POSTS` | `page_id`, `limit` | `id` (`<page>_<post>`), `created_time` (UTC), `message`/`story`, `permalink_url` |
| Hijos de un carrusel | `INSTAGRAM_GET_IG_MEDIA_CHILDREN` | `ig_media_id` | ids de las N imágenes, en orden |
| Estado de un contenedor | `INSTAGRAM_GET_POST_STATUS` | `creation_id` | `FINISHED` / `ERROR` (polling antes de publicar el padre) |

Las stories **no** aparecen en `INSTAGRAM_GET_IG_USER_MEDIA` (son otro endpoint) y los posts
borrados **no** aparecen en ninguna de las dos listas.

## Cuentas e IDs (fuente: `publish.py` del repo de campañas)

```
IG_USER = {'golden': '40006158832316994', 'lucky': '27571270162548342'}
FB_PAGE = {'golden': '820898971112738',  'lucky': '765896786617957'}
# alias Composio (--account)
instagram: golden -> instagram_demal-molala ; lucky -> instagram_scot-linked
facebook : golden y lucky -> facebook_uncite-skyish
```

Los alias de cuenta Composio NO son el `ig_user_id`: pasar el alias donde se espera el id numérico
da `Input validation failed … does not have required property "ig_user_id"`.

## Falsos negativos conocidos (los dos ya me mordieron)

1. **Respuesta en archivo.** `composio execute` puede devolver `{"successful": true,
   "storedInFile": true, "outputFilePath": "/tmp/composio/adhoc_*/<TOOL>_OUTPUT_*.json",
   "tokenCount": 15586}` **sin** payload inline. Parsear solo el JSON inline ⇒ **0 filas** ⇒ "no se
   publicó". Leer `outputFilePath` (desde el host: `/host` + ruta) y parsear `payload.data.data`.
   El mismo tool puede responder inline (`storedInFile: false`, payload en `data.data`) en otra
   corrida: manejar **ambos** casos.
2. **curl a la URL pública.** `https://www.instagram.com/p/<shortcode>/` devuelve **HTTP 200**
   tanto para un post vivo como para uno borrado (login wall, ~626 KB de HTML en ambos casos). No
   sirve para verificar borrados. Verificación válida: lista por API (ausente = borrado).
3. **Confundir "sin filas" con "sin publicar".** Antes de concluir que un publish falló, mirar
   `timestamp` de la story y `created_time` del post: la pieza puede estar arriba aunque el registro
   local esté vacío (así nacieron los duplicados del 12-sep).

## Interpretación útil para el reporte

- Un post repetido el mismo día con el mismo copy, minutos aparte, es el duplicado y **la API no lo
  puede borrar** (FB `#10 Application does not have permission`; IG `code 100 subcode 33`): el
  borrado es manual en la app / Business Suite. Pedirlo con los permalinks directos.
- Las **stories de página de FB** no existen en este pipeline: una story del calendario con canales
  `[instagram, facebook]` sale **solo a IG**. Decirlo al reportar, no dejarlo implícito.
- Contar duplicados y ausencias con la lista completa en Python (dedupe/count en código), nunca
  "a ojo" sobre la salida cruda.
