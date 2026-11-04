# Cross-Source Status Synthesis

**Learned:** 2026-08-13 — Sesión donde el usuario pidió un resumen de NeuralCrew Agency Platform (plan maestro, A2A, Twenty CRM, form bricks, VPS).

## El problema

Usuario pregunta por 5+ temas distintos. Cada uno puede estar en fuentes diferentes (Engram, session history, Brain Wiki, memoria persistente).

## El patrón

1. **Desglosar los temas** — identificar cada entidad/pregunta independiente
2. **Buscar cada tema en todas las fuentes disponibles**:
   - `mcp__engram__mem_search(query="tema", all_projects=True)` — Engram global
   - `session_search(query="tema", sort="newest")` — historial de sesiones
   - `read_file` o `search_files` para documentos plan conocidos
3. **Compilar en tabla por tema** — estado actual, dónde se guardó, qué falta
4. **Cerrar con el estado general** — qué está listo vs qué no se ha iniciado

## Fuentes en orden

| Fuente | Qué contiene | Cómo buscarla |
|--------|-------------|---------------|
| Engram MCP | Observaciones estructuradas | `mem_search(query="...", all_projects=True)` |
| Session history | Conversaciones completas | `session_search(query="...", sort="newest")` |
| Brain Wiki files | Documentos de plan, notas técnicas | `read_file(path)` o `search_files(pattern="*...*")` |
| Memoria persistente | MEMORY.md en system prompt | memory(action="replace", ...) o leer MEMORY.md |

## Pitfalls

- **Engram indexa en inglés** — buscar con términos en español puede fallar. Traducir al inglés.
- **Session search usa FTS5** — requiere términos exactos. Probar variaciones.
- **No asumir que un tema existe** — si no hay resultados en ninguna fuente, decirlo.
- **Documentos plan pueden estar en el VPS** — revisar archivos .md conocidos en /opt/data/.