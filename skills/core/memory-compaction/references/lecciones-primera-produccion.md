# Lecciones de la primera corrida en producción (04-nov-2026, perfil default)

1. **mem_recall.py NO acepta `--profile`** (ni otros flags de memory_inventory). Flags reales: `--limit`, `--archive-dir`, `--only-archive`, `--json`, `--no-engram/brain/repos`. Exit 1 cuando no hay resultados (correcto).

2. **Verificación post-apply: emparejar por sha1 de CONTENIDO, nunca por índice.** Al retirar 103 de 174 entradas, los índices se re-encuadran y comparar idx nuevo vs viejo da falsos 0/71. El método correcto: hashear cada entrada del store resultante y verificar pertenencia al conjunto de sha1s `keep` del plan.

3. **Correr inventario con `--emit-plan` justo antes de rellenar el plan**: el plan fija el sha1 del store; cualquier write de memoria intermedio invalida el plan (gate lo rechaza — correcto, pero obliga a regenerar).

4. **Sembrar el `.brain_manifest.json` de un grafo nuevo desde el del grafo vigente** al cambiar de directorio canónico, o el primer incremental re-extraería todo.

5. **La cadena real del cron del grafo brain** (no confundir): `jobs.json (brain-graph-update-noche, 3:30am) → brain_graph_update_wrapper.sh → brain_graph_update_inner.sh`. `run_brain_graph.sh` es launcher legacy NO usado por el cron. El inner tiene guardas propias (diff por hash, tope de crecimiento, backup dominical) — no duplicarlas.

6. **Bugs del verificador ≠ bugs del apply**: ante un FAIL de verificación propia, re-verificar el método antes de sospechar del gate.