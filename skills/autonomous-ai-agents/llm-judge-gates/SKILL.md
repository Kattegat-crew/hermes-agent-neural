---
name: llm-judge-gates
description: "Use when adding an LLM-judge gate to a pipeline"
tags: [llm, judge, juez, gate, moderacion, compliance, pipeline, shadow-mode]
---

# Gates con juez LLM (compliance, moderación, scoring)

Cuándo aplicar: cualquier check de aprobación de contenido (copy de campañas, moderación, score de riesgo) que se implemente con un modelo juez (ej. typesafe/jev, o un LLM con prompt de veredicto).

## Principios (en orden de decisión)

1. **Determinista primero.** Lo que resuelve `grep`/regex/lookup no se le pregunta al juez. Juez SOLO para intención difusa donde el léxico no separa («aquí los sueños se cumplen» y «ganarás seguro» comparten intención y no comparten palabras). Un diseño con 5 preguntas donde 2 son búsquedas de texto disfrazadas es un diseño mal calibrado — recortarlo.
2. **Colocación: donde hay humano, nunca donde el bloqueo es irreversible.** Verificar la ventana del punto de inserción ANTES de elegirlo — si no hay catch-up (ej. publica solo si `0 <= ahora - slot <= 2h` con tick horario), un bloqueo mata la pieza para siempre y a esa hora nadie está mirando. Colocar el gate en el paso de revisión/aprobación humana (ej. el paquete diario de las 07:30), no en la vía de ejecución.
3. **Informar, no sustituir.** El veredicto acompaña la aprobación humana; el humano aprueba. Un gate que veta sin medición previa puede ser solo ruido.
4. **Estado completo.** Pasar en el `state` TODO dato que las preguntas referencian (listas vigentes/cerradas, metadatos de la fila). El juez no puede validar contra datos que no recibió — y la pregunta quedará mal respondida sin que nadie lo note.
5. **Shadow mode antes de veto.** ~2 semanas registrando veredictos sin bloquear, medidos contra las aprobaciones reales del humano. Sin esa medición no se sabe si el gate acierta.
6. **Control negativo obligatorio** en la suite de validación: al menos un caso limpio que DEBE volver `pass`. Sin él no se detecta un clasificador que solo dice `block`.
7. **Costo estimado antes de instalar.** $ por llamada × piezas/día. Referencia medida: $0,00004 y ~400 ms por llamada → ~$0,03/mes a 20 piezas/día (irrelevante, pero demostrarlo, no suponerlo).

## Pitfalls
- La **confianza engaña como umbral**: no usar el score del proveedor como umbral sin calibrarlo contra casos etiquetados propios (positivos + control negativo). Hallazgo real del 16-sep-2026 al probar el endpoint.
- Los campos obligatorios del proveedor fallan tarde (HTTP 422): validar el esquema con una llamada de humo ANTES de cablear el gate en el pipeline.

## Caso de referencia
Gate regulatorio de copy del calendario de campañas (marketing-campaign-generator; propuesta 16-sep-2026 pendiente de decisión del Admin) → references/publication-gate-case.md. La parte de API y credenciales del proveedor vive en la skill `ai/typesafe-ai` (user-owned, no editable autónomamente).
