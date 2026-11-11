# Lecciones de la primera corrida en producción (04-nov-2026, perfil default)

1. **mem_recall.py NO acepta `--profile`** (ni otros flags de memory_inventory). Flags reales: `--limit`, `--archive-dir`, `--only-archive`, `--json`, `--no-engram/brain/repos`. Exit 1 cuando no hay resultados (correcto).

2. **Verificación post-apply: emparejar por sha1 de CONTENIDO, nunca por índice.** Al retirar 103 de 174 entradas, los índices se re-encuadran y comparar idx nuevo vs viejo da falsos 0/71. El método correcto: hashear cada entrada del store resultante y verificar pertenencia al conjunto de sha1s `keep` del plan.

3. **Correr inventario con `--emit-plan` justo antes de rellenar el plan**: el plan fija el sha1 del store; cualquier write de memoria intermedio invalida el plan (gate lo rechaza — correcto, pero obliga a regenerar).

4. **Sembrar el `.brain_manifest.json` de un grafo nuevo desde el del grafo vigente** al cambiar de directorio canónico, o el primer incremental re-extraería todo.

5. **La cadena real del cron del grafo brain** (no confundir): `jobs.json (brain-graph-update-noche, 3:30am) → brain_graph_update_wrapper.sh → brain_graph_update_inner.sh`. `run_brain_graph.sh` es launcher legacy NO usado por el cron. El inner tiene guardas propias (diff por hash, tope de crecimiento, backup dominical) — no duplicarlas.

6. **Bugs del verificador ≠ bugs del apply**: ante un FAIL de verificación propia, re-verificar el método antes de sospechar del gate.

## Segunda producción — calibración del scorer con auditoría de reuso (v1.1.0)

7. **La cobertura léxica del brain no prueba que el dato se vaya a leer.** La corrida del 04-nov
   archivó 103 entradas por "ya cubierto en brain/skill (80-100%)"; 9 de ellas volvieron a usarse en
   la semana siguiente. El caso testigo: la regla de entrega de crons (#43) se archivó a la 01:59 y a
   las 16:00 del mismo día se cablearon 12 jobs a Discord en perfiles satélite sin comprobar
   capacidad — fallo con falso verde de `cron run` (ejecuta en línea, no por el gateway satélite).
   Desde v1.1.0: `reuse` medido contra `state.db` (fracción de datos duros reutilizados) pesa más que
   la cobertura, e `invariant_ack` bloquea archivar lenguaje de regla sin decisión explícita.

8. **Cobertura léxica vs. cobertura de datos duros.** Con 2.728 ficheros de skill en el corpus, casi
   cualquier entrada "cubre" ≥0,9 por vocabulario. El inventario reporta ahora `hard_coverage` (IDs,
   rutas, ficheros, cifras): si una entrada tiene 90% léxico y 0% de datos duros, no es duplicado, es
   parecido — y el `reason` del plan lo dice.

9. **Auditar el recibo anterior es parte de la corrida, no un extra.** `audit_previous()` compara los
   datos duros de cada entrada archivada contra las sesiones posteriores. Un recibo que coincide con
   el store vivo (aplicado y revertido) se ignora: si no, la ventana es de minutos y el reuso sale 0.

10. **Verificación post-apply salva de repetir el error.** El primer plan de esta corrida archivó
    #90 —la misma regla de Discord— con "cubierto en skill 90%". Se detectó comparando el store
    resultante contra la lista de invariantes esperados, se revirtió desde backup y se regeneró el
    plan. Regla: antes de dar por buena una compactación, comprobar que siguen en el store las
    entradas de la lista corta de invariantes (canales, bypasses, gates de gasto, entrega de crons).

11. **Un apply revertido deja basura en el archivo.** Mover sus `.jsonl`/`.md` a
    `memoria-archivo/anulados/` con sufijo `.anulado` y marcar el recibo (`"anulado": true`), o
    `mem_recall` devuelve cada entrada dos veces.
