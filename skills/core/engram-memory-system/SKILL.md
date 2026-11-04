---
name: engram-memory-system
description: "Use when saving, searching or setting up Engram memory"
tags: [engram, memoria, mcp, persistencia, sqlite, fts, search, knowledge]
version: 1.0.0
author: Ragnar
license: MIT
metadata:
  hermes:
    tags: [engram, memory, mcp, persistence, gentle-ai, knowledge]
    category: devops
    related_skills: [brain-knowledge-base, brain-graph-maintenance, ecosystem-setup, dual-knowledge-system]
---

# Engram Memory System (MCP-based Persistent Memory)

Engram es el sistema de memoria persistente basado en MCP que permite a Hermes guardar, buscar y juzgar observaciones estructuradas que sobreviven a la compactación de contexto y reinicios de sesión.

Se integra con Gentle AI como la capa 3 del stack (OpenCode/Orca → Gentle AI → Engram).

## Architecture

```
Hermes (agente principal)
  └── MCP client → engram mcp (servidor stdio)
        └── SQLite DB (.engram/engram.db)
              └── Observations (con tipo, proyecto, sesión, metadatos)
```

Engram no reemplaza el Brain Wiki (markdown en `/opt/data/brain/`) — es una capa complementaria:
- **Brain Wiki**: conocimiento profundo, estructurado por directorios, consultable por búsqueda de archivos
- **Engram**: observaciones rápidas, searchable por FTS, con dedup, juicio de conflictos, y persistencia cross-session vía MCP

## Setup (Verified 08/08/2026)

### 1. Instalación (dentro del contenedor Docker)

```bash
# Gentle AI incluye engram
pip install gentle-ai
gentle-ai doctor  # Verifica que todo esté OK (6/6 checks)
```

### 2. Sincronización con Hermes

```bash
gentle-ai sync  # Registra el agente, crea .hermes/config.yaml con MCP
```

**IMPORTANTE**: Si ya creaste `.engram/config.json` con el project name (paso 3), ejecuta `gentle-ai sync` DESPUÉS — el sync registra el agente con el contexto del proyecto ya configurado.

Esto crea/actualiza `/opt/data/home/.hermes/config.yaml` con:
```yaml
mcp_servers:
  engram:
    command: /usr/local/bin/engram
    args:
      - mcp
      - --tools=agent
```

### 3. Configurar proyecto en el directorio de trabajo

Crea `.engram/config.json` en el directorio raíz para resolver el proyecto automáticamente:

```json
{"project_name": "hermes"}
```

Engram auto-detecta proyectos por: `.engram/config.json` > git remote > ambiguous → error con recovery_token.

### 4. Permisos críticos

El MCP server de engram escribe a SQLite. Sin permisos de escritura, el server crashea después de 1-2 requests y Hermes lo parkea con "unreachable after N consecutive failures".

```bash
chown -R hermes:hermes /opt/data/home/.hermes/ /opt/data/home/.engram/
```

Los directorios relevantes son:
- `/opt/data/home/.hermes/` — config MCP de engram
- `/opt/data/home/.engram/` — SQLite DB de engram
- `/opt/data/.engram/` — config.json del proyecto (si existe)

### 5. Recuperar de circuit breaker MCP

Si engram MCP acumula 7+ fallos consecutivos, Hermes lo parkea con auto-retry ~55s. Si eso no funciona:

```bash
docker restart hermes-agent  # Limpia el circuit breaker completamente
```

## Usage Pattern

### Iniciar sesión

```python
mem_session_start(directory="/opt/data", id="session-id-2026-08-08", project="hermes")
```

### Guardar observaciones

```python
mem_save(
    title="Nombre descriptivo",
    content="**What**: ...\n**Why**: ...\n**Learned**: ...",
    type="persona|client|architecture|config|decision|process",
    session_id="session-id-2026-08-08",
    project="hermes"
)
```

### Buscar memorias

```python
mem_search(query="palabras clave", limit=10)
mem_search(query="palabras clave", all_projects=True)
```

### Estrategia de búsqueda bilingüe (ES/EN)

Engram es escrito por múltiples actores (subagentes, scripts, mem_capture_passive) que tienden a usar INGLÉS en títulos y keywords, incluso cuando el usuario conversa en español.

**Protocolo cuando el usuario pregunta en español:**

1. Buscar con términos del usuario (ES) — `mem_search(query="modelos OpenCode cambio", all_projects=True)`
2. Si vacío → traducir el concepto central al inglés y buscar UN sustantivo clave — `mem_search(query="model", all_projects=True)`
3. Si vacío → probar términos aún más amplios — `mem_search(query="OpenCode", all_projects=True)`
4. Si vacío → probar `mem_context()` para ver qué se guardó recientemente
5. **No rendirse tras 1 intento** — probar al menos 3 variaciones lingüísticas

**Ejemplos reales:**

| Pregunta (ES) | Search fallido | Search exitoso (EN) |
|---|---|---|
| ¿cambio modelos OpenCode? | `"modelos OpenCode cambio"` | `"model"` |
| configuración Twenty CRM | `"configuración Twenty"` | `"Twenty CRM"` |
| plan despliegue agentes | `"plan despliegue"` | `"deployment"` o `"production"` |

### Juicio de conflictos (dedup)

Cuando `mem_save` retorna `judgment_required=true`, engram detectó similitud con observaciones existentes.

```python
mem_judge(
    judgment_id="rel-<hex>",
    relation="compatible",
    confidence=1.0,
    reason="Categorías distintas — mantener separadas"
)
```

Revisar conflictos pendientes:
```python
mem_review(action="list", project="hermes")  # Verifica conflictos sin juzgar
mem_review(action="list", limit=20)           # Todos los proyectos
```

| Situación | Relación |
|-----------|----------|
| Info complementaria mismo tema | `scoped` |
| Categorías distintas (identidad vs infra) | `compatible` |
| Duplicado exacto | `supersedes` |
| Hechos contradictorios | `conflicts_with` (ask user) |
| Sin relación real | `not_conflict` |

## Knowledge Migration Workflow

### Prioridad (más valioso primero)

1. Identidad (persona) → 2. Clientes (client) → 3. Infraestructura (architecture) → 4. Decisiones (decision) → 5. Procesos (process) → 6. Brain graph (raw)

### Formato recomendado

```
**What**: Descripción del conocimiento
**Why**: Contexto/razón
**Where**: Ubicación física (path, URL, sistema)
**How**: Cómo funciona
**Learned**: Lecciones aprendidas
```

### Estrategia de lotes

- Guarda 3-5 por tanda, juzga conflictos inmediatamente después
- Conflictos no juzgados se acumulan y engram deja de sugerir dedup

### Verificación de integridad

```python
mem_stats()                          # Confirma conteo (sesiones, observaciones)
mem_search(query="término clave")    # Verifica que FTS indexó las observaciones
```

Si `mem_search` retorna vacío pero `mem_stats` muestra el conteo correcto, las observaciones SÍ están guardadas — el índice FTS puede estar desfasado. Usa el sync_id para confirmar o reintenta la búsqueda con términos más específicos.

## Pitfalls (all hit 08/08/2026)

- **MCP caído no es bug de engram** — es Permission denied. Verificar ownership antes de reportar.
- **Proyecto ambiguo** — crear `.engram/config.json` con `{"project_name": "..."}`
- **Campo correcto es `project_name` no `project`** — `"project"` da error
- **`gentle-ai sync` crea config separado** en `~/.hermes/config.yaml` con `--tools=agent`
- **No duplicar en memory tool lo que ya está en engram** — memory tiene ~10K chars, engram no tiene límite
- **FTS index asíncrono** — tras guardar, `mem_stats` refleja el conteo inmediatamente, pero `mem_search` puede devolver vacío por unos segundos. Los datos están ahí, no reintentes la escritura.