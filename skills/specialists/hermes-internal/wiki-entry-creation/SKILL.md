---
name: wiki-entry-creation
description: "Use when documenting docs into the Brain Wiki."
tags: [wiki, brain, documentacion, docusaurus, scraping, indice, notion]
---

# Wiki Entry Creation

## When to Use
- User shares a docs URL and asks to document it in the Brain Wiki
- Browser (Camfox) is not available or too slow
- Target site is Docusaurus-style (has `<main>` or `<article>` tags with content)
- Need to capture official docs, architecture, or tool configurations

## Workflow

### 1. Fetch with urllib + SSL bypass
```python
import urllib.request, ssl, re

url = "https://example.com/docs/page"
context = ssl._create_unverified_context()
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})

with urllib.request.urlopen(req, context=context, timeout=15) as response:
    html = response.read().decode('utf-8', errors='replace')
```

### 2. Extract content from `<main>` or `<article>`
Docusaurus sites render content in `<main>` tags — NOT in JSON script tags.
```python
main_match = re.search(r'<main[^>]*>(.*?)</main>', html, re.DOTALL)
if main_match:
    main = main_match.group(1)
else:
    main_match = re.search(r'<article[^>]*>(.*?)</article>', html, re.DOTALL)
    main = main_match.group(1) if main_match else html
```

### 3. Clean HTML to text
```python
main = re.sub(r'<script[^>]*>.*?</script>', '', main, flags=re.DOTALL)
main = re.sub(r'<style[^>]*>.*?</style>', '', main, flags=re.DOTALL)
text = re.sub(r'<[^>]+>', '\n', main)
lines = [line.strip() for line in text.split('\n')]
lines = [l for l in lines if l]
text = '\n'.join(lines)
```

### 4. Write SKILL.md or wiki entry
Use consistent frontmatter:
```yaml
---
title: "Page Title"
type: wiki
tags: [hermes, category, subcategory]
created: YYYY-MM-DD
updated: YYYY-MM-DD
source: official-docs
url: https://...
---
```

### 5. Update index.md
Add `[[entity_name]]` reference under the appropriate section in `/opt/data/brain/index.md`.

### 6. Ask user for next page
Don't auto-sync to Notion — wait for user direction. The user wants to review entries first.

## Critical Pitfalls

- **Camfox not running** → `Cannot connect to Camofox at http://localhost:9377` — browser tools will fail
- **Docusaurus CSR** → Content IS in `<main>` or `<article>` tags, NOT in JSON script tags. The `urllib` + regex approach works reliably.
- **Large pages** → Some pages are 20KB+ of text. Write directly to file, don't try to echo to terminal.
- **Notion sync** → Don't auto-sync to Notion. Wait for user to review entries first.
- **wiki-to-notion-sync.py** is the canonical sync method — use it when user asks to sync.
- **Progressive disclosure** → Write one entry at a time, update index, then ask for the next URL.

## Antes de escribir (ruteo por mapa)

El brain tiene estructura definida (entities/, concepts/, tasks/, raw/). Antes de guardar una entrada, consulta la skill `mapa-de-carpetas` y su registro `/opt/data/brain/folder-maps/` para elegir la carpeta correcta (entidad → entities/, concepto → concepts/, raw → raw/). No crees carpetas nuevas sin autorización.

## File Locations
- Wiki entries: `/opt/data/brain/entities/`
- Index: `/opt/data/brain/index.md`
- Sync script: `/opt/data/scripts/wiki-to-notion-sync.py`
- Config: `/opt/data/config.yaml`

## Example: Documenting System Architecture

1. Read config.yaml for current settings
2. Create entry with known configuration + documented defaults
3. Include "Próximos temas" section for unfinished topics
4. Update index with new entry
5. Sync to Notion
6. Report progress to user

## Notes
- Create entries section by section, not all at once
- Include "Próximos temas" to track what's left to cover
- Use consistent tag format: `[hermes, category, subcategory]`
- Keep entries under ~4000 chars for manageable Notion pages
