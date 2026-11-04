---
name: video-tts-pronunciation-fix
description: "Use when Spanish TTS mispronounces a reel's dialogue."
tags: [tts, voz, espanol, pronunciacion, reels, seedance, monid]
---

# Video TTS Pronunciation Fix (Seedance / Monid native voice)

## Trigger
Video reel con voz NATIVA (Seedance/Monid) pronuncia mal el español: nombres propios
("Paradise"→"Parodise"), palabras largas ("tragamonedas"→"tragamulidas"), toponímicos
("Chiquinquirá"→"Chicunquía"). El usuario quiere arreglar sin cambiar la voz.

## Regla de oro (preferencia del usuario, 19/08)
**NO usar edge-tts (es-PE-AlexNeural) como reemplazo.** Suena robótica vs la voz de
Seedance. El fix es siempre **respelling fonético en el DIALOGUE del prompt**, mismo
motor de voz y mismo frame (re-run `image2video` = $0.45675).

## Respelling que SÍ funciona
- "Paradise" → escribir **"Paradais"** → pronuncia "Paradise" ✓
- "tragamonedas" → **"tra-ga-mo-ne-das"** (sílabas) → "tragamonedas" ✓
- MUNICIPIOS complejos (Chiquinquirá, etc.): **respelling NO basta** → simplificar
  el diálogo (ej. "Te esperamos en Boyacá y Cundinamarca" en vez de listar ciudades).

## Verificación post-generación
1. `ffmpeg -y -v error -i clip.mp4 -vn -ac 1 -ar 16000 audio.wav`
2. `python3 <skill_dir>/scripts/transcribe_audio.py audio.wav es` (whisper, NaN Builders)
   - Key STT en `/root/hermes-agent-legacy-docker/data/config.yaml` → `stt.openai.api_key` (NO `/opt/data`).
   - Requiere User-Agent navegador o Cloudflare 403.
3. Comparar vs guión; si nombre propio falla → simplificar texto.

## Regeneración (mismo frame HTTPS)
```
python3 monid-client.py --mode image2video --image <url_https> \
  --prompt "<SEQUENCE SHOT ... DIALOGUE corregido>" \
  --resolution 720p --duration 6 --ratio 9:16 \
  --project lucky --scene scene-0X --version 2 --wait 420 --report-cost
```
Monid NO tiene endpoint balance (`/v1/credits`→404); run sin fondos da
`providerResponse.httpStatus`!=200 y `cost:0`.

## Costos
Re-run 1 escena: $0.45675 (130,500 tokens @ $3.5/M). Reel 5 escenas ~$2.28 + $0.46 c/u re-hecha.

## Anti-patrón
- "Cambio la voz por edge-tts" → RECHAZADO (inexpresiva).
- Forzar respelling en topónimos complejos → no funciona; simplificar el texto.
- Asumir saldo agotado por `/v1/credits` 404 → ese endpoint no existe.
