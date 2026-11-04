---
name: guion-reel-mesa-medida
description: "Use when writing or measuring a campaign reel script."
tags: [guiones, reels, campanas, casino, lint, edge-tts, medicion]
version: 1.0.0
metadata:
  hermes:
    tags: [guiones, reels, campanas, casino, lint, edge-tts]
    related_skills: [guiones-campana-por-canal, guion-video-campana, sesion-pieza-por-pieza]
---

# Mesa medida de guiones de reel (repo marketing-campaign-generator)

Se usa cuando Yisus pide **crear, revisar o medir un guion** de las campanas Golden / Lucky (Bingo
Millonario). El guion NO se opina: se escribe, se mide con edge-tts (gratis) y se lintá antes de
tocar cualquier API paga.

## Donde vive (fuente de verdad)

- Repo en el host: `/host/root/marketing-campaign-generator` == `dev:/root/marketing-campaign-generator`.
- Maquina de etapas: `scripts/guion_session.py` · linter: `scripts/guion_lint.py` · planner: `scripts/scene_plan.py`.
- Una sesion por pieza: `sessions/<pieza>/` con `sesion.json`, `00-datos.md`, `01-concepto.md`,
  `02-guion.md`, `02-guion-lint.json`, `REFS.md`, `bitacora.md`.
- Datos duros del T&C v6: `data/datos-duros.yaml` (nada se inventa: cifras, fechas, regla de la balota 53).
- Pre-flight obligatorio: `git status` + `git pull` antes de escribir nada.

## Ritual (lo que funciona)

1. **Escribir en el host, no en el contenedor.** `/host/root` no es escribible localmente (Permission
   denied): se escribe el archivo en `/host/tmp/<algo>` y se copia con
   `ssh -o BatchMode=yes dev 'cp /tmp/<algo> /root/marketing-campaign-generator/sessions/<pieza>/<destino>'`.
2. **Medir ANTES de fijar ventanas:** sintetizar con `edge_tts` (voz `es-CO-GonzaloNeural`, rate `+0%`)
   y leer la duracion real con ffprobe. Las ventanas se calculan sobre esas medidas (holgura <=0,75 s
   por escena), nunca sobre la regla de 2,6-2,8 pal/s.
3. **Lint de verdad** (gratis, no gasta): `ssh dev 'cd /root/marketing-campaign-generator &&
   .venv/bin/python scripts/guion_session.py lint <pieza> --perfil serie'`. Objetivo: 0 errores y
   0 avisos. `--perfil serie` exige el pie legal EN PANTALLA; `--perfil meta-ad` veta cifras y azar.
4. **Bitacora y commit** (`git -c user.name=Roshi ...`) — la bitacora es la materia prima del reporte.
5. **Ninguna etapa pagada (5 keyframes, 8 clips, 9 audio) se ejecuta sin candado firmado por Yisus.**

## Reglas del linter que rompen a quien escribe

- `**Pieza:**` = **slug** (`^[a-z0-9][a-z0-9._-]*$`, es el `spine_id`); la ficha (formato, segundos,
  voz) va en `**Formato:**`. El scaffold lo hace solo desde el 12-sep-2026.
- Celdas de tabla: **sin `|`** dentro del texto (rompe la tabla y bloquea `scene_plan`); usar `·`.
  Aplica al pie legal: `+18 Juego responsable · Regulado por Coljuegos`.
- Ventanas de tiempo contiguas, sin huecos ni solapes; escena minima 4 s.
- `## Spine (7 beats)` con los 7 beats canonicos en orden (trigger, problema, descubrimiento,
  mecanismo, producto, payoff, cta) y TODAS las escenas mapeadas; `descubrimiento` debe nombrar el
  producto, y `trigger`/`problema`/`payoff` NO pueden nombrarlo crudo.
- Bloques `> **0-9:** "texto"` en NARRACION COPIABLE deben usar exactamente los enteros de la ventana.
- Vocabulario vetado (se lee de la linea `Vocabulario vetado:` del propio guion): bote, escalonado,
  uno tras otro, dos bingos, premio de consolacion, carton gratis, pana, todos los viernes.
- Fechas siempre explicitas. Nunca "todos los viernes".

## Calibracion medida (12-sep-2026)

`es-CO-GonzaloNeural` a `+0%` habla a **2,8-3,1 pal/s** (mas rapido que la regla de la serie), y los
maestros G2/G4 declaran 60 s pero miden 100-105 s. Pieza bien dimensionada =
`sessions/golden-0914-reel-nuevo`: 4 escenas, ventanas 9/11/32/13 = 65 s, voz medida 63,02 s, lint 0/0.

## Trampas vistas

- El calendario manda: `planning/calendario-sep2026/calendario.jsonl` dice que sede promociona cada
  reel; los posts del dia antes del bingo confirman la jornada (ej. post del 17-sep = "CARMEN" para el
  viernes 18 → el reel del lunes 14 es El Carmen; Tunja queda para el reel del 21).
- Los copys ya publicados pueden traer la mecanica VIEJA ("dos bingos por noche"); el guion se escribe
  contra el T&C v6 y el choque se reporta como decision del cliente, no se "arregla" por encima.
- Los guiones de `plans/` son referencia de registro y tono, jamas se sobrescriben.
