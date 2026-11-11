---
name: hermes-ecosystem-tools
description: >-
  Use when evaluating Hermes community plugins. Discover/evaluate Hermes Agent community plugins and skills.
tags: [hermes, plugins, skills, evaluacion, github, ecosistema]
category: devops
---

# Hermes Ecosystem Tools

## Cuándo usar
- Descubres un tool/plugin/skill del ecosistema Hermes en Twitter, GitHub o blogs
- Necesitas evaluar si instalarlo en nuestro Hermes Agent
- Quieres trackear herramientas descubiertas para referencia futura

## Workflow de evaluación

### 1. Extraer info del descubrimiento
- Si viene de un tweet: usar browser_navigate para obtener contenido completo
- Identificar: nombre exacto del repo, autor, qué hace

### 2. GitHub Research API
```python
import json, urllib.request
req = urllib.request.Request(
    f"https://api.github.com/repos/{owner}/{repo}",
    headers={"User-Agent": "Mozilla/5.0", "Accept": "application/vnd.github+json"})
with urllib.request.urlopen(req, timeout=20) as r:
    d = json.load(r)
# Extraer: description, stargazers_count, forks_count, language, pushed_at
```

Siempre verificar README para entender funcionalidad real:
```python
import base64
req = urllib.request.Request(
    f"https://api.github.com/repos/{owner}/{repo}/readme",
    headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req, timeout=20) as r:
    d = json.load(r)
readme = base64.b64decode(d["content"]).decode("utf-8", errors="replace")
```

### 3. Criterios de evaluación
| Criterio | Qué mirar |
|----------|-----------|
| ⭐ Stars | Señal de adopción comunitaria |
| 📅 Último push | Sigue mantenido? |
| 🔧 Compatibilidad | Es plugin de Hermes? Skill? CLI autónomo? |
| 🎯 Relevancia | Resuelve un problema que tenemos? |
| 🛡️ Seguridad | Acceso a sistema? Lee/ejecuta comandos? |

### 4. Guardar en Brain Wiki
Crear entrada en `/opt/data/brain/raw/YYYY-MM-DD-hermes-{tool-name}.md` con:
- Descripción del tool
- GitHub stats
- README summary
- Evaluación de instalación
- Decisión: instalar sí/no y por qué

### 5. Herramientas descubiertas hasta ahora

| Tool | Stars | Función | Estado |
|------|-------|---------|--------|
| **Hermeskill** (theopitori/hermeskill) | 37⭐ | Apoptosis: detecta runaway/loops/autirización, genera death certificates. Plugin drop-in. | Pendiente instalar |
| **Hermes Bible** (DeployFaith/hermes-bible-skill) | 26⭐ | 169 páginas docs comunitarias + 25 workflows + patrones SOUL.md + intent routing | Pendiente clonar |
| **Hermes Achievements** (PCinkusz/hermes-achievements) | 50⭐ | 60+ logros desde session history, dashboard-ready | Evaluar |
| **PSI Skills** (Peter-Swain-Inc/psi-skills) | 1⭐ | 25 skills negocio: tráfico, leads, ventas, contenido | Baja prioridad |
| **Hermes Custom Pack** (AtlasOmnia/hermes-custom-pack) | 43⭐ | Field Kit verificado: security review, browser harness, design, Apple reminders | Pendiente revisar |
| **Astros** (Julian Goldie, tweet 14/08/2026) | — | Radar de competidores 24h dentro de Hermes: monitoriza keywords/competidores, puntúa temas por viralidad, genera títulos únicos; pipeline a SEO Content, Video Agent, Notebook; memoria compartida en Obsidian (Hermes/Astros/Oracle/Apollo) | Custom/privado — patrón replicable con Hermes + cron + Obsidian |

## Cómo instalar (cuando se decida)

### Hermeskill
```bash
# Plugin drop-in para Hermes Agent
uv tool install hermes-agent --with hermeskill-hermes
uv tool install hermeskill --with hermes-agent
uv tool update-shell
hermeskill enable-hermes
hermeskill doctor  # verificar instalación
```

### Hermes Bible
```bash
# Clonar skill completa (recomendado)
cd /opt/data/skills/
git clone https://github.com/DeployFaith/hermes-bible-skill.git
```

## Pitfalls
- **Compatibilidad** — verificar pushed_at vs nuestra versión de Hermes
- **Estrellas bajas** = puede ser experimental, revisar código antes de instalar
- **Plugins in-process (Hermeskill)** — evaluar overhead antes de activar en prod
- **Dependencias** — revisar requirements.txt de skills de terceros
- **web_search/web_extract no configurados** (sin Firecrawl) — investigar con el browser: GitHub search (`https://github.com/search?q=...`) funciona, Bing da resultados parciales (leer con `document.body.innerText`), DuckDuckGo suele lanzar CAPTCHA anti-bot → evitar como primera opción.
- **Tool mencionado puede no ser repo público** (ej: "Astros" de Julian Goldie, 14/08/2026) — tras búsqueda en GitHub/web sin resultados, NO inventar repo ni datos: indicar que parece custom/privado y analizar desde el contenido del tweet.
