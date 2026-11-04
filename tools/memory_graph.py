#!/usr/bin/env python3
"""
Herramienta de Consulta de Grafo de Memoria para Ragnar (Hermes Agent).
Permite buscar entidades, relaciones y conceptos dentro de /opt/hermes-agent-data/brain/graphify-out/graph.json.
"""

import json
import os
import sys

GRAPH_PATH = "/opt/hermes-agent-data/brain/graphify-out-v2/graph.json"
if not os.path.exists(GRAPH_PATH):
    GRAPH_PATH = "/opt/hermes-agent-data/brain/graphify-out/graph.json"

def query_memory_graph(query_text):
    if not os.path.exists(GRAPH_PATH):
        # Fallback to host path if testing locally
        alt_path = "/root/hermes-agent-legacy-docker/data/brain/graphify-out/graph.json"
        if os.path.exists(alt_path):
            path_to_use = alt_path
        else:
            return f"Error: No se encontró el grafo de memoria en {GRAPH_PATH}"
    else:
        path_to_use = GRAPH_PATH

    try:
        with open(path_to_use, "r", encoding="utf-8") as f:
            data = json.load(f)

        nodes = data.get("nodes", [])
        edges = data.get("links", []) or data.get("edges", [])

        query_lower = query_text.lower()
        matched_nodes = []

        for node in nodes:
            node_id = str(node.get("id", ""))
            label = str(node.get("label", ""))
            summary = str(node.get("summary", ""))
            content = str(node.get("content", ""))

            if query_lower in node_id.lower() or query_lower in label.lower() or query_lower in summary.lower() or query_lower in content.lower():
                matched_nodes.append({
                    "id": node_id,
                    "label": label,
                    "summary": summary[:300] if summary else content[:300]
                })

        if not matched_nodes:
            return f"No se encontraron entidades relacionadas con '{query_text}' en el Grafo de Memoria."

        result = f"=== Grafo de Memoria (/brain): Coincidencias para '{query_text}' ===\n"
        for idx, m in enumerate(matched_nodes[:8], 1):
            result += f"\n{idx}. [{m['label']}] (ID: {m['id']})\n   Resumen: {m['summary']}\n"

        return result
    except Exception as e:
        return f"Error leyendo el Grafo de Memoria: {str(e)}"

if __name__ == "__main__":
    if len(sys.argv) > 1:
        print(query_memory_graph(" ".join(sys.argv[1:])))
    else:
        print("Uso: memory_graph.py <pregunta/entidad>")
