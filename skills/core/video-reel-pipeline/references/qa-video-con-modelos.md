# QA de video con modelos de NAN — protocolo y costos

Medido el 2026-11-11 sobre un film de 69s, 1080p30, mismo prompt y mismo clip de prueba
(560px, 5 fps, 444 KB), temperature 0.2.

## Tokens reales por pasada

| modelo | tiempo | input | output | tramo NAN | fiabilidad |
|---|---|---|---|---|---|
| gemma4 | 1.9 s | 2.459 | 37 | unmetered (0 créditos) | baja: se saltó vacíos reales |
| qwen3.6 | 4.3 s | 12.397 | 42 | unmetered (0 créditos) | media |
| glm5.3-flash | 9.6 s | 17.031 | 91 | flash (fracción) | **alta: la más precisa** |
| glm5.3 | 12.3 s | 8.696 | 193 | larger model | inventa vacíos |
| qwen3.8-flash | 24.4 s | 13.157 | 1.285 | flash | inventa solapes |
| qwen3.8-max | 175 s | 13.124 | 6.038 | larger model | verborrágico, falsos positivos |

NAN no publica € por token fuera del portal (`cloud.nan.builders/tokens` pide sesión).
Los tramos sí están documentados: glm5.3 y qwen3.8-max son *larger model*; glm5.3-flash y
qwen3.8-flash son fracción; gemma4 y qwen3.6 son *unmetered*.

## Regla central

**Un VLM no mide layout, juzga estética.** En un film oscuro por diseño (64% de píxeles
casi negros) los modelos reportan "pantalla negra" sobre frames con contenido y afirman
solapes de texto que no existen. Todo claim espacial se verifica contra el píxel antes de
actuar.

## Escalera

1. `scripts/qa_gate.py` — 0 tokens: luminancia, stddev y bordes por segundo; marca VACIO
   con `std < 9` y `mean < 13`; exit 1 si hay vacíos no justificados (`--allow`).
2. Manifiesto de layout del motor de render — 0 tokens: bbox de cada texto → márgenes,
   solapes por intersección, contraste WCAG. Convierte el QA visual en test unitario.
3. VLM — 1 pasada, `glm5.3-flash` por defecto, solo juicio (ritmo, jerarquía, acabado).
4. `qwen3.8-max` — árbitro, solo si dos pasadas discrepan en algo que cambia una decisión.

## Cuántas pasadas

- 2 por corte (previa al encode final + confirmación); 3 si cambió más del 30% de frames.
- Nunca re-preguntar sin cambio real: si el hash del MP4 no cambió, no se lanza pasada.
- 2 pasadas de glm5.3-flash ≈ 34k tokens; un ciclo de qwen3.8-max cuesta como 12 del flash.

## Input nativo del VLM

El mp4 se puede pasar directo como input del modelo (glm5.3-flash lo acepta nativo y lo ve
entero, como lo vería un humano — verificado con corrida real sobre un film de 69 s): no hace
falta extraer frames ni armar manifiesto cuando el juicio es holístico (vacíos, colisiones,
ritmo). El manifiesto de layout del motor de render sigue siendo la fuente para claims
espaciales exactos; el input nativo complementa, no reemplaza, la escalera.

## El juez VLM no es determinista ni siquiera a temperature 0

Mismo mp4, mismo guion, temperature 0, varias corridas: una marcó solapes de subtítulos que
otra no vio, y otra devolvió `blocking: []` con score 8 mientras sus propias secciones de
evidencia listaban colisiones en 5 timestamps distintos. Reglas duras para cualquier juez LLM:

- La decisión se calcula sobre la evidencia declarada (voids, colisiones, legibilidad),
  nunca sobre el flag `passed` ni sobre la lista `blocking` sola: el modelo deja secciones
  bloqueantes vacías y pone el hallazgo en otra parte del veredicto.
- Contrato completo o veredicto inválido: si falta cualquier clave del contrato, se descarta
  la pasada y se reintenta dentro del presupuesto; fallar cerrado, jamás interpretar un JSON
  parcial como aprobación.
- La salida se trunca a media frase incluso por debajo de `max_tokens`: registra
  `finish_reason` y el largo del contenido de cada pasada inválida en el reporte, o el
  diagnóstico será imposible.
- La clave de cache incluye TODO parámetro que cambia el comportamiento (`--max-passes`,
  versión del contrato): una corrida obtenida con 1 pasada no puede servir a quien pidió 2.

## Catálogo de defectos ya mecanizados

- alpha de helpers canvas se multiplica (`a * ctx.globalAlpha`), nunca se reemplaza.
- fade a negro entre escenas = voz sobre nada; mantener el elemento saliente.
- dos textos en la misma base a menos de 40 px colisionan; separación mínima 44 px.
- etiquetas bajo `rgba(244,241,234,0.55)` sobre `#07080B` no se leen en móvil.
- el highlight de una tarjeta arranca antes de la palabra que lo anuncia (cue − 0.45 s).
