---
name: github-repo-ingestion
description: >-
  Use when ingesting a GitHub repo into Brain/Outline wiki. Ingest GitHub repos into Brain Wiki and the Outline wiki. hermes: tags: [github, repos, ingestion, wiki, outline, brain-wiki, research] commands: [curl, python3]
tags: [github, repos, ingestion, wiki, outline, brain-wiki, research]
version: 1.1.0
author: Ragnar (NeuralCrew Labs)
metadata:
prerequisites: {}
---

# GitHub Repo Ingestion

## Trigger

Any GitHub repository URL (`github.com/<owner>/<repo>`) posted in a monitored
channel, or when the user asks to analyze/save a GitHub repo.

## Destino de guardado (ACTUALIZADO)

**NO se guarda en Notion** — la integración Notion se retiró (03/09/2026).
El destino canónico es la **wiki** (Outline, `wiki.neuralcrewlabs.com`) + el
**Brain Wiki** en disco.

- **Ficha de repos en la wiki:** documento `Repos` (colección `NeuralCrew
  Interno`, id `22c8fed7-62a4-4a89-bbe1-ef88ac42ea89`), una tabla markdown con
  columnas: `Repo | URL/GitHub | Qué es | Importancia | Tags | Estado`. Se
  AÑADE una fila por repo (`documents.update` conservando el texto previo).
- **Brain Wiki en disco:** `/opt/data/brain/raw/<repo>.md` con frontmatter y
  secciones.
- La prueba de que el repo ya fue analizado es la fila en la ficha `Repos` +
  el `.md` en `brain/raw/`. Usar `outline-wiki-ops` para la API de Outline.

## Workflow

### 1. Extract Metadata (GitHub API)

```sh
curl -sL "https://api.github.com/repos/<owner>/<repo>" | python3 -c "
import sys,json; d=json.load(sys.stdin);
print(json.dumps({
  k:d.get(k) for k in
  ['name','full_name','description','html_url','language',
   'stargazers_count','forks_count','license','topics',
   'created_at','updated_at']
}, indent=2)
)"
```

Also check default branch:
```sh
curl -sL "https://api.github.com/repos/<owner>/<repo>" | python3 -c "import sys,json; print(json.dumps({'default_branch': json.load(sys.stdin).get('default_branch')}))"
```

### 2. Read Primary Docs

```sh
curl -sL "https://raw.githubusercontent.com/<owner>/<repo>/<branch>/README.md" | head -300
curl -sL "https://raw.githubusercontent.com/<owner>/<repo>/<branch>/AGENTS.md" | head -200
curl -sL "https://api.github.com/repos/<owner>/<repo>/contents/docs" | python3 -m json.tool
```

Para repos de skills/contenido de Hermes, leer también los archivos reales
(`SKILL.md`, `references/*.md`, `scripts/*.py`) en vez de solo el README.

### 3. Analyze Relevance

| Pregunta | Criterio |
|----------|----------|
| ¿Qué soluciona? | Problema concreto que aborda |
| Casos de uso | Escenarios donde ya se usa o aplica |
| Potencial NeuralCrew ⭐ | 1-5 según qué necesidad resuelve |
| Riesgos | Madurez, breaking changes, stack, licencia |

### 4. Save to Brain Wiki

Write to `/opt/data/brain/raw/<repo>.md` with:
- YAML frontmatter: title, url, tags, created, updated, rating
- Sections: Metadata, Resumen, Arquitectura (table), Capacidades, Potencial NeuralCrew, Riesgos, Tags

## 5. Save to Outline wiki (ficha Repos)

La ficha `Repos` es una tabla markdown; añadir UNA fila. Usar la API de
Outline (ver skill `outline-wiki-ops`):

```python
import requests, os
key = open('/opt/data/.outline-wiki-key').read().strip()
base = 'https://wiki.neuralcrewlabs.com'
h = {'Authorization':f'Bearer {key}','Host':'wiki.neuralcrewlabs.com',
     'X-Forwarded-Proto':'https','Content-Type':'application/json'}
DOC_ID = '22c8fed7-62a4-4a89-bbe1-ef88ac42ea89'   # ficha "Repos"

def post(m, b):
    r = requests.post(f'{base}/api/{m}', json=b, headers=h, timeout=30)
    return r.status_code, r.json()

s, d = post('documents.info', {'id': DOC_ID})
txt = d['data']['text']
row = ("| <owner>/<repo> | https://github.com/<owner>/<repo> | "
       "<qué es, 1 línea> | ⭐⭐⭐⭐ | <tags> | Analizado ⭐<stars> |\n")
new_text = txt.rstrip() + '\n' + row
s2, d2 = post('documents.update', {'id': DOC_ID, 'text': new_text, 'publish': True})
# verificar: buscar la fila de vuelta
s3, d3 = post('documents.info', {'id': DOC_ID})
print('fila presente:', '<owner>/<repo>' in d3['data']['text'])
```

### 6. Deliver Report

```
📦 **<name>**
**<full_name>**
🔥 **<N> ⭐** · <N> forks · <time>
---
**Lenguaje:** <T> · **Licencia:** <L>
---
**¿Qué es?** <summary>
**¿Qué soluciona?** <problem>
**Potencial NeuralCrew <rating>** <pros> **Riesgo:** <risk>
**Tags:** #t1 #t2
✅ Brain Wiki + ficha Repos en wiki
```

## Pitfalls

- Default branch may be `master` not `main` — check API first
- GitHub API rate: 60/hr unauthenticated; use token for heavy loads
- Outline API: SIEMPRE `Host: wiki.neuralcrewlabs.com` + `X-Forwarded-Proto: https`
  (sin ellos da 301/405); todos los endpoints POST; `documents.update` con
  `publish:true`; filtro borradores en `list` → usar `documents.search` para
  auditar; NO hay upsert (crear siempre doc nuevo) → aquí usamos `update`
  sobre la ficha existente, no `create`.
- La ficha `Repos` id puede cambiar: verificar con `documents.search "Repos"`
  en la colección `NeuralCrew Interno` antes de escribir.
- Rich text paragraph limit 2000 chars (Notion legacy — no aplica a wiki)
