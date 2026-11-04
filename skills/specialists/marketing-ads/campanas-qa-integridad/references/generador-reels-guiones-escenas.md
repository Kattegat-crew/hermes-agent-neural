# Inventario: generador de campañas (guiones + escenas) — ago/sep 2026

Levantado el 2026-09-11 para la tarea de automatizar guiones y escenas (keyframes generados con GPT)
para **Golden Game** y **The Grand Paradise / Lucky Brothers**.

## Repo (corazón del pipeline)

- `/host/root/marketing-campaign-generator/` — en el contenedor; es **el mismo árbol** que
  `/root/marketing-campaign-generator/` (mismo inodo: `/opt/data` == `/host/root/hermes-agent-legacy-docker/data`).
- Git: `git@github.com:Kattegat-crew/marketing-campaign-generator.git`, rama `main`.
- Flujo: guion → imagen → video vertical 9:16 → voz con lip-sync → análisis por plataforma. Tests en `tests/`.

## Servicio (host)

- `reel-worker.service` (systemd) → `scripts/reel_worker.py`, puerto **:8090**, `GET /health` → `{"status":"ok"}`.
- Auth JWT: `REEL_WORKER_JWT_SECRET` en `.env` + `scripts/make_worker_token.py`.
- Flows ActivePieces (`ap-db` PROD, medido 12-sep-2026): existen y están **ENABLED**, pero el orquestador **NO funciona** —
  `reel-orchestrator` 6 OK / **15 FAILED** (las últimas fallan en `step_post_jobs`, el POST al worker); `reel-callback` sin
  correr desde el 16-ago; `video-generator` (zombi, ya cubierto por el motor del repo) sigue ENABLED. Lección: "ENABLED"
  no es "funciona" — hay que mirar `flow_run`.
- `reel-worker.service` apunta a `/root/marketing-campaign-generator` (`WorkingDirectory` y binario python de su `.venv`). La ruta está normalizada en el host, active y responde `{"status":"ok"}` en `/health`.

## Guiones (dónde viven)

- Serie septiembre: `plans/GUION-G1..G4` (Golden: Agua de Dios, Tunja, El Carmen, Pacho) y
  `plans/GUION-L0` / `GUION-L1-CHIQUINQUIRA` (Paradise) en `/opt/data/plans/`.
- Arquitectura de la serie: `/opt/data/plans/SERIE-LUCKY-GRAN-BINGO-PARADISE.md` (nombre del evento, sedes, motor visual, constantes T&C v6).
- Guion fuente Goldie: `assets/golden/Guion reel goldie.md` (inmutable) + `docs/goldie-akari-reel-plan.md`.
- Skills: `creative/guion-video-campana`, `creative/video-reel-pipeline` (+ `references/lucky-reel-guion-v2.md`), `bragi/skills/guiones/neuralcrew-guion-series-ops`.

## Escenas (keyframes "con GPT") y animación

- Imágenes de entrada: `assets/golden/Scene 1..4.png`, `scene 2.png`, `goldie-bingo/s2..s6/`;
  `assets/lucky/scene-01..05.jpg`, `scene-01/{v1,v2,v3,v6}`, `scene-s2a|s2b|s2c`, `scene-4.png`.
- Contrato por escena: `contracts/scene-plan.schema.json` (crop 9:16 con `crop_box_pixels`, `source_sha256`/`output_sha256`, `corrections`) — ejemplos reales en `planning/golden/goldie-reel-v01.json` y `goldie-reel-v04-direct.json`.
- **El keyframe lo genera hoy un humano en GPT/ChatGPT** y entra al repo como PNG/JPG (CHANGELOG 05-sep:
  "el usuario regeneró la imagen con GPT como cartoon 3D → `scene-2-v2.png`"). Helper existente para leer un
  share de ChatGPT: `/opt/data/scripts/dump_gptshare.sh` (Chromium headless → dump del DOM).
- Generación propia disponible: `scripts/nan_client.py` (flux-2-klein, NaN Builders `/images/generations` y `/images/edits`), `scripts/fal-client.py` (+ gates `.fal-gate.json` / `.monid-gate.json`), `scripts/image_refiner.py` (refinado local gratis, PIL/ffmpeg).
- Animación: `run_scenes.py`, `run_scene1.py`, `batch_golden_bingo.py`, `batch_lucky_bingo.py`, `run_pacho*.py` → Monid **Seedance 2.0 Mini** (`first_frame` + DIALOGUE fonético + `generate_audio`; tope de duración 15 s ⇒ partir la escena). Lip-sync alterno: `lipsync_batch.py`. Draft gratis: `draft_renderer.py` (Three.js).
- Motor + QA: `reel_engine.py` (imagen→TTS→video→mix→auditoría→previews→concat 1080x1920), `auto_auditor.py` (LUFS/VAD/OCR), `fit_voice.py`, `elevenlabs_client.py` / `edge_tts_client.py`, `assets/sheets/registry.json` (sheets `locked` por marca + `voice_id`).

## Salida / publicación

- PROD host: `/var/www/golden-webproxy/reels/` → `golden-game/campañas/septiembre-2026/`,
  `lucky-brothers/campañas/septiembre-2026/`, y el reel activo de Paradise `reels/lucky/reel2-chiquinquira/` con `escenas/`, `overlays/` (contador, balota53, logo Paradise), `voces/`, `clips/`, `index.html`.
- Previews versionados por job en `va/` y `reels/<hash>/`. Scripts: `publish-review.sh`, `build-review-page.py`, `output_layout.py`.
- Drive clientes: `Marketing Golden/Campañas/bingo-millonario-sep2026/` y `Marketing Lucky/Campañas/...` (IDs en `brain/folder-maps/bingo-millonario-campanas.md`).

## Automatización ya viva

- Crons raíz: `content-intel-daily` (6:00), `calendario-paquete-diario` (7:30), `calendario-publicacion-horaria` (60 min),
  `calendario-metricas-diario` / `calendario-metricas-tarde`, `calendario-informe-campana` → `scripts/calendario_*.sh` +
  `planning/calendario-sep2026/` (fuente: `calendario.jsonl` + `Calendario_BingoSep2026_Golden_Lucky.xlsx`).
- Content-intel: `content-intel/{pipeline,campaign_report,content_harvest}.py` + dashboards por marca.

## Brechas abiertas (insumo para automatizar)

1. ~~**El paso "guion → prompts de escena → imágenes GPT" es manual.**~~ **Resuelto (WU-12, 11-sep-2026), verificado
   12-sep:** el puente guion → brief ya existe — `scripts/guion_lint.py` (mide la locución real con edge-tts, gratis;
   valida estructura, los 7 beats del spine, pie legal **en pantalla**, fechas explícitas y vocabulario vetado; perfiles
   `serie` y `meta-ad`) + `scripts/scene_plan.py` → `brief.json` (`approved_to_spend=false`, `max_cost_usd=0`, una ficha
   por escena con `prompt_image` + `sheet_ref` + `sha256` del guion). Lo que sigue abierto es el **primer run LIVE**
   (imagen/video pagados): el gate está CERRADO y la rama live nunca se ha ejecutado.
2. Regla anti-drift vigente: sheets en `status=locked` + bloque `CHARACTER` textual idéntico en cada prompt (evita que el personaje mude).
3. Personajes humanos en keyframe deben ser claramente cartoon 3D: un keyframe fotorrealista hace que la moderación del video rechace la escena.
4. Protocolo de repos vivos: `git status` + `git pull` en el árbol físico del host antes de proponer/aplicar cambios; este repo ya vive en el host, no clonar otra copia.

## Documentos que describen el pipeline (y su estado por eslabón)

- `docs/arquitectura/GENERADOR-CAMPANAS-PIPELINE.md` — el flujo de 9 pasos en palabras llanas + la infografía
  entregada (`docs/arquitectura/assets/generador-campanas-infografia.{png,html}`) + "Estado al 11-sep-2026".
- `docs/planes/PLAN-SEMIAUTOMATICO-2026-09-11.md` — §11 lo que queda FUERA, §12 bitácora preparado vs observado,
  §13 revisión independiente (los hallazgos y bugs reales). Es la fuente más honesta del repo.
- `docs/decisions/2026-09-11-reels-cortos-conversion.md` — los dos perfiles de pieza (`serie` vs `meta-ad`).

**Cómo verificar cualquiera de esas afirmaciones (sondas, no lectura):** `references/verificar-generador-campanas.md`.
