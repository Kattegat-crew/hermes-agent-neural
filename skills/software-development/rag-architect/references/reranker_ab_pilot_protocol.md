# Protocolo piloto A/B de rerank (verificado en operación 03-nov-2026)

Procedimiento reproducible para responder: *¿el reranker coloca la evidencia correcta más arriba que el ordenamiento actual?* Ejecutado contra NAN `/v1/rerank` (20/20 HTTP 200, 350 pares query-documento) pero es agnóstico del proveedor. No activa nada en producción; el único requisito externo es un labeler independiente.

## Reglas duras

1. **Congelar el corpus de candidatos antes de llamar al reranker.** Generar `frozen.json` (candidatos + sha256 de cada texto y del archivo) y trabajar SOLO contra ese hash. Sin congelación, A y B no ven lo mismo y la comparación no significa nada.
2. **Etiquetado a ciegas ANTES de ver el orden del reranker.** Generar `blind-review.json` con los textos barajados (seed = id de la pregunta) y SIN títulos ni referencias que delaten el origen; entregar a un subagente/etiquetador independiente con escala 0 (no responde) / 1 (parcial) / 2 (evidencia directa). Si el labeler ve el ordenamiento, el benchmark está contaminado.
3. **Privacidad en el tránsito:** filtrar secretos/credenciales de los textos enviados al labeler y al reranker (regex de tokens/keys); los fragmentos excluidos se marcan y reciben 0 en ambos brazos por igual.
4. **Pool con tres tipos de pregunta:** intent (semántica), exact (token literal: IDs, placas, rutas) y negative (hechos imposibles que deben devolver 0 o score bajo). Las negative detectan rerankers que alucinan relevancia.
5. **Validar cada respuesta del ranker** como permutación exacta (`len`, índices, scores finitos) antes de calcular métricas.
6. **Métricas:** comparar precision@k y nDCG@k (con los qrels) entre orden baseline y orden rerank, más latencia añadida por query. Un rerank solo vale la pena si la ganancia de nDCG supera la latencia añadida en el caso de uso real.

## Flujo con las herramientas de la flota (lo que funcionó)

1. Preguntas → `questions.json`; candidatos via pipeline de recall existente (p.ej. `mem_recall.py` con su scoring y Engram, límites fijados por adelantado) → `baseline.json`.
2. Blind copy barajada + filtro de secretos → `blind-review.json` (sha256 registrado).
3. Labeler independiente via `delegate_task` (contexto autocontenido, prohibido leer baseline/frozen, output a `qrels.json`).
4. Llamadas al reranker con reintentos desactivados y stop-on-error → `nan-results.json` (incluye frozen_sha256, latencias, usage reportado).
5. Validación programática (hash congelado, permutaciones, conteo de pares) y solo entonces métricas.

Anti-patrón observado: el revisor de turnos anteriores ya había identificado que Jev (routing de skills) hace su propio reranking — evaluar rerank ahí sería duplicar una etapa; el valor está en el recall de memoria/Brain sobre un pool amplio de candidatos.

## Segunda ronda (v2, 04-nov-2026): lecciones del piloto refinado

Repetición con 20 preguntas nuevas y 586 pares (20/20 HTTP 200 del reranker). Lo que cambió y por qué:

1. **Falsos 2 de la ronda 1 (pitfall del labeler):** el etiquetador había dado relevancia 2 a pasajes que solo *describían un protocolo* o *enumeraban componentes sin explicar roles*. Corrección: fijar los `required_answer_elements` ANTES de recuperar, exigir para cada 2 una **cita textual (quote)** del candidato que contenga TODOS los elementos, y prohibir inferir desde nombres de skills, títulos o contexto propio. Los criterios gold NUNCA se envían a la búsqueda ni al reranker.
2. **Tres brazos en lugar de dos:** L (literal/scoring actual), H (fusión RRF k=60 de literal top-40 + Brain semántico top-40, dedupe por texto normalizado, top-20) y R (rerank sobre los MISMOS 20 pasajes congelados de H). L vs H mide recuperación+fusión; H vs R aísla el efecto del rerank — sin esto no se sabe si la mejora viene del embedding o del reranker.
3. **Resultado medido:** la fusión RRF sola puso la fuente gold en rank 1 en 12/16 preguntas con respuesta conocida (literal: 2/16, promedio rank ~5); 1 gold quedó inaccesible para ambos brazos (gap de recall real, no de ordenamiento). Latencia: embeddings de query 1 tanda (~2 s por 20 queries); rerank mediana ~1,3 s/query con 20 docs.
4. **Pasajes y trazabilidad:** párrafos naturales ≤1500 chars expandidos hacia vecinos con mayor IDF del corpus (nunca hacia la respuesta esperada), dedupe por sha256 del texto normalizado, boundary checks ejecutables; cobertura de la fuente gold registrada por brazo (`gold_source_coverage@20`), además de precision/MRR/nDCG.
5. **Privacidad y costo:** regex de secretos + lista explícita de refs excluidas (14 en v2: secrets, .env, notas con credenciales); topes duros declarados en un `protocol.json` (1 tanda de embeddings, N tandas de rerank, 0 retries, stop-on-error) y verificados programáticamente.
6. **Labeler en paralelo:** dividir las preguntas barajadas en 4 archivos `blind-N.json` para 4 subagentes ciegos concurrentes (seed de shuffle = id de pregunta), cada uno con prohibición explícita de leer frozen/baseline/qrels ajenos.