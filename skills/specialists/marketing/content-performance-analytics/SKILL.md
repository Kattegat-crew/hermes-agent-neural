---
name: content-performance-analytics
description: "Analyze campaign reel perf: features + platform insights."
category: devops
metadata:
  author: Ragnar
  version: "1.0.0"
---

# Content Performance Analytics (sistema content-intel)

Sistema para **medir y optimizar** contenido publicado (reels, stories, posts,
carruseles) uniendo **características del asset final** (no clips crudos) con
**métricas de plataforma** reales. Vive en `content-intel/` dentro del repo
`marketing-campaign-generator` (hub de generación de campañas). Unidad de análisis
= el REEL/POST/STORY FINAL publicado.

> Diferencia clave vs creatividad: esto NO decide qué publicar, mide lo que ya
> salió y produce benchmarks/veredictos para el **siguiente** guion. Es la capa que
> convierte el rendimiento en reglas, no en intuición.

## Arquitectura (5 módulos, orquestador en `pipeline.py`)

| Módulo | Rol | Salida |
|---|---|---|
| `registry.py` | **Fuente de la verdad**: cada publicación (brand, campaña, formato, plataforma, media_id, asset, fecha). JSONL `data/posts.jsonl`, idempotente por (platform, media_id). | registro |
| `features.py` | Características del asset final: ffprobe (dur/fps/res), cortes de escena, LUFS/true_peak, energía por banda (scipy), wps/silencios/CTA@ (faster-whisper). | dict por asset |
| `harvest.py` | Métricas de plataforma vía Composio: IG insights y FB post insights, normalizadas. | dict metrics |
| `analyze.py` | Benchmarks por formato×marca + veredictos (ALTO/MEDIO/BAJO vs mediana) + render HTML mobile-first. | dict + html |
| `pipeline.py` | CLI: `register` / `features` / `harvest` / `analyze` / `render`. | — |

### Flujo

```bash
# registrar publicación
python3 pipeline.py register --brand golden --campaign bingo-sep2026 \
    --format reel --platform facebook --media_id <id> --asset <ruta>
# extraer características del asset final (--no-stt si no hay whisper)
python3 pipeline.py features
# cosechar métricas de plataforma
python3 pipeline.py harvest --account-instagram <alias> --account-facebook <alias>
# analizar y renderizar por marca
python3 pipeline.py analyze --brand golden
python3 pipeline.py render --brand golden
```

## Método de trabajo (validado 04/09, datos reales desde 15/08)

No hay datos locales de campañas antiguas — **jalarlos de las plataformas**:

1. **Descubrir media** desde el inicio de campaña:
   - IG: `INSTAGRAM_GET_USER_INFO --account <word_id>` → `data.id` es el IG User ID numérico (no asumir; `'me'` y el `ig_user_id` de memoria fallan con 400 "object does not exist").
   - IG frame list: `INSTAGRAM_GET_IG_USER_MEDIA --account <word_id> -d '{ig_user_id:<num>, fields: id,caption,media_type,permalink,timestamp,media_product_type}'`.
   - FB: `FACEBOOK_GET_PAGE_POSTS --account facebook_... -d '{page_id:<page>, since, fields}'`.
2. **Cosechar insights** por pieza (reels/posts desde el inicio de campaña; stories SOLO en vivo, expiran 24h).
3. **Extraer features** de los reels finales medibles (los que tienen asset).
4. **Ingestar** al registry + correr `analyze`/`render`.

## Pitfalls descubiertos en vivo

- **IG insights el campo es `ig_media_id`, NO `media_id`** (`media_id` → error de validación "Unknown key media_id"). Ambos en el schema de `INSTAGRAM_GET_IG_MEDIA_INSIGHTS` son engañosos: usar `ig_media_id`.
- **FB post insights es `post_id`** y `metrics` solo acepta `post_media_view` desde nov-2025 (impressions/engagements deprecados).
- **IG insights funciona aún <1.000 followers** (Golden 69, Paradise 273): el límite de la doc es para fiabilidad estadística, NO un bloqueo duro de la API. Jala `views`/`reach`/`likes`/`comments`/`saved`/`shares` igual.
- **STT necesita el modelo cacheado**: `/root/marketing-campaign-generator` no resuelve HuggingFace (DNS) si el modelo no está en disco. Modelos `Systran/faster-whisper-base` y `-tiny` ya están en `/root/hermes-agent-legacy-docker/data/.cache/huggingface/hub`. Correr con `env HF_HOME=/root/hermes-agent-legacy-docker/data/.cache/huggingface` + modelo `base` (no `small`, que intenta descargar y falla).
- **faster_whisper vive en el venv de python3.11** `/opt/hermes-venv`, no en el venv del repo (python3.12, sin numpy/scipy/whisper). El stack de análisis del repo usa python3.12 + `numpy/scipy/requests` del **sistema**; whisper aparte.
- **features.py con `NamedTemporaryFile` deja el wav a 0 bytes** (ffmpeg escribe concurrente sobre el archivo ya abierto). Fix: path fijo `os.path.join(tempfile.gettempdir(), f"ci_audio_{pid}_{hash(path)}")` + `-y` y check de size >0.
- **Host vs contenedor**: el repo está en `.250:/root/marketing-campaign-generator` (host), accesible desde el contenedor vía `/host/root/marketing-campaign-generator`. Ejecutar en el host o con `docker run --rm --privileged -v /:/hostfs --pid=host alpine` + `chroot /hostfs /usr/bin/python3.12 <script>`. El dir de build del agente (`/opt/data/...`) = host `/root/hermes-agent-legacy-docker/data/...`.
- **Benchmarks requieren n≥10 por formato** para ser fiables; con n=4 son orientativos. Este es un límite honesto a comunicar, no esconder.

## Almacenamiento / destino

- **Datos crudos**: `content-intel/data/posts.jsonl` (series re-analizables) en el VPS.
- **Análisis legible**: render → dashboard HTML por marca → publicar a la **colección wiki del cliente** (Outline, 1 colección por empresa) en su carpeta de campaña.
- **Separación por cliente de verdad**: crudo en store por marca (`golden`, `lucky`), porque el benchmark se normaliza por follower; no se comparan marcas entre sí.

## Cron automatizado (verificado 04/09/2026)

El ciclo diario está registrado como cron `content-intel-daily` (id `1de9d6aa3d90`, 6:00am, `no_agent`).
El wrapper `content_intel_cron.sh` orquesta 3 pasos:

1. **Harvest** (contenedor): `content_harvest.py` → Composio IG+FB → `harvest_metrics/*.json`
2. **Pipeline host** (docker chroot): `pipeline_wiki.py` → registry + analyze + render + dump `.md`
3. **Wiki publish** (contenedor): `publish_wiki.sh` → curl Outline API

**Por qué 3 pasos separados**: el host .250 NO resuelve `backend.composio.dev` ni `wiki.neuralcrewlabs.com`
(DNS/Cloudflare roto). Composio y Outline API solo funcionan desde el contenedor Hermes. El pipeline
de análisis (python3.12 + repo) solo corre en el host. La solución es el patrón container→host→container.

### Rutas clave del cron
- Build dir (contenedor): `/opt/data/content-intel-build/`
- Build dir (host): `/root/hermes-agent-legacy-docker/data/content-intel-build/`
- Metrics shared: `harvest_metrics/ig_metrics.json` + `fb_metrics.json`
- Analysis output: `analysis_out/{brand}-analisis.md`
- Script en hermes scripts dir: `/opt/data/scripts/content_intel_cron.sh`

## Wiki population batch (patrón verificado 04/09/2026)

Para publicar N documentos a la wiki en lote:
1. Preparar archivos `.md` en un dir local (`/opt/data/wiki-content/`).
2. Script `wiki_publish.py` con lista STRUCTURE (coll_id, title, file, parent).
3. `documents.create` con `collectionId` — NO usar `parentDocumentId` (403 con API key).
4. Rate limit: ~14 creates rápidos antes de 429 → `time.sleep(5)` entre calls.
5. Verificar con `documents.search` (NO `documents.list` que tiene cache/stale).
6. Safe print: titles con emojis causan `UnicodeEncodeError` → wrapper `_builtins.print()`.

## Repo (dónde vive el código)

Dentro de `marketing-campaign-generator` (el hub de campaña, renombrado de `video-ai-generator` — ver skill `repo-rename` para el rename seguro).

## Referencias

- `references/content-intel-run-20260904.md` — la primera corrida real: media descubiertos, métricas cosechadas de IG/FB, features de los reels Goldie/Lucky, y el análisis de la campaña desde 15/08 (Golden) / 21/08 (Lucky).
