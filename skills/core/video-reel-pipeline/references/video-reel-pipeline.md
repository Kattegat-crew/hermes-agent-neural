---
name: video-reel-pipeline
description: Use when generating AI video reels (video-ai-generator).
---

# Video Reel Pipeline (video-ai-generator)

## Cuándo usar
- Generar reels verticales 9:16 (30s) para clientes de NeuralCrew (Golden Game, Lucky Brothers/The Grand Paradise Club, futuros).
- Retomar un reel a medio hacer: SIEMPRE verificar qué existe en el repo antes de regenerar o de afirmar "ya tenemos X".

## Acceso al repo
- Repo host: `/root/marketing-campaign-generator` (accesible dentro del contenedor Hermes en `/host/root/marketing-campaign-generator`).
- Repo GitHub: `Kattegat-crew/marketing-campaign-generator`. **Rama canónica: `main`**. Si tenés un clone local, `git fetch origin && git checkout main && git pull`.
- Worker HTTP: `http://localhost:8090/health` → `{"status":"ok"}` (systemd `reel-worker.service`). `/` responde 404 "ruta no encontrada" (normal).
- Keys (host, no commitear): `NAN_API_KEY` (flux), `MONID_API_KEY`, `TOKENROUTER_API_KEY` en `/repo/.env`; además migradas a `~/.config/akari-video/credentials.env` (chmod 600, fuente del doctor de AKARI). Nunca imprimir valores.

## Pipeline de 3 capas
1. **Draft rústico (GRATIS)**: `scripts/draft_renderer.py` — screenshots de chromium headless cargando un HTML Three.js (three.min.js local) por frame, ensambla con ffmpeg. Scene-plan JSON (objetos box/sphere/plane, camera, background). Determinista por construcción (t = i/fps).
2. **Imágenes (flux)**: `scripts/nan_client.py` — `generate_image()` (text-to-image) y `restyle_image()` vía NaN Builders (OpenAI-compatible, https://api.nan.builders/v1). Solo stdlib, allowlist de descarga = nan.builders.
3. **Realismo (Monid)**: Seedance 2.0 Mini 720p. Imagen → video. Para lip-sync: prompt de boca hablando + `generate_audio:false`, luego mezcla con ducking.

## Script inventory
| Script | Función |
|---|---|
| `draft_renderer.py` | Draft 9:16 gratis (Three.js → ffmpeg) |
| `nan_client.py` | Imágenes flux (generate_image / restyle_image) |
| `edge-tts-voice.py` / `edge_tts_client.py` | Voz española GRATIS (`es-PE-AlexNeural`; alternativa `es-CO-SalomeNeural`) |
| `mix-narration.sh` | Mezcla narración + música con ducking (workaround `asplit=2` para ffmpeg 6.1) |
| `ffmpeg_client.py` | Ensamblado video+audio |
| `reel_engine.py` / `reel_worker.py` | Orquestación + worker HTTP :8090 |
| `auto_auditor.py` | Auditoría (ffprobe + OCR + VAD/astats/ebur128 reales desde 18/08) |
| `cleanup_previews.py` | TTL de previews/reels locales (previews 7d, finales 30d, no-aprobadas 3d; timer systemd `cleanup-previews.timer` 03:17) |
| `publish-review.sh` + `build-review-page.py` | Previews HTTPS versionados bajo `/va/` |
| `prepare-golden-assets.py` | Frames 9:16 + corrección de marca (modo `direct` OK; modo `composite` tiene bugs de scope) |
| `contract_validator.py` | Validación de contracts |

## Cambios de hoy (18/08, en `main`) — leer antes de operar
- **Costo real de Monid**: el engine ya NO estima el costo por escena cuando el cliente lo reporta. `monid-client.py --report-cost` imprime `COST_USD=<n>` y `reel_engine` lo usa en el manifest. El gate #2 (`max_cost_usd`) ahora reserva `per_scene_cost * SAFETY_FACTOR (1.5)` y, tras obtener el costo real, re-valida el límite duro con `BudgetExceededError`. No relajar nunca `approved_to_spend` ni `max_cost_usd`.
- **Checks de audio reales**: `auto_auditor` corre astats/ebur128/silencedetect (clipping, LUFS, voice_present). El audio es informativo: NO participa del verdict.
- **Cleanup TTL**: `scripts/cleanup_previews.py [--base output] [--dry-run]` + timer systemd activo. No borra directorios que no sean `v<N>`.

## Costos
| Item | Costo |
|---|---|
| Monid Seedance 2.0 Mini 720p | $0.38115/clip (~$0.38) |
| Reel 30s = 5 clips | ~$2.29 |
| Draft Three.js + voz edge-tts | $0 |

## Workflow
1. **Verificar estado real del repo**: `git log --oneline`, `git status --short`, `find planning/ assets/ .draft_scratch/` — no asumir que los artefactos de sesiones previas siguen existiendo.
2. Guion aprobado → guardar en `planning/<cliente>/<reel>-v2.json` + **commit inmediato**.
3. **Si el usuario pide el documento de guión + prompts de imagen** (con consistencia de personaje): generar el "prompt-pack" DOCX completo ANTES de tocar el pipeline — ver `references/reel-prompt-pack-character-consistency.md`. Entregar link de Drive, no adjunto.
4. Scene-plans JSON por escena → `draft_renderer.py` (12fps basta para validar timing).
5. Gates humanos por escena: aprobar preview antes de pagar Monid (`approved_to_spend` con evidencia).
6. 5 imágenes flux → 5 clips Monid → edge-tts → `mix-narration.sh` → ffmpeg.
7. Publicar previews `/va/` y verificar con ffprobe + curl 200 sobre Cloudflare en cada versión.

## Pitfalls
- **🔥 COMMIT POR FASE — la regla de oro.** `.draft_scratch/` es gitignored: lo que vive ahí se PIERDE si no se commitean los scene-plans y guiones al repo. El draft de Lucky (17/08) se perdió completo por esto — `.draft_scratch/` y `assets/lucky/` quedaron vacíos y hubo que regenerar todo. El postmortem de Golden (`docs/goldie-reel-postmortem.md`) ya lo advertía. Regla: todo scene-plan, guion y artefacto de decisión → commit en el momento.
- **Si el usuario pide "el guion que hiciste":** entregarlo YA desde session_search o el repo. No re-verificar el pipeline primero (corrección explícita del usuario 18/08).
- `assets/<cliente>/` vacío = ese reel nunca se generó/commitó.
- Kokoro vía NaN sin español (HTTP 500) → edge-tts local es la voz estándar.
- Monid: `role` dentro de `image_url` → HTTP 400; `role` va a nivel del item `content`. Descarga frágil → `find_video_url()` recursivo + sidecars `.response.json` / `.runid`.
- Monid no tiene endpoint de balance (`/credits` → 404): no es señal de error de cuenta.
- ffmpeg 6.1: label compartido sidechain+amix → `asplit=2` antes de la sidechain.

## Referencias
- `references/lucky-reel-guion-v2.md` — guion 30s de Lucky Brothers (5 escenas × 6s) recuperado de la sesión del 17/08, con notas visuales por escena.
- `references/reel-prompt-pack-character-consistency.md` — técnica para crear documentos DOCX con guión + prompts en inglés por escena, incluyendo ficha de personaje para consistencia visual, estructura del prompt, y reglas de entrega a Drive.
