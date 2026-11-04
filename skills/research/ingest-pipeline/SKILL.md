---
name: ingest-pipeline
version: 1.0.0
author: Ragnar
license: MIT
description: "Use when ingesting an X/TikTok/GitHub link into brain."
tags: [ingesta, brain, wiki, outline, fxtwitter, tiktok, graphify]
related_skills: [knowledge-consolidation, brain-knowledge-base, outline-wiki-ops, twitter-telegram-ingestion, tiktok-ingestion, graphify]
---

# External Source Ingest Pipeline

End-to-end architecture for ingesting external sources (X/Twitter, TikTok, GitHub repos) into the NeuralCrew knowledge system: **wiki tables** (Outline) + **brain/ingestas/** (structured markdown) + **knowledge graph** (graphify).

## Architecture Overview

```
Link arrives (Telegram group or direct message)
  → ingesta_externa.py (central script)
    → Wiki: row in correct table (Tuits/TikToks/Repos)
    → Brain: .md with frontmatter in brain/ingestas/<tipo>/
    → Brain: index.md regenerated
    → (optional) Engram MCP observation

Nightly cron (3:30 AM):
  → brain_graph_update_wrapper.sh
    → graphify extract (qwen3.6, concurrency 2)
    → merge with existing graph → grafo acumulativo
```

## Wiki Tables (Outline)

Three tables in NeuralCrew Interno collection:

| Table | Doc ID | Columns |
|-------|--------|--------|
| Tuits analizados | `59d62985-a7e5-4634-9efe-669feac23802` | Fecha · Autor · URL · Tema · Importancia · Resumen · Tags · ¿Aplicable? · Nota |
| TikToks | `0a3388c7-ec75-46ce-832d-17950f737740` | Fecha · URL/ID · Creador · Tema · Importancia · Resumen · Tags · Aplicable en |
| Repos | `22c8fed7-62a4-4a89-bbe1-ef88ac42ea89` | Repo · URL/GitHub · Qué es · Importancia · Tags · Estado |

**Schema is uniform** across all tables: each row has info, resumen, importancia (⭐), tags, and an applicability field.

## Brain /ingestas/

Structured markdown files with frontmatter:

```yaml
---
fecha: 2026-08-13
fuente: X/Twitter
url: https://x.com/GitTrend0x/status/...
autor: @GitTrend0x
tema: 5 plugins esenciales de Hermes Agent
importancia: ⭐⭐⭐⭐
tags: hermes agent, plugins, agentes, automación
---
```

Directory structure: `brain/ingestas/tuits/`, `brain/ingestas/repos/`, `brain/ingestas/tiktoks/`, `brain/ingestas/posts/` (general web/docs links: official docs, blogs, news — no script, manual flow), plus `brain/ingestas/index.md` (auto-regenerated accumulator table).

## Central Script

`/opt/data/scripts/ingesta_externa.py` — CLI tool:

```bash
python3 scripts/ingesta_externa.py \
  --tipo x|tiktok|repo \
  --url "https://..." \
  --autor "@user" \
  --tema "Description" \
  --resumen "1-2 sentence summary" \
  --importancia 4 \
  --tags "tag1,tag2" \
  --aplicable "SI" \
  --nota "optional note"
```

Writes to: wiki table (row insert) + brain/ingestas/ (frontmatter .md) + index.md (regenerated).

## Workflow: General Web/Docs Link (no script)

For links that are NOT x/tiktok/repo (docs pages, blogs, news) `ingesta_externa.py` does not apply (its `--tipo` only accepts x|tiktok|repo). Manual flow (verified 2026-09-23 with Hermes user-stories docs page):

1. `web_extract(url, char_limit=15000)` — if head+tail truncated, page the full saved file with `read_file` (path + offset come in the extract footer); do not summarize from the truncated window alone.
2. Write `brain/ingestas/posts/YYYY-MM-DD-<slug>.md` with the standard frontmatter (fecha/fuente/url/autor/relevancia/tema).
3. Add a row to `brain/ingestas/index.md` (accumulator table).
4. Insert a Notion row in the canonical Links DB — recipe in `references/notion-links-db.md` (dedup by URL query BEFORE insert).
5. Report in chat using the canonical template in `references/reporte-ingesta-plantilla.md`.

## Techniques

See `references/fxtwitter-api.md` for X/Twitter extraction.
See `references/graphify-brain-update.md` for the graph update pattern.
See `references/outline-ua-pitfall.md` for the Cloudflare UA requirement.
See `references/notion-links-db.md` for the Notion Links DB insert recipe (key recovery, dedup, payload).
See `references/reporte-ingesta-plantilla.md` for the canonical chat report template the Admin expects.

## Pitfalls

- **Outline API behind Cloudflare**: Python User-Agent → 403 error 1010. MUST use `User-Agent: Mozilla/5.0 ... Chrome/126.0` header on every request.
- **Tuits `x.com/i/status/<id>`**: these are articles or anonymous-format tuits. Use FXTwitter to resolve the real author. Some resolve to full articles with `tweet.article`.
- **Repos in brain/raw/ with Notion URLs**: old ingestion stored `notion:` URLs in frontmatter while real GitHub URL was in `source: github://owner/repo`. Always prefer `source:` over `url:` when the URL points to app.notion.com.
- **Dedup by tweet ID not URL**: the same tweet can appear with different URL formats (with/without `www.`, with query params). Extract the numeric status ID and dedup on that.
- **Nightly graph update**: NaN-Builders limits 5 simultaneous requests per API key. The gateway shares this key. Use concurrency ≤2 for graphify extract. qwen3.6 produces better JSON than deepseek-v4-flash for graphify's semantic extraction.

## Workflow: Processing a New Link

1. **Identify type**: X/Twitter → `--tipo x`, TikTok/IG/FB reel → `--tipo tiktok`, GitHub repo → `--tipo repo`
2. **Extract metadata**:
   - X: `web_extract` on `https://api.fxtwitter.com/USER/status/ID` (or `/i/status/ID`)
   - GitHub: `https://api.github.com/repos/OWNER/REPO` for description, stars, language, topics
   - TikTok: `web_extract` on the URL (may need redirect resolution)
3. **Run `ingesta_externa.py`** with extracted fields
4. **Verify**: check wiki table has new row, brain/ingestas/<tipo>/ has new .md

## Workflow: Batch Populate from Historical Data

1. Query `state.db` for messages in ingestion groups:
   ```sql
   SELECT content FROM messages m JOIN sessions s ON m.session_id=s.id
   WHERE s.source='telegram' AND s.chat_id IN ('-1003820724234','-1003869738224')
   AND m.role='user' AND m.content IS NOT NULL
   ```
2. Regex extract URLs (X: `x.com/USER/status/ID`, GitHub: `github.com/OWNER/REPO`, TikTok: `tiktok.com/...`)
3. Dedup by tweet ID (numeric) against `brain/raw/` and `brain/ingestas/`
4. Extract metadata for new items (FXTwitter for X, GitHub API for repos)
5. Generate `rows_x.json` / `rows_r.json` / `rows_t.json` (uniform schema)
6. Write tables to wiki via `documents.update` API
7. Generate .md files in `brain/ingestas/` + regenerate `index.md`

## Cron: Auto-Update Knowledge Graph

`brain-graph-update-noche` (id `5a1925b95575`): every night at 3:30 AM.
- Script: `brain_graph_update_wrapper.sh`
- Pattern: backup current graph.json → graphify extract → merge backup + new → write merged
- Model: qwen3.6 (better JSON than deepseek-v4-flash)
- Concurrency: 2 (NaN limit is 5 shared with gateway)
- Output: `graphify-out/graph.json` (cumulative, never loses prior nodes)

## Cron vs Dispatched

- **Cron is NOT needed for link ingestion** — links are processed in real-time when the user sends them. The cron's role is graph maintenance.
- **No cron for daily ingestion** — the agent processes each link as it arrives.
- **Cron IS for graph update** — graphify extract + merge runs nightly to index new ingestas.

## User Preferences

- User wants tables **uniform**: same schema columns across Tuits/TikToks/Repos.
- User wants **all fields populated**: tags, descriptions, importance, not placeholders.
- User prefers **brain/ingestas/ over brain/raw/** — structured > unstructured.
- User wants graph to update automatically so they can search semantically without relying on agent memory.
- Every link from the groups must be captured — nothing left behind.