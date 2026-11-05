---
name: hermes-ecosystem-tools
description: >-
  Evaluar plugins de Hermes y medir huecos del catálogo.
tags: [hermes, plugins, skills, evaluacion, github, ecosistema]
category: devops
---

# Hermes Ecosystem Tools

## Cuándo usar
- Descubres un tool/plugin/skill del ecosistema Hermes en Twitter, GitHub o blogs
- Necesitas evaluar si instalarlo en nuestro Hermes Agent
- Quieres trackear herramientas descubiertas para referencia futura
- La pregunta es de ecosistema, no de un plugin: "¿qué falta?", "¿qué construimos?", "¿dónde está el hueco?" → sección *Análisis del corpus*

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

## Análisis del corpus (buscar huecos, no plugins sueltos)

Cuando la pregunta es estructural, no se evalúa plugin por plugin: se mide el catálogo completo.

1. **Fuente local:** `/opt/hermes-agent/plugin-catalog/*.yaml` (~911 manifiestos). Campos útiles: `name`, `category`, `tier`, `requires_hermes` y el bloque `capabilities:` con `provides_tools`, `provides_hooks`, `provides_middleware`.
2. **Contar por campo parseado, nunca con grep sobre el archivo entero:**
```python
m = re.search(r"provides_middleware:(.*?)(?:\n  [a-z_]+:|\Z)", text, re.S)
ks = re.findall(r"^\s*-\s*([a-z_]+)", m.group(1), re.M)
```
   `grep -i redact *.yaml` marcó 45 plugins cuando la capacidad real era casi nula: el `description:` de los manifiestos lleva prosa de disclosure ("…with secrets redacted…") y el grep la cuenta como capacidad. Grep sobre el YAML completo sobrecuenta siempre.
3. **Medición de referencia (verificada):** 28 plugins con middleware — `llm_request` 20, `llm_execution` 8, `tool_execution` 4, `tool_request` 2. De los 8 que envuelven `llm_execution`, ninguno reescribe el stream.
4. **Hueco real** = capacidad que el core ya expone como costura, que nadie usa, con incumbentes adyacentes que prueban demanda. Categoría vacía no es señal de oportunidad: puede ser el aviso de que nadie lo quiere. Los incumbentes dicen cuál mitad falta (p. ej. redacción de PII: tres plugins cubren la entrada usuario→modelo, ninguno la salida modelo→canal).
5. Antes de proponer o prometer arquitectura, leer `references/extension-surfaces.md` (kinds de middleware, hooks de stream y sus límites, reglas de admisión al catálogo).

## Formato obligatorio de propuesta (mesas de decisión de la flota)

Toda propuesta de plugin responde, en este orden: **quién lo paga o lo usa hoy** y por qué no existe todavía → **foso real** frente a la absorción por el core → **viabilidad** con el stack que ya tenemos → **riesgo declarado por adelantado**. Cada afirmación de mercado con fuente; si no hay dato, se escribe "sin dato", no una estimación disfrazada.

El foso nunca es el hook: si el core puede añadir la costura en dos versiones, el valor está en el corpus (políticas por jurisdicción, ledger auditable, normalización por proveedor). Diseñar el plugin para detectar el hook nuevo y degradar con fallback en vez de romperse.

**Prueba de flota real (elige el modo default con esto):** antes de presentar un modo como característica principal, verificar que protege al menos UNA superficie que la flota opera hoy. Si ningún canal propio streamea (nuestros puentes ensamblan el mensaje final y lo editan), el modo por-delta no protege a ningún cliente propio — solo a un comprador hipotético del jurado; ese modo se degrada a secundario y el modo fail-closed instalable hoy es el default. Verificar también el costo de fallo del modo default: si al fallar deja al bot de un cliente mudo con un aviso en inglés, la activación en perfiles de cliente queda bloqueada hasta tener fallback traducido.

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
- **Nunca construir sobre un recuento ajeno sin recomputarlo.** Un conteo de catálogo se re-mide en ~15 líneas de parseo sobre los YAML; se aceptó como línea base un "5 plugins con middleware" que al parsear `provides_middleware` eran 28, y el corolario estratégico ("middleware es tierra virgen") era falso. Si el número no lo mediste tú, no es dato.
- **Categoría vacía ≠ oportunidad.** Un hueco del catálogo puede ser falta de demanda. Se valida con incumbentes adyacentes o con alguien pagando el problema en otro mercado, nunca con el conteo en cero.
- **Compatibilidad** — verificar pushed_at vs nuestra versión de Hermes
- **Estrellas bajas** = puede ser experimental, revisar código antes de instalar
- **Plugins in-process (Hermeskill)** — evaluar overhead antes de activar en prod
- **Dependencias** — revisar requirements.txt de skills de terceros
- **web_search/web_extract no configurados** (sin Firecrawl) — investigar con el browser: GitHub search (`https://github.com/search?q=...`) funciona, Bing da resultados parciales (leer con `document.body.innerText`), DuckDuckGo suele lanzar CAPTCHA anti-bot → evitar como primera opción.
- **Tool mencionado puede no ser repo público** (ej: "Astros" de Julian Goldie, 14/08/2026) — tras búsqueda en GitHub/web sin resultados, NO inventar repo ni datos: indicar que parece custom/privado y analizar desde el contenido del tweet.
