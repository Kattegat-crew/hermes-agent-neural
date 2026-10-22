---
name: marketing-calendar-publishing
description: "Use when publishing bingo-sep2026 calendar pieces."
tags: [marketing, calendario, calendar, publicacion, composio, instagram, facebook, crons]
version: 1.0.0
author: Ragnar
---

# Marketing Calendar Publishing Flow (Bingo Sep-2026)

## Comandos rápidos

> ⚠️ El repo vive en `/root/marketing-campaign-generator` (host) = `/host/root/marketing-campaign-generator` (gateway/crons).

| Acción | Comando |
|---|---|
| **Aprobar por chat ("Dale <ID>")** | `cd /root/marketing-campaign-generator/planning/calendario-sep2026 && python3 approve_ids.py <ID> [<ID> ...]` (o `/host/root/...` en el contenedor; marca aprobado + regenera XLSX + lo sube a AMBOS Drive + commit/push; `--dry-run` para validar) |
| Sync XLSX→JSONL manual | `cd /root/marketing-campaign-generator/planning/calendario-sep2026 && python3 sync_from_drive.py` |
| Ver piezas debidas ahora | `python3 cron_publish_due.py` (sin args → lista silenciosa o publica) |
| Publicar manualmente un ID | `python3 publish.py --id golden-sep09-story-d1` |
| Dry-run de publicación | `python3 publish.py --id <ID> --dry-run` |
| Reparar drift de estado (fila publicada que quedó en `aprobado`) | `cd .../planning/calendario-sep2026 && python3 repair_drift_publicado.py [--dry-run]` (idempotente: devuelve a `publicado` toda fila con `publicado_en`/`media_ids`, regenera XLSX, sube a ambos Drive, commit+push) |
| Paquete del día (test local) | `bash /root/hermes-agent-legacy-docker/data/scripts/calendario_daily_package.sh` |
| Harvest métricas (test local) | `bash /root/hermes-agent-legacy-docker/data/scripts/calendario_harvest.sh` |

## Aprobación (regla dura: nada se publica sin 'Aprobado')

Dos vías:
1. **Chat**: el usuario dice "Dale <ID>" → Ragnar edita JSONL, pone `estado: aprobado`, commitea, el cron horario lo publica en su slot.
2. **XLSX en Drive**: el humano edita la celda `Estado` a `Aprobado` → el sync la recoge en el siguiente tick horario.

## Máquina de estados

```
listo_para_aprobacion  →  (aprobado)  →  publicado
    a_producir  →  listo_para_aprobacion (cuando se produce la pieza)
```

## Crons Hermes

| Cron | Herario | delivers |
|---|---|---|
| `calendario-paquete-diario` | 7:30 AM daily | Discord `discord:1542126606900920340` (#bragi-content, canal del webhook "Crons de posts") |
| `calendario-publicacion-horaria` | every hour | Discord `discord:1542126606900920340` — **modo script puro (`no_agent`) desde 12-sep-2026**: entrega el stdout de `cron_publish_due.sh`; sin piezas debidas = stdout vacío = **nada se publica al canal** (silencio, no spam) |
| `calendario-metricas-diario` | 6:00 AM daily | local (sin spam) |
| `calendario-metricas-tarde` | 6:00 PM daily | Discord `discord:1542126606900920340` |
| `calendario-informe-campana` | 8:00 AM daily, autogate solo 1er lunes del mes | Discord `discord:1542126606900920340` (no_agent) |

**Por qué la publicación es `no_agent`**: el 12-sep-2026, con el job en modo agente (terminal incluido), el agente improvisó y publicó mientras otra sesión hacía lo mismo → **post duplicado** en IG y FB. En modo script la publicación es determinista y no gasta tokens de agente. El paquete 7:30 sigue como agente (formato del digest). Comando: `hermes cron edit <job_id> --no-agent` (requiere `--script` ya configurado). Verificado: tick 13:27 del 12-sep corrió `ok` y no posteó nada al canal.

## Datos críticos

| Concepto | Valor |
|---|---|
| IG account Golden | `instagram_demal-molala` → `goldengame_casinos` (40006158832316994) |
| IG account Lucky | `instagram_scot-linked` → `thegrandparadiseclubcasino` (27571270162548342) |
| FB Page (ambas marcas) | `facebook_uncite-skyish` → Golden (820898971112738), Lucky (765896786617957) |
| Drive XLSX Golden ID | `1K1EFCAQiR8Z-hch_0Hr1IY4Y9Fjd8n6e` |
| Drive XLSX Lucky ID | `1O1KX15rSq4CY3xuPlox5y2FosfTRC_Gn` |
| Assets PROD | `/opt/reels/assets/sep2026/` → `https://reels.neuralcrewlabs.com/assets/sep2026/` (sin SSO) |
| Bio Golden | `goldengame.com.co` |
| Bio Lucky | `paradiseclubcasinos.com.co` |

## Footer automático (reels/posts/carruseles)

Se añade al final del caption (después de hashtags):
- IG: `🔗 Más info: link en nuestra bio\n🌐 <url_marca>`
- FB: `🔗 Más info: link en nuestra página\n🌐 <url_marca>`
- Stories: SIN footer (IG no lo permite por API)
- Si el copy ya contiene 'link en' o la URL, no se duplica.

## Pitfalls documentados

1. **`notify` parameter** — Composio FB tools: `notify` debe ser bool/list, nunca string "True". Siempre `notify=False`.
2. **`media_id` → `ig_media_id`** (Jul-2026): el parámetro de `INSTAGRAM_GET_IG_MEDIA` y `INSTAGRAM_GET_IG_MEDIA_INSIGHTS` cambió. Usar `ig_media_id`.
3. **FB video >100MB** via local upload (`/path/to/file.mp4`) da HTTP 413. Solución: hostear en portal y usar `file_url`.
4. **FB stories**: no hay herramienta Composio para publicar stories; solo IG.
5. **IG stories link stickers**: Meta API NO soporta stickers interactivos en stories (confirmado 2026-06). La única vía manual es Meta Business Suite (desktop).
6. **Scopes string vs list** en credenciales Drive: si `scopes` viene como string, parsearlo a lista antes de `Credentials(..., scopes=...)`.
7. **Entorno dual host/gateway (VERIFICAR SIEMPRE CON NSENTER, no setpriv):** los crons corren en el contenedor del gateway (uid 10000, HOME=/opt/data, python 3.13 del contenedor, repo visible solo vía /opt/data/repos, sin composio propio). `setpriv --reuid=10000` en MI namespace da falsos verdes. Prueba real: `nsenter -t $(pgrep -f 'hermes gateway run|head -1) -m -n -S 10000 -G 10000 -u -- bash /opt/data/scripts/calendario_publish_due.sh`. Ver detalles en la skill `cron-runtime-verification`.
8. **Composio dentro del gateway:** el shim `/opt/data/.local/bin/composio` puentea por SSH al CLI real del host (`root@10.0.2.1`); el binario bun nativo hace core dump dentro del contenedor.
9. **Path.exists() sobre /root del contenedor LANZA PermissionError** (no devuelve False) — usar helper try/except `_first_existing()` para rutas bilingües.
10. **Drift `publicado` → `aprobado` (detectado y arreglado 11-sep-2026):** `cron_publish_due.py` marcaba `publicado` pero solo regeneraba el XLSX **local**; el `sync_from_drive.py` del tick siguiente aplicaba la columna `Estado` de Drive (desactualizada en "Aprobado") y devolvía la fila a `aprobado`, conservando `publicado_en` + `media_ids`. Efecto: la tabla mostraba "Aprobado" para piezas ya publicadas y `content-intel/campaign_report.py` (cuenta `estado=='publicado'`) subinformaba el cierre de mes. Fix aplicado (3 piezas):
    - `drive_xlsx.py` (nuevo): helper compartido `upload_review_xlsx()` → sube el XLSX de revisión a **AMBAS** copias de Drive. Lo usan `approve_ids.py` y `cron_publish_due.py` (tras publicar). Regla: **toda** mutación de estado sube el XLSX a Drive, si no la tabla miente.
    - `sync_from_drive.py`: transición **monotónica** del campo `Estado` (RANK a_producir<listo_para_aprobacion<aprobado<publicado). Nunca aplica un valor que retroceda el estado; registra la divergencia en `divergencias_estado.json`. Un retroceso deliberado se hace por chat.
    - `repair_drift_publicado.py` (nuevo): reparación idempotente del drift histórico.
    Prueba end-to-end del guard: subir a Drive un XLSX atrasado y correr `sync_from_drive.py` → 0 cambios aplicados + N divergencias ignoradas (antes degradaba).
    Lección: los campos editables por el humano (Estado/Copy/Hashtags/Portada/Nota) son **espejos**; cualquier escritura automática del pipeline debe re-subir el espejo o el sync la pisará.

## Pitfalls del carrusel y del registro (12-sep-2026, verificados en vivo)

1. **Carrusel IG exige JPEG**: los assets del carrusel eran PNG (~2,2 MB, 1080×1080) y `INSTAGRAM_CREATE_CAROUSEL_CONTAINER` devolvía **400 "Invalid parameter in carousel request"** (mensaje engañoso: habla de child containers). Meta pide JPEG en `image_url` → `publish.py::_jpegify_images()` convierte a JPEG (fondo blanco) antes de subir al portal. Los .jpg ya no se tocan.
2. **No pasar `share_to_feed` al contenedor padre del carrusel**: con ese flag el 400 reaparece. `publish.py::_carousel_container()` lo omite y, si el tool falla, usa la **vía 2**: hijos con `INSTAGRAM_POST_IG_USER_MEDIA` (`is_carousel_item=True`) → esperar `FINISHED` con `INSTAGRAM_GET_POST_STATUS` → padre con `media_type=CAROUSEL` + `children`. Los hijos son de **un solo uso**: reutilizar ids ya consumidos da 400.
3. **FB devuelve `post_id`, no `id`**: `FACEBOOK_CREATE_MULTI_PHOTO_POST` responde `data.post_id`; si solo se lee `data.id`, un post **ya publicado** se reporta como error y la fila queda sin registrar (así nació el duplicado de golden del 12-sep). Parsear ambos.
4. **`registry.register(format=...)` no acepta `carrusel`**: `FORMATS = {reel, story, post, carousel, video, image}`. `cron_publish_due` pasaba `r['type']` = `carrusel` → `ValueError` **después** de publicar → la fila quedaba en `aprobado` sin `media_ids` y el tick siguiente podía republicar. Fix: `FORMAT_ALIASES = {'carrusel': 'carousel'}` en `content-intel/registry.py`.
5. **Antes de reintentar una publicación fallida, comprobar si el post existe**: el registro local puede estar vacío aunque el post esté arriba. `INSTAGRAM_GET_IG_USER_MEDIA` / `FACEBOOK_GET_PAGE_POSTS` con los ids del día. **Nada de lo publicado se puede borrar por API** (FB `#10 Application does not have permission`, IG `code 100 subcode 33`) → el borrado de duplicados es manual en la app / Business Suite.
6. **Credencial de Drive**: `drive_xlsx.py` y `sync_from_drive.py` usaban `os.environ` **sin `import os`** (NameError) y `_first_existing(['', '/root/...', '/opt/data/...'])` devolvía `Path('.')` (la cadena vacía "existe") → toda llamada a Drive fallaba. Fix 12-sep: `import os` + `_first_existing` ignora cadenas vacías. Además `fetch_xlsx` usa un temporal con PID (dos runtimes: ticker root del Desktop y gateway uid 10000 chocaban por el mismo `/tmp/xlsx_drive_master_*.xlsx`).
7. **Link del carrusel en el paquete diario**: `cron_daily_package.py` enlazaba `slides[0].drive_url` (una sola foto). Ahora resuelve el **padre común** de los slides y enlaza la carpeta (`https://drive.google.com/drive/folders/<id>`); si los padres difieren o la API falla, lista los links individuales.
8. **Reintento de una sola vía**: `publish.py --platforms instagram` (o `facebook`) permite reponer el lado que falló sin duplicar el otro.

9. **Insights de Facebook exigen el id con prefijo de página**: `FACEBOOK_GET_POST_INSIGHTS` necesita `<page_id>_<post_id>` (golden `820898971112738`, lucky `765896786617957`). Con el id "pelado" Meta responde **HTTP 400 · code 200 · subcode 1504029 "Permissions error"** — subcode engañoso: es error de resolución del objeto, no de scopes, y la pieza queda con 0 vistas en dashboards e informe (caso real `golden-sep10-post-pacho`, aislado y arreglado el 12-sep-2026, commit `63b0b31`). Blindaje de 3 capas implementado: `publish.py` prefija el `post_id` que devuelve FB antes de registrarlo, `registry.normalize_media_id()` normaliza en `register()` (forma canónica al escribir) y `harvest.harvest_one(brand=...)` repara ids heredados antes de pedir insights. `cron_harvest` pasa `brand` (la cuenta de FB es la misma para ambas marcas, así que el brand es la única fuente de la página).

## Pitfalls del publicador, sync portal y assets (19-oct-2026, verificados en vivo)

1. **Doble ticker del publicador = duplicado garantizado.** El 19-oct un backstop en el HOST (`/etc/cron.d/publish-backstop`, cada 15 min) corría el publicador además del cron del gateway. El `flock` NO protege si cada runtime resuelve el lock en SU `/tmp` (contenedor ≠ host): el lock debe vivir en una ruta compartida visible por ambos con el MISMO uid → `LOCK_PATH = /opt/hermes-agent-data/cache/publish-calendario.lock` (fijo, 0600, uid hermes=10000 en ambas vistas). `gettempdir()+euid` es una trampa. Y regla dura: **nunca añadir crons backstop del publicador en el host** — el cron horario del gateway ya es el único ticker.
2. **Logs de `sync_all.sh` nunca en `/tmp`.** El cron del host corría sync_all como root y dejaba `/tmp/sync_*.log` `root:root`; el siguiente tick del contenedor moría con `Permission denied` que se enmascaraba como `libro del portal FALLO` (el script reporta el síntoma, no la causa). Fix: logs en `<repo>/.sync_logs/` (dentro del repo, chown final incluido). Además: al verificar exit codes, **no pipear** — `cmd | tail` devuelve el exit de `tail`, no del script (verificación viciada clásica).
3. **`sync_all` recibe CARPETA, no alias de calendario.** `r['campaign']` en calendario.jsonl es el alias `alias.calendar_campaign` (p.ej. `sorteo-terror-oct2026`), pero `drive_sync` espera la carpeta física `assets/campanas/<slug>` (p.ej. `2026-10-halloween`). Pasar el alias directo = `"no existe assets/campanas/..."` y sync rojo en cada tick. Fix en `cron_publish_due.py`: resolver alias → carpeta escaneando `planning/*/campaign.yaml` (`alias.calendar_campaign == campaign` → nombre del directorio; fallback: el alias mismo).
4. **Cover de reel IG: el seek del frame no puede salirse de la duración.** El fallback de cover extrae un frame a un segundo fijo (p.ej. s32); si el reel dura 16.6 s → 0 frames → el contenedor IG aborta mientras FB sí publica → fila PARCIAL. Vía de reparación: generar cover JPEG del propio reel, subirla a Drive (credencial `jonathan-drive.json`), inyectar `cover_drive_id` (+`cover_name`) en la fila y republicar solo IG con `republish_ig.py` (republica piezas PARCIAL, no toca el lado FB ya vivo).
5. **ID de Drive truncado en la fila = 404 engañoso.** Un asset_id al que le falta el ÚLTIMO carácter da `404 "File not found"` de Drive aunque el archivo exista y el publicador esté sano. Diagnóstico: comparar el sufijo del ID de la fila contra el ID real del archivo en la carpeta de assets; corregir la fila y republicar. El error parece de Drive/pipeline, es de dato.
6. **El wrapper filtrado oculta tracebacks.** `calendario_publish_due_filtered.sh` solo pasa líneas `^(ERROR|Traceback|fatal|⚠)` — los frames indentados del traceback se pierden. Para diagnosticar, correr `cron_publish_due.py` (o el sh sin filtro) en vivo y capturar stderr completo.

## Plantilla mensual (regla NeuralCrew desde sep-2026)

Este calendario es el estándar para campañas mensuales de ambas marcas. Ver skill `monthly-campaign-calendar-playbook` para replicarlo en octubre+: inventario Drive → build_calendario → XLSX a Drive → crons gemelos (paquete/publicación/métricas) → harvest → cierre de mes.