---
name: reel-preproduccion
description: Lint de guiones, brief y draft three.js previo al gasto.
version: 1.0.0
author: Ragnar
metadata:
  hermes:
    category: specialists
    tags: [reels, guiones, threejs, draft, marketing-campaign-generator]
---

# Reel Preproducción Skill

Etapa pre-gasto de la cadena de reels de campañas (casinos Golden/Lucky): lint de guiones, brief de prompts y render draft three.js de diagramación. Todo corre a $0 — existe para validar timing y layout ANTES de autorizar GPT Image (fal) o Seedance (monid). No cubre generación pagada ni publicación.

## When to Use
- Antes de pedir autorización de gasto para stills/video de un reel.
- Al integrar guiones nuevos (30s/15s por marca) al pipeline del repo.
- Al diagnosticar un draft que "renderizó" pero sale blanco o roto.

## Prerequisites
- Repo marketing-campaign-generator en DEV — resolver la ruta en vivo (candidatos /host/root primero), nunca hardcodearla; `git status`/`pull` pre-flight.
- `CHROMIUM_BIN=/opt/chrome-for-testing/chrome-linux64/chrome` (Chrome for Testing). NO el chromium snap.
- `.env` del repo cargado con `set -a; . .env; set +a` (contiene credenciales — no imprimir valores).

## Procedure
1. **Lint** los 4 guiones (30s+15s × marca) con `scripts/guion_lint.py`.
2. **Brief**: verificar que CADA marca tenga `02-guion.brief.json` (no asumir que existe); `scripts/scene_plan.py` lo emite con `approved_to_spend=false` y `max_cost_usd=0`.
3. **Bloque draft**: el brief puede no traer el bloque `draft` (spec three.js); construirlo según lo que exige `draft_renderer.py`.
4. **Render**: `draft_renderer.py --scene-plan <json> --out <mp4> --width 720 --height 1280 --fps 12` (~6-8 min) en `terminal(background=true)`.
5. **Permisos**: normalizar owner de los archivos generados (pueden quedar root:root).

## Pitfalls
- Render exitoso ≠ render correcto — el chromium snap falla con ERR_ACCESS_DENIED silencioso y captura un frame blanco sin error ruidoso. VERIFICAR el KEYFRAME con visión antes de confiar en el MP4, siempre.
- `scene_plan.py` no escribe el brief si lint devuelve avisos, salvo `--allow-warn`.
- Línea de metadata del guion — `**Pieza:**` limpia; la procedencia ("Derivado de:") en línea propia, porque el parser se traga la línea entera como spine_id.
- Pie legal del arte — va LITERAL en la columna "En pantalla" del cierre, no como nota al pie del documento.
- El beat "descubrimiento" de los cortes 15s también debe mencionar el producto (test de producto).
- `.draft_scratch/` acumula GB de frames; con load alto del host los renders se alargan.

## Verification
- `ffprobe` del MP4 — 720x1280, 12 fps, duración esperada.
- Extraer keyframe y analizarlo con visión — personajes/geometría/fondo de marca presentes, sin página de error.
- Confirmar que las narraciones de los guiones quedaron intactas (solo arte/metadata tocadas).

## References
- `references/draft-render-receta.md` — receta concreta del render y caso de diagnóstico del render blanco.
- `references/lint-casos-sep2026.md` — bitácora de casos lint resueltos.


---

## Procedencia

Absorbido por F3 el 20260923-055337 desde la autoskill `data/skills/specialists/reel-preproduccion` (sin versión en git hasta hoy).
El procedimiento se conserva íntegro; el paraguas `video-reel-pipeline` es su punto de entrada.

