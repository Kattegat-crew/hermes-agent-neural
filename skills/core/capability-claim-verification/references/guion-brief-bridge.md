# Puente guión → brief.json (caso marketing-campaign-generator, 11-sep-2026)

El eslabón que convierte una campaña en algo semiautomático: el guión aprobado entra, el `brief.json` que come el motor sale. Sin esto la generación es copy-paste manual.

## 1. Los DOS formatos de guión vivos (no hay que reescribir los aprobados)

El repo tenía dos formatos en producción y nadie lo había notado:

- **Formato A — «escena por escena»** (serie Golden): sección `## GUION — ESCENA POR ESCENA` con tabla de 4 columnas `| Tiempo | Visual | Narración | En pantalla |` y filas tipo `| 0-12s | … | "texto" | rótulos |`; más `## NARRACIÓN COPIABLE` con bloques `> **00-12:** "…"` (ese bloque **manda** sobre la tabla: es el texto de locución).
- **Formato B — «tomas»** (serie Lucky): secciones `### TOMA N — "título"` con tabla de 2 columnas `| Campo | Contenido |` y campos `Entorno (fijo)`, `Acción`, `Personajes (≤2)`, `Narración (Lucky, a cámara)`, `Texto en pantalla`, `Duración` (`~6s`). Aquí **la duración viene explícita por toma** y el total es la suma.

Detección en código: si existe `^##\s*GUION` → formato A; si no, `### TOMA N` → formato B. Normalizar ambos a un modelo único (`name`, `start_s`, `end_s`, `duration_seconds`, `visual`, `narration`, `on_screen_text`) evita tocar guiones ya aprobados.

## 2. Mapeo estructura-de-serie ↔ 7 beats canónicos

La serie publicada está escrita como pasos, no como beats. El mapeo que se validó (declarado explícitamente en el linter, revisable):

| paso de la serie | beats |
|---|---|
| ① dato curioso del pueblo | `trigger` |
| ② conexión con la suerte/la amistad | `problema` |
| ③ dinámica del bingo (con premio temprano) | `descubrimiento`, `mecanismo`, `producto`, `payoff` |
| ④ CTA + legal | `cta` |

Reglas que evitó errores reales:
- **Un beat nunca puede quedarse sin escenas** (el contrato exige `scene_names` con ≥1 item). Con menos escenas que beats, el reparto proporcional deja el último beat vacío: haz *backfill* desde el paso no vacío más cercano. El solapamiento entre beats es legal (un clip puede disparar `trigger` y `problema`).
- **Spine derivado ≠ spine del autor.** Si el guión no declara su tabla `## Spine (7 beats)`, el linter deriva uno y lo marca `DERIVADO`: en ese caso el test de producto-necesario se reporta como **aviso**, no como error — no puedes reprobar un test en nombre del autor con una espina que inventaste tú.
- El `product` del spine sale del campo `**Campaña:**`/`**Producto:**` (primer segmento antes de `·`), **nunca** del campo `**Pieza:**`: ese trae la ficha técnica completa («Reel 9:16 · 60s (con recorte…)») y como producto hace fallar el test de producto-necesario con tokens absurdos.

## 3. Reglas de validación que hacen útil el linter

- **Voz medida, no estimada**: `edge_tts.Communicate(texto, voz).save(mp3)` + `ffprobe -show_entries format=duration` por escena → comparar con la ventana. Tolerancia 0,75 s (por debajo = aviso «ajustable acelerando la voz ~X%»); por encima = error con los segundos de exceso. Medido el 11-sep-2026: **G2 Tunja declara 60 s y mide 105,2 s** (16,2·11,5·56,1·21,3); **L1 Chiquinquirá declara 38 s y mide 40,0 s**.
- **El cumplimiento se aplica al texto que SALE AL AIRE** (narración + rótulos), jamás a las notas: un guión que cita «fechas explícitas, nunca "todos los viernes"» en sus notas no puede fallar por esa frase. Igual con el vocabulario vetado.
- **Estructura**: ventanas contiguas que cubran el total (huecos y solapes = error), mínimo de escena configurable, y contraste del total con los segundos que declare la ficha de pieza.
- **Contrato propio del guión** (`contracts/guion.schema.json`) con `source_format` (`escena-por-escena` | `tomas`) y `narration_source` (`tabla` | `narracion-copiable` | `toma`): así el planner no depende del formato de escritura.

## 4. Contrato del brief que el planner emite (fail-safe)

Campos que el motor consume de verdad (ojo: `voice_line` y `duration_seconds`, no `narration`/`duration_s`): `job_id`, `project`, `approved_to_spend`, `max_cost_usd`, `scenes[]` (`name`, `voice_line`, `duration_seconds`, `prompt_image`, `on_screen_text`), `spine`, `budget`, `delivery`.

- `approved_to_spend: false` y `max_cost_usd: 0` **por defecto**: el planner nunca abre el gasto.
- `job_id` se deriva del **título** (`g2-tunja`), no de `**Pieza:**`; el `project` es marca+pieza (`golden-g2-tunja`).
- Marca, voz y sheet se resuelven del registro del repo (`assets/sheets/registry.json`: `brands.<marca>.{voice_id,voice_name,sheets[]}`), no se hardcodean: así cambiar la voz de una marca (p. ej. reemplazar la de Lucky) se hace en un sitio.
- El `prompt_image` sale del campo **Visual** del guión con la referencia del sheet canónico delante (`[sheet:goldie-character] …`): trazable y revisable, sin prompt inventado por el modelo.

## 5. Cómo se mide la unidad de trabajo (E2E real, $0)

```bash
# 1) guión → brief (se niega si el lint tiene errores)
python3 scripts/scene_plan.py /tmp/GUION-G2-TUNJA.md --out /tmp/brief.json --skip-lint
# 2) motor en dry-run (sin gate, sin gasto): manifest con N/N escenas + reel.mp4
python3 scripts/reel_engine.py --brief /tmp/brief.json --base /tmp/e2e-out
# 3) el MISMO brief por el servicio (el worker corre el código del repo)
#    body = brief + {"dry_run": true}; token de scripts/make_worker_token.py
```

Resultado que cierra la unidad: `version-manifest.json` con **4/4 escenas** `dry_run`, `total_cost: 0.0`, `simulation: true` y `reel/reel.mp4` real; y por el worker, el log del engine en disco con `--- exit 0 ---` y el stdout completo.

## 6. Pitfalls vistos

- El CLI del motor debe correr en **dry-run por defecto** (`--live` explícito): el default inseguro fue justo el que produjo un POST live no autorizado el 11-sep-2026.
- Un guión con escenas **sin `edits`** mata el job si el refiner no maneja el caso ausente (`-filter_complex ""` → exit 234): el E2E tiene que incluir una escena sin `edits` a propósito.
- Los `.pyc` viejos hacen que un traceback muestre la ruta **antigua** del repo: limpia `__pycache__` antes de creerte una ruta en un error.
- Ejecuta los scripts multi-línea en DEV con `ssh dev 'cd <repo> && .venv/bin/python -' < script.py` (evita el infierno de quoting de los heredocs dentro de `ssh`); y lanza las corridas largas en background: canalizar por `tail` **buffer**iza y no ves nada hasta que termina.
