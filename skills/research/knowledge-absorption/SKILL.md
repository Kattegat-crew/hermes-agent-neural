---
name: knowledge-absorption
description: >-
  Use when absorbing external sources into the brain wiki. Absorber y transformar conocimiento desde fuentes externas (Notion, docs, web) hacia el Brain wiki. Incluye estrategias de priorización, deduplicación, y filtrado de ruido para absorber SOLO lo que importa. hermes: tags: [wiki, knowledge-base, absorption, notion, research] category: research related_skills: [brain-knowledge-base, notion-integration, defuddle, local-vision-toolkit, document-reader]
version: 1.0.0
author: Ragnar
license: MIT
metadata:---

# Knowledge Absorption — De Fuentes a Brain

Procedimiento para absorber conocimiento desde fuentes externas hacia el Brain wiki
de forma eficiente, estratégica y con filtrado de ruido.

## Cuándo Usar
- El usuario dice "escanea Notion", "absorbe X", "lee Y y guárdalo"
- Migrar conocimiento de otra herramienta al Brain
- Actualizar Brain con nueva información de una fuente
- Investigar y documentar un tema nuevo

## Reflexión del Día (2026-04-25) — Lecciones Aprendidas

### ✅ Lo que hicimos BIEN
1. **Delegación en paralelo** — Dos subagentes trabajando simultáneamente ahorró tiempo
2. **Estructura Brain ya existente** — No empezamos de cero, teníamos SCHEMA.md, index.md, log.md
3. **Frontmatter consistente** — Todas las páginas tienen metadata (title, type, tags, source, created)
4. **Wikilinks** — Usamos `[[wikilinks]]` para conectar entidades
5. **Fuente referenciada** — Cada página tiene `source: notion://pagina` para trazabilidad
6. **Contenido accionable** — No solo copiamos, transformamos en páginas estructuradas

### ⚠️ Lo que hicimos MAL / PODRÍA SER MEJOR
1. **No filtramos ruido** — Absorbimos páginas de investigación genérica (50+ artículos de AI trends)
   que no son específicos de Nexa Labs. Ruido = pérdida de token space.
2. **Daily Reports = metadata** — Los reports tenían poco contenido real, solo IDs y URLs.
   No valía la pena absorberlos tal cual.
3. **No priorizamos** — Leímos 72 páginas sin saber cuáles eran críticas.
   Deberíamos haber identificado primero las 10 más importantes.
4. **Páginas duplicadas** — Algunos módulos existían en Notion como DB entries Y como sub-páginas.
   Creamos versiones duplicadas (nexa-social-module + nexa-social, nexa-leads + nexa-leads-page).
5. **No actualizamos memoria persistente** — No guardamos lecciones en `memory()` durante el proceso.
6. **No creamos skill al final** — Deberíamos haber creado esta skill antes de terminar.
7. **Contenido en inglés vs español** — Algunas páginas de investigación están en inglés,
   otras en español. No estandarizamos el idioma.

### 📊 Métricas del Día
- **Páginas en Notion:** 93 páginas + 7 bases de datos
- **Páginas leídas:** 72 (de las cuales ~30 eran ruido/research genérico)
- **Páginas absorbidas:** 14 páginas en Brain
- **Tamaño Brain:** ~30 KB
- **Tiempo total:** ~10 minutos (delegación + escritura)
- **Ratio ruido/valor:** ~60% ruido (artículos genéricos de AI)

### 🔄 Qué Haremos Mejor la Próxima
1. **Filtrar antes de absorber** — Identificar páginas relevantes vs genéricas ANTES de leer
2. **Priorizar por impacto** — Primero: organigrama, stack, módulos, clientes, financiamiento
3. **Deduplicar** — Si una info está en 3 páginas, fusionar en una sola
4. **Estandarizar idioma** — Todo en español para Nexa Labs
5. **Actualizar memoria en tiempo real** — Guardar lecciones en `memory()` durante el proceso
6. **Crear skill al final** — Convertir el aprendizaje en skill reutilizable
7. **Respectar límites de contexto** — No absorber TODO, solo lo que el Brain necesita

## Procedimiento

### Fase 1: Exploración (No leer contenido)
1. **Conectar a la fuente** — Notion API, web, docs, etc.
2. **Listar TODOS los items** — Obtener títulos, tipos, metadatos (NO leer contenido aún)
3. **Clasificar por prioridad:**
   - **P1 (Crítico):** Organigrama, stack, módulos, clientes, finanzas, identidad
   - **P2 (Importante):** Proyectos activos, agentes, herramientas, procesos
   - **P3 (Referencia):** Investigación, tendencias, comparaciones
   - **P4 (Ruido):** Templates, contenido genérico, duplicados, legacy
4. **Filtrar P4** — Descartar inmediatamente
5. **Priorizar P1 > P2 > P3** — Solo absorber lo relevante

### Fase 2: Extracción (Leer solo lo prioritario)
1. **Para cada página P1/P2:**
   - GET properties + GET blocks children
   - Extraer contenido en formato markdown
   - Guardar temporalmente
2. **Para páginas P3:**
   - Solo extraer título + resumen (no TODO el contenido)
   - Guardar como referencia rápida
3. **Paginación:** Siempre verificar `has_more`

### Fase 3: Transformación (No copiar, transformar)
1. **Identificar entidades** — Personas, empresas, productos, herramientas
2. **Identificar conceptos** — Procesos, metodologías, arquitecturas
3. **Identificar proyectos** — Workstreams activos con estado
4. **Crear páginas Brain:**
   - Usar frontmatter: `title`, `type`, `tags`, `created`, `source`
   - Usar wikilinks `[[entidad]]` para conexiones
   - No copiar texto literal, reescribir en formato Brain
   - Unificar información duplicada
5. **Idioma:** Estandarizar al idioma del usuario

### Fase 4: Integración
1. **Actualizar index.md** — Agregar todas las páginas nuevas
2. **Actualizar log.md** — Registrar qué se absorbió y cuándo
3. **Actualizar memoria** — Guardar lecciones aprendidas en `memory()`
4. **Reportar al usuario** — Resumen de lo absorbido con métricas

## Ruteo de lo Absorbido (mapa de carpetas)

El destino de cada página sigue la estructura del brain (entities/, concepts/, tasks/, raw/) y las reglas de `mapa-de-carpetas`: consulta el mapa antes de escribir, usa wikilinks y frontmatter, y no crees carpetas nuevas sin autorización.

## Formato de Páginas Brain

### Entidades (entities/)
```markdown
---
title: Nombre
type: person | company | agent | tool | team
tags: [absorcion, wiki, brain, notion, filtrado, deduplicacion, priorizacion]
created: YYYY-MM-DD
source: fuente://pagina
---

# Nombre

**Rol/Descripción corta**

## Rol / Descripción
- Detalle 1
- Detalle 2

## Relaciones
- [[otra_entidad]] — Tipo de relación

## Notas
- Información relevante
```

### Conceptos (concepts/)
```markdown
---
title: Nombre
type: concept
tags: [tag1, tag2]
created: YYYY-MM-DD
source: fuente://pagina
---

# Nombre

## Descripción
Qué es y para qué sirve

## Componentes / Detalles
- Detalle 1
- Detalle 2

## Estado / Métricas
- Información relevante
```

### Proyectos (projects/)
```markdown
---
title: Nombre
type: project
tags: [tag1, tag2]
status: active | paused | completed
created: YYYY-MM-DD
source: fuente://pagina
---

# Nombre

## Descripción
Qué es

## Estado
- Actual

## Próximos pasos
- Acción 1
- Acción 2
```

## Estrategia de Filtrado

### Descartar automáticamente (P4):
- Templates de Notion pre-instalados
- Contenido de "Wiki legacy" desconectado
- Páginas sin contenido real (solo metadata)
- Artículos genéricos de investigación AI (trends, benchmarks)
- Duplicados exactos marcados como tal
- Contenido de terceros sin relación con la empresa

### Absorber selectivamente (P1-P3):
- **P1:** Todo lo que define QUIÉNES somos, CÓMO operamos, QUÉ hacemos
- **P2:** Todo lo que afecta operaciones diarias
- **P3:** Solo título + resumen + URL de referencia

### Regla de oro:
> **Si no ayuda al agente a tomar mejores decisiones HOY, no va al Brain.**

## Flujo de Imágenes al Brain

Cuando el usuario comparte una imagen (screenshot, gráfico, diagrama, infografía) y quiere guardarla en el Brain:

1. **Extraer con local-vision-toolkit:**
   ```bash
   python3 SKILL_DIR/../local-vision-toolkit/scripts/vision_tool.py imagen.png --action full --format json
   ```

2. **Crear página Brain con frontmatter:**
   ```markdown
   ---
   title: {description_short}
   type: image_analysis
   tags: [image, {chart_type|diagram|infographic}, {category}]
   created: YYYY-MM-DD
   source: local
   ---

   # {Title}

   ## Descripción
   {natural language description from toolkit}

   ## Texto Extraído
   {OCR text if any}

   ## Análisis Estructural
   {structured analysis from toolkit}
   ```

3. **Actualizar index.md** con la nueva página.

**Ejemplo — screenshot de dashboard:**
```bash
python3 SKILL_DIR/../local-vision-toolkit/scripts/vision_tool.py dashboard.png --action full --format json
# Returns: chart types, text, description
# Create Brain page with the extracted data
```

**Ejemplo — diagrama de arquitectura:**
```bash
python3 SKILL_DIR/../local-vision-toolkit/scripts/vision_tool.py arch.png --action diagram --format json
python3 SKILL_DIR/../local-vision-toolkit/scripts/vision_tool.py arch.png --action ocr --format json
# Combine: diagram type + shape count + OCR labels = full understanding
```

## Métricas de Calidad
- **Ratio absorción:** Páginas absorbidas / Páginas leídas (objetivo: >40%)
- **Duplicados:** Debería ser 0 (fusionar antes de crear)
- **Wikilinks:** Cada página debe tener al menos 2 conexiones
- **Trazabilidad:** Cada página debe tener `source` referenciado

## Integración con Otras Skills
- **brain-knowledge-base:** Estructura del wiki, convenciones
- **notion-integration:** API de Notion, paginación, autenticación
- **defuddle:** Extraer markdown limpio de páginas web
- **obsidian-cli:** Si se usa Obsidian como capa humana
- **local-vision-toolkit:** Cuando la fuente es una imagen (screenshot, diagrama, gráfico, infografía). Primero extraer texto y estructura con el toolkit, luego absorber el resultado al Brain.
- **document-reader:** Cuando la fuente es un documento (PDF, Word, Excel). Complementar con local-vision-toolkit para análisis visual profundo.

## Pitfalls
- **No absorbas TODO** — El Brain no es un data lake, es un cerebro. Filtra.
- **No copies literal** — Transforma, no hagas copy-paste de Notion
- **No ignores duplicados** — Fusiona antes de crear nuevas páginas
- **No olvides la fuente** — Siempre referencia `source:` para trazabilidad
- **No absorbas en inglés si el usuario habla español** — Estandarizar idioma
- **No te pierdas en investigación** — Si el usuario pidió "escanea Notion",
  escanea lo relevante, no los 50 artículos de AI trends que encontró Chucho
