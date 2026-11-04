---
name: twitter-telegram-ingestion
description: "Use when an X link lands in the Links de X group."
tags: [x, twitter, telegram, ingesta, ingestion, outline, wiki, brain]
---

# Twitter/Telegram Ingestion Workflow

## Trigger
An X/Twitter status URL (`x.com/i/status/...` or `twitter.com/...`) is posted in the Telegram group **"Links de X"**. Group standing context: "Procesa cualquier enlace de X/Twitter usando la skill twitter-telegram-ingestion. Extrae obligatoriamente: relevancia, resumen, key takeaway, stack, acción. Guarda en Notion DB + Brain Wiki y responde con el reporte estandarizado."

## Required output (reply in the group)
1. **Relevancia** — 1–5 estrellas (⭐)
2. **Resumen** — 2–3 líneas conciso
3. **Key Takeaway / Problema que soluciona**
4. **Herramientas o Stack mencionados**
5. **Acción o impacto sugerido para NeuralCrew Labs**
Close with "Guardado en Brain Wiki + Notion DB ✅".

## Steps

### 1. Extract the tweet
Use the `x-tweet-scrape` skill for extraction techniques (fixupx.com metadata extraction is primary, no auth). Fallbacks: Nitter script (`/opt/data/scripts/tweet-scraper.py`), FXTwitter API.

### 2. Enrich if truncated or link-only
- fixupx `og:description` truncates at ~276 chars. If the tweet has bullets/links or ends abruptly, resolve the t.co links (NoRedirect urllib pattern) and fetch the real destination.
- GitHub destination → `https://api.github.com/repos/{owner}/{repo}` (stars, description, language) + `https://raw.githubusercontent.com/{owner}/{repo}/main/README.md` for concrete specs (resolutions, durations, formats). Feed specs into Resumen/Stack/Acción.
- X Article (`x.com/i/article/`) → **`api.fxtwitter.com/<user>/status/<tweet_id>` devuelve `tweet.article` COMPLETO** (title + content.blocks[] Draft.js) sin login (verificado 28/08). Si FXTwitter no trae el article, fallback a búsqueda externa (DuckDuckGo) por el título (ver skill x-tweet-scrape).

## 3. Guardar (NUEVO pipeline — ya NO usamos Notion)

NOTION ABANDONADO. Todo va a **wiki (Outline) + brain/ingestas**. Usar el script central:

```bash
python3 /opt/data/scripts/ingesta_externa.py \
  --tipo x \
  --url "<url>" \
  --autor "@autor" \
  --tema "<tema corto>" \
  --resumen "<2-4 lineas>" \
  --importancia 4 \
  --tags "tag1,tag2,tag3" \
  --aplicable "Sí/No + dónde" \
  --nota "<nota opcional>"
```

El script hace 4 cosas: (1) inserta la fila en la tabla `Tuits analizados` de la wiki (doc 59d62985...), (2) crea `brain/ingestas/tuits/YYYY-MM-DD-x-<autor>-<tema>.md` con frontmatter estructurado, (3) regenera `brain/ingestas/index.md` (índice acumulativo), (4) [opcional] Engram.

Esquema de columnas wiki (uniforme para las 3 tablas): `Fecha | Autor | URL | Tema | Importancia | Resumen | Tags | ¿Aplicable? | Nota`.

**PITFALL:** la API de la wiki va detrás de Cloudflare → 403 error 1010 si el User-Agent es Python. Siempre enviar `User-Agent: Mozilla/5.0 ... Chrome/126.0`. El script ya lo incorpora.

**No crear fila duplicada** si ya existe (dedup por URL); verificar antes de insertar o dejar que el flujo la detecte.

## 3b. ANTES (obsoleto — NO usar)

El flujo viejo escribía a la DB de Notion "Links de X". Ya NO se hace. Si aparece un ID de Notion en un contexto de grupo, es stale — ignorarlo y usar `ingesta_externa.py`.

### Formato de respuesta al grupo

Relevancia ⭐ + Resumen + Key Takeaway + Stack + Acción + "Guardado en wiki + brain/ingestas ✅". Español, sin ruido de sistema.

## Pitfalls
- **Wrong Notion DB ID** — the group instructions embed a stale ID. Always verify via search/schema before writing; the working Links de X DB is `3ae853a7-3369-81f4-9581-fcc41b5c5ea4`.
- **fixupx truncation** — never rely on OG description alone for bullet/tool tweets; enrich from the t.co destination.
- **FXTwitter DNS failure** (`No address associated with hostname`) — expected on this VPS; go straight to fixupx.
- **Notion token** lives in `/opt/data/.env` as `NOTION_API_KEY` (not exported to shell env — parse the file manually, k=v, ignore #).
- **Notion DB page content**: paragraphs limited to 2000 chars — truncate rich_text before sending.

## Related
- `x-tweet-scrape` (user-owned) — extraction techniques: fixupx, Nitter, t.co resolution, X Article handling.
- `notion-integration` — general Notion API usage (its DB ID table is stale for Links de X; use the ID above).