---
name: technical-proposal-review
description: "Use when evaluating a technical proposal or a relatoría."
version: 1.0.0
author: Ragnar
license: internal
tags: [evaluacion, relatoria, propuestas, hackathon, plugins]
---

# Technical Proposal Review & Relatoría

## When to Use
Evaluación severa de una propuesta técnica/arquitectónica (interna o de hackathon) con múltiples revisores, y redacción de la relatoría que consolida hallazgos, veredictos y plan de envío.

## Always-on rules
- Verify every premise against the live system (measure, clone, read from disk) before judging; label each finding `verificado` (with source: file:line, command output, or measurement) or `sin reproducir`. Never judge from memory or a previous session's snapshot.
- Evaluate proposals against the mature state of a growing installation (installed skills accumulate, memory accumulates), not the day-0 clean clone — day-0 metrics understate the problem. Separately flag any premise that describes local fleet configuration as if it were native behavior.
- Never propose a lexical/keyword gate as first-stage skill selector: users describe the task, not the skill, so keyword matching returns nothing on most messages (tested evidence ≈100% no-match). The interpreter must decide; compress what the interpreter READS (compact per-skill context paragraph), not who decides.
- Do not quote a baseline metric measured under our own prompt or instructions as native behavior — state the contamination explicitly.

## Procedure
1. **Aritmética en ambas direcciones:** medir el eje de costo con mecanismo ON leyendo índice compacto, ON leyendo el catálogo completo (peor caso), y hoy sin mecanismo. Una optimización solo cuenta si su mecanismo no consume lo que pretende ahorrar.
2. **Separar eliminable de acotable:** los round-trips extra no se eliminan, se acotan (primera etapa barata solo cuando hay ambigüedad). Prometer «latencia medida y acotada», nunca «mínima latencia».
3. **Nombrar bien al enemigo:** medir qué componente domina el costo por turno (índice del catálogo vs memoria) antes de aceptar el framing del documento; el framing suele señalar el componente equivocado.
4. **Chequeo de saturación:** antes de reclamar novedad, revisar descripciones en el catálogo de plugins (`/opt/hermes-agent/plugin-catalog/*.yaml`) buscando equivalentes directos por nombre y función.
5. **Relatoría (Markdown, entregada adjunta + resumen en Discord):** objeciones por revisor y cuáles sobrevivieron a las aclaraciones; tabla de hallazgos (hallazgo / fuente / estado); veredicto pieza por pieza (VÁLIDA / RENOMBRAR / DEGRADAR / POSPONER); propuesta reformulada; regla de decisión basada en medición («si la cascada le gana a X por ≥N puntos se envía A, si no B» — siempre debe existir camino de envío); plan día a día hasta el deadline; sección de cierre «lo que NO vamos a prometer».
6. **Discrepancia de números entre revisores:** reproducir ambas mediciones, elegir un método y declararlo — nunca promediar ni elegir en silencio.
