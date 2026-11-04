---
name: guion-validacion-y-brief
description: "Use when validating a reel guion before production."
tags: [guion, reel, lint, edge-tts, brief, marketing, gate]
version: 1.0.0
author: Ragnar
metadata:
  hermes:
    tags: [guion, reel, lint, brief, marketing-campaign-generator, edge-tts, spine, gate]
    category: creative
    related_skills: [guion-video-campana, marketing-campaign-pipeline, reel-portal-protocol]
---

# Validar un guion de reel y convertirlo en brief (antes de producir)

El guion dejó de ser prosa que se aprueba a ojo. En el repo `marketing-campaign-generator` hay contrato, plantilla, linter y planner, y el linter **mide la locución real** (edge-tts, costo $0) antes de que se gaste un peso en imagen o clip.

## When to Use

- Llega un guion de campaña (propio, del cliente, o dentro de un .docx/informe) y hay que decir «cómo está» y refinarlo.
- Antes de generar keyframes, clips o locución: el guion tiene que estar lint-clean.
- Hay que convertir un guion en el `brief.json` que come el motor (`reel_engine.py`).
- Alguien afirma una duración (60s, 30s) y hay que comprobarla.

## Herramientas (repo `marketing-campaign-generator`)

| Pieza | Ruta en el repo |
|---|---|
| Contrato del guion | `contracts/guion.schema.json` |
| Contrato del brief | `contracts/brief.schema.json` |
| Plantilla obligatoria | `templates/guion-reel.md` |
| Linter (estructura + espina + **VOZ REAL** + cumplimiento) | `scripts/guion_lint.py` |
| Planner guion → `brief.json` | `scripts/scene_plan.py` |
| Test producto-necesario | `scripts/sales_spine.py` |
| Tests | `tests/test_guion_lint.py`, `tests/test_scene_plan.py` |

```bash
cd <repo> && setpriv --reuid=hermes --regid=10000 --clear-groups \
  env HOME=/tmp/hermes-home TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 \
  .venv/bin/python scripts/guion_lint.py <guion.md> --json --out /tmp/informe.json
```

Correr SIEMPRE como usuario `hermes`: como root deja `__pycache__` root-owned dentro del repo y rompe el reclamo de «0 archivos ajenos» (y puede bloquear al worker). El guion se cierra con el informe en **`ok: true`**, no con la lectura a ojo. `--no-voice` existe para modo offline, pero entonces no se está midiendo nada.

## Qué EXIGE el linter (error, no aviso)

1. Ventanas de tiempo contiguas que cubran el total declarado, sin huecos ni solapes.
2. La narración debe **caber** en su ventana: la sintetiza con edge-tts y si sobra más de `--tolerance-s` (0,75s por defecto) falla **diciendo cuántos segundos sobran**.
3. Tabla `## Spine (7 beats)` **declarada y completa**. Si falta, el linter la DERIVA de la estructura de la serie y avisa «requiere confirmación humana» — y es justo ahí donde pasa invisible el defecto de una escena comiéndose 4 beats.
4. Pie legal `+18` + `Coljuegos` en el texto **EN PANTALLA** de alguna escena (no basta con que esté en la narración).
5. Fechas explícitas (nunca «todos los viernes») y vocabulario vetado fuera del texto que sale al aire.
6. Test producto-necesario (`sales_spine`): el `payoff` no debe volver a nombrar el producto crudo después del borrado, y el `descubrimiento` debe mencionar un token del producto.

## La regla de oro: medir antes de producir

Un guion puede declarar 60s y tener 105s de locución escrita. Mientras la duración real no se decida, todo lo que se produzca encima (keyframes, clips, montaje, slots) se produce mal. **Medir primero, decidir después, producir al final.**

Caso real (serie Golden sep-2026): los cuatro guiones declaran «60s con recorte a 30s» pero miden 100–105s; el «recorte» existe solo como instrucción en prosa, no como un guion de 60s.

Orden de sacrificio al recortar:
1. Frases de ambiente («el bingo es la excusa, el plan es el viernes»).
2. Contexto histórico que se puede sugerir en vez de narrar.
3. Autopreguntas/rótulos completos → **bajan a rótulo que se responde solo en pantalla** (conservan el recurso diferenciador sin costar segundos de voz).
4. Dirección del local hablada → solo en pantalla, **y solo si el cliente lo autoriza**.

**Intocable en cualquier recorte:** fechas explícitas, cifras, balota, mecánica del bingo y pie legal. Si el recorte obliga a mutilar el recurso diferenciador, la salida honesta es **producir dos piezas del mismo texto** (una corta para redes, una larga para el canal que la campaña ya declare) en vez de dejar el «recorte» como prosa.

## Cómo se analiza un guion recibido (entregable del análisis)

Cuando piden «analicen el guion, denme la tabla de diálogos y cámara y a ver cómo está»:

1. Bajar el guion fuente (si viene en .docx/link del cliente) y leerlo completo.
2. Transcribirlo a `templates/guion-reel.md` (cabecera, estructura de serie, `## Spine (7 beats)`, tabla `Tiempo|Visual|Narración|En pantalla`, narración copiable).
3. Correr el linter y quedarse con las medidas **por escena**, no solo el total.
4. Entregar: tabla de medidas (ventana vs voz real vs sobra), los defectos de estructura (escena que se come la espina, payoff pegado a la trama, espina sin declarar, pie legal fuera de pantalla) y el ajuste concreto por escena.
5. Cerrar con la decisión que le toca al humano (duración real; si la dirección hablada se cae a pantalla) y el handoff al redactor.

Nunca entregar el análisis desde el texto sin haber corrido el linter: la diferencia entre «se lee bien» y «mide 105s» es exactamente el valor del análisis.

## Pitfalls

- **Una celda con `|` sin escapar** descompone la fila: el linter avisa «se recomponen sus columnas» — revisar el pie legal cuando aparezca.
- **Dos formatos de guion siguen vivos** y el linter normaliza ambos: tabla `Tiempo|Visual|Narración|En pantalla` (Golden) y secciones `### TOMA N` (Lucky); el campo `source_format` del JSON dice cuál detectó.
- **Los maestros de la serie viven en el HOST**, no en el repo: `/root/hermes-agent-legacy-docker/data/plans/GUION-*.md` y `SERIE-*.md`. En el runtime desktop `/opt/data/plans/` es OTRO directorio (7 docs viejos, root): verificar antes de decir «no existe».
- **El guion y las escenas NO son de Roshi**: su skill lo declara así. Él aporta el gate documental/QA y su mesa pieza-por-pieza (12 etapas, las pagas exigen `candado` de presupuesto). Los dos esfuerzos son complementarios: el `guion_lint` del repo debería correr dentro de la etapa 2 (guion) de esa mesa, en vez de que cada lado tenga su linter.

## Referencias

- `references/guion-lint-y-brief.md` — receta de transcripción paso a paso, medidas reales de la serie sep-2026 por escena, y cómo bajar el guion fuente de Drive cuando el token local está revocado.
