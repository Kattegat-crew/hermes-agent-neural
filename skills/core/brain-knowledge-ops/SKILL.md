---
name: brain-knowledge-ops
description: >-
  Operaciones sobre la base de conocimiento y grafo del Brain. Consulta eficiente por graph.json, sincronización de notas en Obsidian/Markdown y mantenimiento de memoria.
tags: [brain, memoria, knowledge, engram, graph, wiki, obsidian, roshi]
version: 2.0.0
author: NeuralCrew / Hermes Fleet
---

# Operaciones sobre el Brain y Grafo de Conocimiento

Habilidad canónica para consultar, estructurar y mantener la base de conocimiento empresarial acumulativa de la flota Hermes (`/opt/data/brain/`), navegando de forma eficiente a través de su grafo semántico (`graph.json`) en lugar de realizar barridos ciegos de cientos de archivos markdown.

---

## Cuándo usar esta Skill (Triggers y Síntomas)

Usa esta skill inmediatamente cuando se presente cualquiera de estas situaciones:
- Peticiones del usuario: *"consulta el brain"*, *"qué sabemos sobre este cliente/campaña en el grafo"*, *"actualiza el índice del brain"*, *"el grafo de memoria no está actualizado"*, o *"busca en las notas de la empresa"*.
- Búsqueda de relaciones entre entidades, decisiones pasadas, reglas de negocio o arquitectura sin saturar la ventana de contexto del agente.
- Re-indexación periódica del directorio `/opt/data/brain/` mediante herramientas de grafos (Graphify / GGA).

---

## 1. Consulta Quirúrgica mediante el Grafo Semántico

El directorio del brain almacena cientos de notas en Markdown. **Regla de oro: Nunca leer decenas de archivos `.md` de forma secuencial.** Eso colapsa la ventana de contexto y desperdicia tokens. La consulta debe hacerse sobre el grafo:

```bash
# 1. Ubicación del grafo persistente
BRAIN_GRAPH="/opt/data/brain/graph.json"

# 2. Consultar entidades y relaciones por palabra clave
jq '.nodes[] | select(.id | test("golden|paradise|hermes"; "i"))' "$BRAIN_GRAPH"

# 3. Consultar las conexiones de un nodo específico
jq '.edges[] | select(.source=="cliente-golden" or .target=="cliente-golden")' "$BRAIN_GRAPH"
```

Una vez identificado el nodo exacto en el grafo, el agente lee **únicamente** la nota puntual que contiene la evidencia requerida.

---

## 2. Estructura de Notas en el Brain (Markdown Compuesto)

Toda nueva nota añadida al brain debe respetar el formato estándar de enlaces bidireccionales tipo Obsidian:

1. **Frontmatter canónico**:
   ```yaml
   ---
   id: nombre-entidad
   type: cliente | decision | arquitectura | campaña
   tags: [etiquetas, clave]
   updated_at: "2026-10-17"
   ---
   ```
2. **Enlaces explícitos**: Usar `[[id-otra-nota]]` para declarar dependencias y relaciones.
3. **Sección de Hechos Inmutables**: Datos verificados con fecha y fuente.
4. **Historial de Decisiones**: Por qué se tomó cada determinación arquitectónica o comercial.

---

## 3. Mantenimiento y Re-indexación del Grafo

Cuando se hayan agregado o modificado múltiples notas en `/opt/data/brain/`:

```bash
# Reconstruir el grafo de conocimiento
python3 -c "
import json, glob, os

nodes = []
edges = []
for f in glob.glob('/opt/data/brain/**/*.md', recursive=True):
    name = os.path.basename(f).replace('.md', '')
    nodes.append({'id': name, 'path': f})

# Guardar estado actualizado
with open('/opt/data/brain/graph.json', 'w') as out:
    json.dump({'nodes': nodes, 'edges': edges}, out, indent=2)
print('Grafo de notas sincronizado exitosamente.')
"
```

---

## Gotchas y Errores Críticos

1. **Desincronización de enlaces rotos**: Si renombras una nota en el brain sin actualizar las referencias `[[nota]]` en los demás archivos, los analizadores de grafos generarán nodos huérfanos.
2. **Duplicación de memorias**: La información táctica y de corto plazo vive en las sesiones de Hermes o en Engram; el Brain (`/opt/data/brain/`) se reserva exclusivamente para conocimiento compuesto a largo plazo (reglas de negocio, clientes, credenciales maestras y arquitectura).
