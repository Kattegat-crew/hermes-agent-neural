---
name: monid-seedance-clips
description: "Use when generating image2video clips via Monid Seedance."
tags: [monid, seedance, video, image2video, reels, clips, lipsync, api]
---

# Monid Seedance — Generación de Clips Image2Video

## Cuándo usar
- Convertir frames/imágenes aprobadas en clips de video 9:16 (Seedance 2.0 Mini 720p) para reels de clientes (Lucky Brothers, Golden Game, futuros).
- Retomar una generación a medio hacer: verificar sidecars `.response.json` / `.runid` en `assets/<proyecto>/<scene>/v<N>/video/` antes de re-lanzar (un clip ya COMPLETADO NO se debe volver a pagar).
- Depurar fallos de Monid (400/504/descarga) en image2video.

## Lote paralelo con voz nativa (nuevo método, 29/08)

El método FINAL para reels con personaje: **Seedance 2.0 Mini con audio nativo + voz de marca en CapCut**.

### Receta (probada y aprobada por el Admin)
1. Generar clips con `generate_audio: true` + bloque `DIALOGUE` con respelling fonético.
2. Publicar como `clips/<S>-seedance.mp4` debajo de los mudos.
3. En CapCut: silenciar la pista nativa → superponer WAV de ElevenLabs (`voz/`).
4. La boca queda alineada porque los textos son idénticos.

### Script batch: `scripts/batch_golden_bingo.py` (29/08, Goldie — el más evolucionado)
Patrón escena-por-escena con gate de aprobación del Admin:
```bash
cd /root/marketing-campaign-generator && set -a && source .env && set +a
python3 scripts/batch_golden_bingo.py S3          # una escena a la vez
python3 scripts/batch_golden_bingo.py S3 --dry-run # valida prompt sin gastar
```
- Submit → poll → descarga → publica clip+wav en docroot de galería → `DONE` JSON por escena.
- **Extractor robusto ya parcheado**: busca `video_url` en `output`, `output.content`, y `data.output*` — un "❌ sin video_url" post-COMPLETED NO justifica re-submitir (ya está pagado); recuperar por run ID.
- **Bloque MOTION POR ESCENA** (aprendizaje clave 29/08): dejar el movimiento implícito en ACTION da clips "casi quietos" (S1 Goldie: dolly sutil). Solución: campo `motion` en el dict de escena con movimiento específico (caminata con pasos reales S2/S3; balota rueda + head-tilt S4; dedos abren→agarra→presenta S5; brazo presenta + luces pulsan S6) + default de caminata. Header `SEQUENCE SHOT. NO CUT. Single continuous take, Ns total.` + "Camera never static" mejoran notablemente el movimiento (S2→S6 vs S1).
- Costos verificados tanda Goldie: 5s $0.381 · 6s $0.457 · 10s $0.759 · 11s $0.835.
- QA obligatorio por clip: (1) STT de la pista nativa (faster-whisper small int8 CPU) palabra-por-palabra vs diálogo — cifras grandes las pronuncia bien ("1.600.000"→"un millón seiscientos mil"); (2) grilla 4-5 frames hstack → vision_analyze.

### Script batch: `scripts/batch_seedance_voice.py` (Lucky, tanda completa)
```bash
cd /root/marketing-campaign-generator && set -a && source .env && set +a
nohup python3 scripts/batch_seedance_voice.py 2>&1 &
```
Envía N escenas en paralelo con `generate_audio: true` + DIALOGUE. Recupera por run ID con `recover_voice_batch.py`.

### Quirks de la API Monid (CRÍTICO)
- **video_url** aparece en `output.content.video_url` (NO `output.video_url`).
- **cost** es un dict: `{value: 0.30555, currency: "USD"}` → usar `cost.get("value")`.
- **Poller frágil**: puede fallar con 502. Recuperar runs COMPLETED por ID via `GET /v1/runs/<id>` SIN regenerar.
- **generate_audio true** NO cuesta extra vs mudo (costo idéntico por duración).
- **Catálogo Monid**: 1,500 endpoints, solo Seedance (mini/fast/full/2.5) y Hailuo (2.3/H3). NO hay Kling/Hedra/OmniHuman/talking-avatars.

### Estrategia de recuperación
Si el poller falla (502 o URL vacía), ejecutar `recover_voice_batch.py` con los run IDs:
```bash
python3 scripts/recover_voice_batch.py --run-ids ID1,ID2,ID3 --output-dir clips/ --site-dir /var/www/golden-webproxy/reels/
```
Esto descarga, verifica audio, y publica sin regenerar (costo = $0 extra).

### Costos reales verificados
| Tipo | Costo |
|---|---|
| Mini 5s mudo | $0.30 |
| Mini 5s con voz | $0.30 |
| Mini 15s mudo | $1.13 |
| Mini 15s con voz | $1.13 |
| Full 5s r2v (audio-url) | $1.50 |
| sync-lipsync | $0.07 |

---

## Cliente real (monid-client.py) — EXISTE desde 19/08
- **Ruta**: `/root/marketing-campaign-generator/opencode/skills/reel-pipeline/references/monid-client.py` (commit `472515e`, 19/08). NO está en `scripts/`.
- Se ejecuta SIEMPRE por subprocess (nunca import):
  ```bash
  cd /root/marketing-campaign-generator && set -a && source .env && set +a
  python3 opencode/skills/reel-pipeline/references/monid-client.py \
    --mode image2video \
    --image "https://<dominio>/va/<proyecto>/scene-0X.jpg" \
    --prompt "<SEQUENCE SHOT prompt>" \
    --resolution 720p --duration 6 --ratio 9:16 \
    --project <cli> --scene scene-0X --version 1 \
    --wait 420 --report-cost
  ```
- Salida: `assets/<proyecto>/<scene>/v<N>/video/clip.mp4` + sidecars `.response.json` (incluye `cost.value` real) y `.runid`.
- `--dry-run` valida el request sin gastar — usarlo SIEMPRE antes del primer run de una tanda.
- `MONID_API_KEY` vive en `/root/marketing-campaign-generator/.env` (nunca imprimir el valor). `source .env` antes de correr.
- Preflight integrado (19/08): valida que la URL del frame responda `image/*` ANTES de POSTear — si da 400/504, primero verificar la URL con `curl -I`.

## URL del frame — REQUIERE https://dominio (crítico)
| Forma | Resultado |
|---|---|
| data URL base64 | HTTP 400 (Seedance no acepta) |
| `http://IP:puerto` | run COMPLETED pero provider 504, `cost: $0` (no cobra, pero no genera) |
| `https://dominio/...` | ✅ funciona |

### Publicar frames en el VPS (Lucky/Golden)
- **El VPS 147.93.3.250 ES el host local del contenedor hermes** — `/var/www/golden-webproxy/va/lucky/` se escribe con `cp` directo, NO con paramiko/SSH (password auth rechazada: publickey only).
  ```bash
  cp <repo>/assets/lucky/scene-0X.jpg /var/www/golden-webproxy/va/lucky/
  curl -s -o /dev/null -w "%{http_code} %{content_type}\n" "https://goldengame.com.co/va/lucky/scene-0X.jpg"  # → 200 image/jpeg
  ```
- El `/va/` público se restauró 19/08: NPM del VPS nuevo reenvía `/va/*` upstream al VPS viejo (147.93.3.250:80). Verificado con curl 200.

## Formato de prompt que FUNCIONA (SEQUENCE SHOT + voz nativa)
Estructura probada en escena 1 de Lucky (clip 6.04s, voz en español incluida en el clip):```
SEQUENCE SHOT. NO CUT. Single continuous take, 6 seconds total.

SETTING: <entorno completo: lugar, arquitectura, luz, clima, elementos clave con posiciones izq/der/fondo>

CHARACTER: <bloque fijo de personaje — ver consistencia abajo>

ACTION: <pose + mirada a cámara>

DIALOGUE (spoken by Lucky in Spanish, cheerful tone): "<línea en español>"

CAMERA: <movimiento: push-in / pull-back / tilt, inicio → final>

MOTION: <movimientos naturales: gesto, hojas, bandera, confeti>

STYLE: High-quality 3D animated film render, vibrant but natural colors, cinematic lighting, consistent character rendering every frame. NO text overlays, no extra characters, no changes to the setting or character design.
```
- **Voz NATIVA Seedance**: la sección `DIALOGUE` (español, tono indicado) + NO pasar `--no-audio` → el clip sale con pista AAC con la voz. No hace falta edge-tts para la voz del personaje.
- NO pasar `--no-audio` si se quiere voz nativa; pasarlo solo si se va a mezclar otra narración.

## Costos reales (verificados)
| Clip | Costo real |
|---|---|
| Seedance 2.0 Mini 720p 5s | $0.38115 |
| Seedance 2.0 Mini 720p 6s | $0.45675 (130,500 tokens; W×H×(24×s+1)/1024) |
| Reel 30s = 5 clips | ~$2.29 |
- El costo real aparece en `clip.mp4.response.json` → `cost.value` y en stdout con `--report-cost` (`COST_USD=<n>`).
- Monid NO tiene endpoint de balance (`/credits` → 404): no es señal de error de cuenta.

## Consistencia de personaje entre escenas
1. **Un bloque CHARACTER fijo** copiado idéntico en los 5 prompts (color exacto, ojos/iris, cejas, mejillas, dientes+lengua, brazos/manos, pies, tallo, textura).
2. Abrir cada prompt con `EXACT same character as the previous scenes:`.
3. Negativos SIEMPRE: `changed character design, different character, deformed limbs, distorted face`.
4. Si el usuario genera las imágenes (GPT/DALL·E/flux) y las envía: QA con `vision_analyze` preguntando por CONSISTENCIA del personaje + texto legible + pose vs brief ANTES de aprobar la escena para gastar en Monid.

## Pitfalls
- **No regenerar lo ya pagado**: si `clip.mp4` existe con `status: COMPLETED` en el sidecar, usarlo. Verificar con ffprobe (720×1280, ~6s).
- El engine (`reel_engine.py`) referencia el cliente en `opencode/skills/...` — respetar esa ruta, no moverlo a `scripts/`.
- Palabras tipo "marble columns / neoclassical" en prompts de casino → el generador produce templo egipcio; usar "colonial building converted into casino" + negativos `marble columns, egyptian architecture, pyramid, night`.
- Textos de logos en imágenes generadas salen mal escritos → superponer el PNG del logo en post-producción en vez de pedírselo al generador.
- Retry: 2 intentos con 20s de espera antes de reportar fallo de un clip.
- **Sync de Drive puede pisar archivos de producción a mitad de una tanda (real, Golden 19-oct-26):** el cron `sync_all.sh` (cada 30 min en DEV) hace drive_pull Drive→repo y REVIRTIÓ prompts/lote/guion editados localmente; el clip se pagó con el diálogo viejo («boleta del día» en vez de «boleta diaria»). Detección: la STT-QA de la pista nativa mostró la línea vieja. Reglas: (1) antes de una tanda, pausar el sync (`/etc/cron.d/reels-sync-all`) o correr un push y confirmar que no hay pull pendiente; (2) si un clip sale con diálogo revertido, NO regenerar la tanda: corregir prompt/lote/guion y re-lanzar SOLO la escena afectada (los batch scripts aceptan la escena como argumento posicional, p.ej. `batch_*.py S03A`) con su propio authorize/close del gate; (3) el costo del re-run cuenta como gasto real del reel aunque el manifest lo fusione (reportar suma, no el merge).
- **El audio nativo del clip SOLO sirve como guía de timing labial, NUNCA como "ambiente" de una mezcla** — arrastra bleed de la voz nativa y suena doble (error real S1-mix.mp4, Goldie 30/08; Jonathan: "se escucha la voz de Seedance al fondo"). La voz final se calibra con `scripts/fit_voice.py` (ver skill `reel-voice-lipsync`).

## Verificación post-clip
```bash
ffprobe -v quiet -show_entries stream=codec_name,width,height -show_entries format=duration -of default=noprint_wrappers=1 <clip>.mp4
```
Esperado: h264 720×1280, duración ≈ pedida, pista aac si voz nativa.

## Referencias
- Postmortem del pipeline: `/root/marketing-campaign-generator/docs/goldie-reel-postmortem.md`
- Decisión /va/ y primer clip Lucky: `/root/marketing-campaign-generator/docs/decisions/2026-08-18-lucky-primer-clip.md`
- API Monid: `/root/marketing-campaign-generator/docs/research/monid-api.md`
- Orchestrador de tanda completa de clips: `/opt/data/lucky-draft/run_lucky_clips.py` (patrón reutilizable: carga .env, dict de escenas, subprocess por escena, resumen final)
