# QA de video con input nativo (mp4 completo)

## Qué es y qué no
El modelo recibe el **mp4 entero** como `video_url` (data URL en base64), no una tira de frames.
Eso le permite juzgar lo que sólo existe en movimiento: si la voz y la imagen cuentan lo mismo, si
un texto se come a otro al entrar, si el ritmo se lee como film o como diapositiva narrada.

No es un ojo humano:

- Muestrea frames internamente; no ve los 30 de cada segundo. Un parpadeo de 2 frames se le escapa.
- No mide márgenes, cajas ni píxeles. Para eso: manifiesto de layout + `qa_gate.py`.
- No lee con fiabilidad texto pequeño o sobre fondo con textura. Si la legibilidad es el riesgo,
  exporta los bboxes del render y verifica geométricamente.

## Evidencia medida (film de 69 s, 11-nov)
`bench2.txt` del banco de pruebas, mismo prompt y mismo mp4:

| modelo | latencia | tokens in/out | voids | colisión |
|---|---|---|---|---|
| `glm5.3` | 12.3 s | 8696 / 193 | ~12 s y ~19 s | sí, ~4 s (tagline sobre el título) |
| `glm5.3-flash` | 9.6 s | 17031 / 91 | 0:00 y 0:22 | no |

La colisión de ~4 s existía y `glm5.3` la vio; `glm5.3-flash` la negó. Los dos discreparon en los
vacíos. Conclusión operativa: **un solo veredicto no es evidencia**. De ahí el presupuesto de
pasadas y la confirmación por severidad.

### Segunda medición, con este script (mismo film, 12-nov)
`glm5.3-flash`, 1 pasada, contrato JSON: 14.3 s · 9135 tokens in / 323 out · score 8/10 · pasa con
una advertencia `low` en 18.5 s (subtítulos superpuestos menos de un segundo). El modelo nombra
timestamps concretos (18.5, 47.5, 54, 61.5), no impresiones generales.

Gotcha medido: GLM razona antes de responder. Sin acotarlo, 3000 tokens de salida se fueron en
razonamiento y el JSON nunca llegó (`sin veredicto válido`). El script manda
`chat_template_kwargs.enable_thinking=false` + `reasoning_effort=none` y `max_tokens=1500`; si el
gateway rechaza esos campos, reintenta sin ellos y parsea también `reasoning_content`.

## Uso

```bash
python3 scripts/video_native_qa.py film.mp4 --script guion.txt --json
python3 scripts/video_native_qa.py film.mp4 --script guion.txt --cues cues.json \
        --model glm5.3-flash --max-passes 2 --pre-gate
```

Exit codes: `0` aprueba · `1` bloquea · `2` degradado (sin veredicto válido, API caída, artefacto
inválido). Un `2` nunca se interpreta como pase.

`--dry-run` arma el payload y muestra su tamaño sin llamar al modelo. `--force` ignora la cache.

## Presupuesto de pasadas
- Verde en la primera pasada: no se re-confirma (no se paga de más).
- `critical`/`high`: bloquea con una pasada, sin segunda opinión.
- `medium`: necesita aparecer en dos pasadas (ventana ±1.5 s) para bloquear; si sale una sola vez
  queda como advertencia visible.
- `--max-passes` es un techo duro: nunca hay una tercera llamada.

## Cache y recibos
`$VIDEO_QA_STATE` (default `$HERMES_HOME/video-qa`)/`receipts/<sha256>.json`. La clave cubre hash
del mp4, modelo, versión de contrato y guion: mismo corte + mismo revisor = mismo recibo, coste 0.
Reeditar el video cambia el hash y obliga a re-revisar.

## Gate determinista delante
`--pre-gate` corre `qa_gate.py` (frames vacíos por segundo, con ventanas toleradas). Si falla, no
se llama al modelo: un film con voz sobre negro no necesita un VLM para saber que está roto.

Medido sobre el mismo film: el gate determinista bloqueó con **7 segundos vacíos**
(`0, 22, 30, 31, 43, 58, 59`) coste 0, mientras el VLM lo aprobaba con 8/10. No es que uno se
equivoque: ven cosas distintas. El negro intencional (frase de apertura, cambio de acto) se declara
con `--pre-gate-allow "0,22,43"`; lo que quede fuera de esa lista es caída real.

## Cada vez menos QA
Los hallazgos que se repiten entre films se **promueven a check determinista**: si tres videos
seguidos fallan por lo mismo (caption sobre título, logo fuera de margen, cierre en negro), eso se
convierte en regla del manifiesto de layout y deja de necesitar modelo. El VLM se reserva para lo
que no se puede medir: sincronía voz/imagen y ritmo.

## Coste
Se cobra por tokens de entrada, y el video pesa: 69 s ≈ 17 k tokens de entrada en `glm5.3-flash`.
El recibo guarda `tokens.in/out` por corrida para poder auditar el gasto real; nunca se estima de
memoria.
