---
name: guion-reel-lint-brief
description: "Use when writing reel scripts that must pass lint"
tags: [guiones, reel, lint, brief, edge-tts, campana, video, qa]
---

# Guiones de reel contra el pipeline lint → brief

Clase de tarea: escribir o refinar un guion de reel que **no se produce hasta
que el protocolo del repo lo valida**. El guion markdown es la fuente de todo:
`scripts/guion_lint.py` mide la locución REAL con edge-tts (gratis) y
`scripts/scene_plan.py` lo convierte en el `brief.json` del motor. Esta skill es
la capa MÁQUINA del oficio (ventanas, espina, contratos, gate).

La capa VOZ/COMPLIANCE/cliente de la misma campaña vive en skills user-owned
(`campaign-script-revision`, `neuralcrew-campaign-content`,
`neuralcrew-guion-series-ops`): leerlas para tono, vetos y constantes T&C, pero
**no** escribirlas (no son curator-managed).

## When to Use

- Reescribir un guion cuyo lint sale con errores de ventana (piezas que declaran
  60s y miden 100s+ de voz).
- Escribir una pieza nueva de la serie Golden/Lucky en el repo
  `marketing-campaign-generator` (`data/plans/GUION-*.md`).
- Encadenar guion → `brief.json` → dry-run del motor sin gastar un peso.
- No aplica a posters, stories o copy de WhatsApp (no pasan por este linter).

## Prerequisites

- Repo: `/root/marketing-campaign-generator` (su `.venv`
  ya trae `edge-tts`; `ffprobe` está en PATH).
- Maestros en `/root/hermes-agent-legacy-docker/data/plans/GUION-*.md`; los briefs se dejan
  al lado del maestro. La versión anterior **no se borra** (es el control de calidad).
- Si el pre-flight `git status` falla por *dubious ownership*:
  `git config --global --add safe.directory <ruta>`.

## How to Run

```bash
cd /root/marketing-campaign-generator
.venv/bin/python scripts/guion_lint.py <guion.md>            # 0 ok · 1 errores · 2 ilegible
.venv/bin/python scripts/guion_lint.py <guion.md> --json --out /tmp/lint.json
.venv/bin/python scripts/scene_plan.py <guion.md> --out <brief>.json \
    --brand golden --product "Bingo Millonario"
.venv/bin/python scripts/reel_engine.py --brief <brief>.json --dry-run --base /tmp/<job>
```

Medición de candidatos ANTES de fijar ventanas (lo que hace rápida la iteración):

```bash
.venv/bin/python <skill_dir>/scripts/medir_narraciones.py cand.json   # {"s1": "texto", ...}
```

## Quick Reference

| Hecho medido (11-sep-2026, `es-CO-GonzaloNeural` +0%) | Valor |
|---|---|
| Ritmo de locución (relato corrido) | 2,43–3,03 pal/s (media útil **2,7**; pre-flight: palabras ÷ 2,7) |
| Ritmo con registro exclamativo o cifras leídas | **2,0–2,5 pal/s** (CTA con fechas + dirección 2,28; rótulo de montos 2,02) → presupuestar con 2,3 y **medir**, no estimar |
| Mismo texto, otra sintaxis | hasta **±15%** de duración (mismas 34 palabras: 16,8s vs 14,9s según dónde caer la dirección) → medir 2 variantes antes de recortar |
| Determinismo de edge-tts | idéntico al centésimo en 3 corridas → 0,5s de margen por escena es seguro |
| Umbral aviso | voz > ventana; voz < 55% de la ventana ("aire muerto") |
| Umbral error | voz > ventana + 0,75s |
| `scene_plan.py` | rechaza el brief con **cualquier** aviso (salvo `--allow-warn`) |
| Pieza de 60s | ~154 palabras de voz = 57,1s de voz + 2,9s de aire (4,8%) |

## Procedure

1. **Tabla primero, prosa al final.** Ventanas enteras, contiguas desde 0, ≥4s
   cada una, sumando exactamente el total declarado (si no cuadra, el linter avisa).
2. **Medir candidatos con `scripts/medir_narraciones.py`** y elegir la ventana
   como el entero ≥ voz medida. Recortar el texto, no estirar la ventana, cuando
   una escena no cabe.
2b. **Si el cliente reescribe la voz, injertar — no reescribir.** Conservar su
   registro literal y meter las constantes de cumplimiento (fechas, mecánica,
   cifras, calificador legal del "gratis", dirección, pie legal) en los segundos
   libres que midió el linter. Chequeo de encaje ANTES de tocar texto:
   `ceil(voz)` por escena debe sumar ≤ total; si suma más (p. ej. 11+6+27+17 = 61
   en una pieza de 60s, medido en G2 v4), recortar 2–4 palabras de las líneas de
   menor valor — **nunca** un item de cumplimiento. Reportar al cliente las
   palabras exactas que se cayeron y que son reversibles a cambio de alargar la pieza.
3. **Declarar la espina** `## Spine (7 beats)` en orden canónico, con las escenas
   que cubre cada beat (toda escena en ≥1 beat; el solape entre beats es legal).
4. **Diseñar los beats contra el test de producto-necesario:**
   `descubrimiento` DEBE contener un token del producto; `trigger`, `problema` y
   `payoff` NO pueden contener el producto en crudo. Ahí es donde se arregla el
   fallo clásico (el `payoff` que repite el producto que ya nombró el mecanismo).
5. **Rótulos y cumplimiento:** el pie legal (`+18` + `Coljuegos`) debe estar en el
   texto EN PANTALLA de alguna escena — las notas internas no cuentan. Fechas
   explícitas siempre; "todos los viernes" es error duro.
6. **Lintar hasta 0 y 0:** `guion_lint.py` → exit 0 con 0 errores **y 0 avisos**.
   Pegar en el archivo la tabla `voz medida vs. ventana` que imprime el linter.
7. **Encadenar el brief:** `scene_plan.py` con `--brand`/`--product` explícitos →
   válido contra `contracts/brief.schema.json`, `spine_origen=declarado`,
   `approved_to_spend=false`, `max_cost_usd=0`. Verificar el binding
   `source.guion_sha256` contra el sha256 del guion.
8. **Cerrar E2E gratis** (opcional pero recomendado): `reel_engine.py --dry-run`
   → 4/4 escenas, `total_cost 0.0`. El gasto real lo firma un humano en la etapa 5.
9. **Entregar el archivo .md completo** (header con changelog citado, espina,
   ficha del pueblo con fuentes, tabla escena/visual/narración/rótulos, locución
   seguida para TTS, regla de animación, notas de producción, checklist) y reportar
   la ruta absoluta en texto plano: **en la TUI el tag `MEDIA:` no se intercepta**.
   El resumen del chat nunca sustituye al archivo, y lo que no se midió se dice
   como no verificado (p. ej. un recorte a 30s sin lintear).
   Si el cliente trabaja en Sheets/Docs, generar además un **CSV espejo** del guion
   ya parseado (`csv.writer`, delimitador `;`, `QUOTE_ALL`, `utf-8-sig`) para que su
   tabla y la tuya no se separen: la fuente sigue siendo el `.md`, el CSV es de lectura.

## Pitfalls

- **`**Pieza:**` debe ser un slug** si el guion declara la espina: el linter arma
  `spine_id` con el valor CRUDO (`header['pieza'][:40]`) y
  `contracts/sales-spine.schema.json` exige `^[a-z0-9][a-z0-9._-]*$`. Con la ficha
  que manda la plantilla ("Reel 9:16 · 60s · voz del local") el lint da **2 errores
  y exit 1**. Usar `**Pieza:** g2-tunja-centro-60s-reel-9-16` + la ficha humana en
  `**Formato:**`, y reportar el defecto (la suite no lo caza).
- **El pie legal con `\|` cuenta como celdas de más:** `parse_scenes` parte por todo
  `|`, la fila da 5 celdas y emite aviso "celdas con '|' sin escapar", que bloquea
  `scene_plan.py`. En la tabla usar `·` (contenido legal idéntico) — el arreglo de
  fondo es del parser, no del guion: reportarlo, no parchear el linter compartido
  en medio de un encargo de guion.
- **Ventanas enteras** si hay bloque `## NARRACIÓN COPIABLE`: sus líneas
  (`> **0-11:** "…"`) solo casan con rangos de dígitos enteros; con decimales el
  bloque se ignora en silencio y la narración medida deja de ser la del guion.
- **El bloque copiable manda sobre la tabla:** si divergen, el linter mide el
  bloque. Mantener ambos idénticos o no declarar el bloque.
- **`--brand` explícito** cuando el texto menciona las dos marcas (Golden y Lucky):
  `scene_plan` aborta con `BrandError` si el guion menciona dos marcas del registro.
- **La marca necesita un sheet de personaje `locked`** en
  `assets/sheets/registry.json` o `scene_plan` se niega (los prompts saldrían sin
  referencia canónica de personaje).
- **No leer el `verdict: review` del dry-run como defecto del guion:** los clips
  placeholder de 20s frente a los 5s esperados y el OCR saltado por falta de
  `tesseract` son artefactos de la simulación. Mirar `format`/`audio`/`vision`
  antes de reportar un problema de contenido.
- **Una corrida del linter puede submedir una escena:** scene-04 de G2 v4 salió
  **11,04s** donde el texto mide **14,90s** (confirmado 4×: medición suelta + 3
  corridas del linter). Si un valor del linter se desvía mucho de tu medición
  suelta, **re-correr el lint antes de recortar texto o estrechar ventana**: la
  submedición silenciosa deja pasar una escena que se pasa de su ventana. Dejar en
  el archivo el número medido con la nota "medido en 3 corridas".
- **No escribir promesas que los T&C no autorizan:** el registro del cliente puede
  traer frases de valor ("el viernes con amigos va por nuestra cuenta") que la casa
  no ha autorizado. Sacarlas del guion, decir dónde queda el hueco medido y dejarlas
  pendientes de decisión del cliente — no "suavizarlas" ni dejarlas pasar por estilo.

## Verification

- `guion_lint.py <master>` → **exit 0, 0 errores, 0 avisos**, con la voz medida
  impresa y copiada al archivo.
- Brief en disco revalidado de forma independiente contra `brief.schema.json` **y**
  `sales-spine.schema.json`, cobertura completa de escenas y test
  producto-necesario `pass`.
- `approved_to_spend=false` y `max_cost_usd=0` (el planner nunca firma gasto).
- `source.guion_sha256` == sha256 del guion.
- Detalle de las dos reproducciones de defectos, checklist de autoría y tabla
  antes/después de G2 en `references/guion-lint-brief-pipeline.md`.
