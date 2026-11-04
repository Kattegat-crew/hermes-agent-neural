---
name: graphify-codebase-graph
description: "Use when querying an existing codebase graph (graph_query)."
tags: [graphify, grafo, codebase, dependencias, comunidades, graph-query]
---

# Graphify Codebase Graph

El sistema de grafos de Ragnar. Cada repo tiene su grafo generado en `/opt/graphs/<repo>/graphify-out/graph.json` (JSON de NetworkX: nodes, links, hyperedges).

## Repos disponibles
- `hermes-agent` (36,222 nodos / 75,914 links / 1,005 archivos)
- `ai-platform`
- `golden-game-landing`

## Estructura del grafo
- **Nodos**: `file_type` = `code` (24,765) | `rationale` (11,403) | `concept` (54) | `package`. Campos: `id`, `label`, `source_file`, `source_location` (L#), `community` (1217 comunidades).
- **Links**: `relation` = `calls` (25k), `method`, `rationale_for`, `contains`, `uses`, `references`, `imports`, `imports_from`, `indirect_call`, `inherits`, `re_exports`, `defines`, `extends`. Cada link: `source`, `target`, `relation`, `source_file`, `confidence`.
- `_origin`: `ast` o `semantic`. `confidence_score`: 0-1.

## CLI de consulta (script oficial)
```bash
python3 /opt/data/scripts/graph_query.py <repo> <consulta> [args]
```

### Consultas
| Comando | Descripción | Ejemplo |
|---|---|---|
| `stats` | Estadísticas del grafo | `graph_query.py hermes-agent stats` |
| `files [N]` | Archivos cubiertos (top N=40) | `files 20` |
| `file <ruta>` | Nodos code + imports + dependents de un archivo | `file gateway/platforms/telegram.py` |
| `deps <ruta>` | Solo dependencias directas | `deps agent/agent.py` |
| `dependents <ruta>` | Quién depende de un archivo | `dependents tools/mcp_tool.py` |
| `callers <id>` | Quién llama a un nodo | `callers tools_mcp_tool_mcp_tool_init` |
| `callees <id>` | A quién llama un nodo | `callees <id>` |
| `search <texto>` | Busca nodos por label/id | `search mcp_tool` |
| `community <id>` | Nodos de una comunidad | `community 0` |
| `neighbors <id>` | Vecinos in+out de un nodo | `neighbors <id>` |
| `relations [N]` | Distribución de relaciones | `relations 10` |
| `types [N]` | Distribución de file_type | `types` |

## Uso con Python directo (consultas ad-hoc)
```python
import json
from collections import defaultdict
g = json.load(open('/opt/graphs/hermes-agent/graphify-out/graph.json'))
nodes, links = g['nodes'], g['links']
by_id = {n['id']: n for n in nodes}
out_links = defaultdict(list)
for l in links:
    out_links[l['source']].append(l)
# nodos code de un archivo:
cn = [n for n in nodes if n.get('source_file')=='gateway/platforms/telegram.py' and n.get('file_type')=='code']
```

## Pitfalls
- **TRAMPA host/contenedor (crítica)**: `/opt/data` EXISTE en el host como espejo viejo que NADIE lee — NO es el bind mount. El árbol vivo en el host es `/root/hermes-agent-legacy-docker/data`. So cualquiera de estos grafos u otro asset vive en `/opt/data/...` (contenedor) = `/root/hermes-agent-legacy-docker/data/...` (host). Scripts con rutas hardcodeadas `/opt/data` corriendo desde el host escriben al espejo muerto y pierden el trabajo. Aplica a TODOS los grafos, no solo de codebase.
- Los symlinks de perfiles a vaults solo resuelven DENTRO del contenedor — desde el host parecen rotos.
- El grafo se generó de `/root/hermes-agent-legacy-docker` — las rutas son relativas al repo, NO a `/opt/data/`.
- `graph.json` pesa ~43MB: no usar `read_file` sobre él, siempre Python.
- No hay CLI `graphify` instalado; el script `graph_query.py` es el interfaz.
- Para regenerar grafos de skills usar `python3 /opt/data/scripts/build_skills_graph.py --all-profiles` (global: `--global`); el binario graphify vive en `/opt/data/.venv-graphify/bin/graphify` (NO en PATH).
- 869 nodos tienen `source_file` vacío (nodos package/concept globales).
- Los tests son ~60% de los nodos; filtrar con `source_file` si solo interesa código productivo (excluir `tests/`).
- `.graphify_analysis.json` contiene las comunidades (detección de clústeres) — útil para ver agrupaciones de módulos.
- `manifest.json` tiene hashes por archivo (mtime/ast_hash/semantic_hash) — sirve para saber si el grafo está desactualizado vs el código real.

## Regenerar el grafo
Los grafos viven en `/opt/graphs/` (generados 2026-08-02 por Jonathan con graphify, ~20:37 UTC). Si el código cambia mucho, pedir regeneración.
