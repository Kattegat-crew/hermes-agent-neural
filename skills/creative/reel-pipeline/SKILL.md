---
name: reel-pipeline
description: >-
  Use when generating a vertical 9:16 AI reel. e imagen-a-video. Usa OpenCode Go para el 90% del trabajo (gratis) y Monid Seedance 2.0 para el realismo final (pago por clip). Pipeline de 3 capas: rustico → refinar → realismo.'
tags: [reels, seedance, monid, vertical, video, pipeline, 9:16, ia]---


# Reel Pipeline Skill

## Overview

Genera reels verticales 9:16 (TikTok/Shorts/Reels) usando un pipeline de 3 capas:
1. **Rustico** (gratis): OpenCode Go codea Three.js + puppeteer renderiza draft
2. **Refinar** (gratis): NaN flux-2-klein hace style frame + kokoro genera narracion
3. **Realismo** (pago): Monid Seedance 2.0 genera el clip final con audio

## When to Use

- Generar un reel desde texto (topic → video)
- Generar un reel desde imagenes existentes (imagenes → video)
- Animar personajes/escenas ya diseniadas
- Crear contenido para TikTok/Instagram Reels/YouTube Shorts

## When NOT to Use

- Video horizontal 16:9 (usar scroll-world skill en su lugar)
- Video mas largo de 15 segundos por clip (limite de Seedance)
- Video que requiere edicion compleja con cortes (usar ffmpeg manual)

## Pipeline

### Modo A: Imagen-a-video (usuario tiene imagenes)

```
Imagen del usuario
  → Monid Seedance 2.0 image-to-video (first_frame role)
  → ffmpeg concat + kokoro TTS
  → reel.mp4 9:16
```

### Modo B: Texto-a-video (desde cero)

```
Brief de texto
  → researcher: referencias visuales
  → specifier: plan escena por escena + prompts
  → designer: art direction 9:16
  → developer: codea Three.js (camara, motion, timing)
  → puppeteer + chromium: renderiza draft.mp4
  → ffmpeg: extrae keyframe del draft
  → NaN flux-2-klein: restyle del keyframe
  → NaN kokoro: genera narracion de audio
  → Monid Seedance 2.0: draft + keyframe estilizado → clip final
  → ffmpeg: concat clips + audio → reel.mp4
```

## Monid API

- Endpoint: POST https://api.monid.ai/v1/run
- Auth: Bearer $MONID_API_KEY (from .env, never hardcode)
- Provider: bytedance
- Endpoints:
  - /v1/video/seedance-2.0 (full, up to 4K, $7-7.7/1M tokens)
  - /v1/video/seedance-2.0-mini (up to 720p, $3.5/1M tokens)
  - /v1/video/seedance-2.0-fast (up to 720p, $5.6/1M tokens)
- Input body: { content: [...], resolution, duration, ratio, generate_audio }
- Async: returns 202 with runId, poll GET /v1/runs/:runId
- Token formula: tokens = width x height x 24fps x seconds / 1024

## NaN Builders API

- Base: https://api.nan.builders/v1
- Auth: Bearer $NAN_API_KEY (from .env, never hardcode)
- Image gen: POST /v1/images/generations (model: flux-2-klein)
- TTS: POST /v1/audio/speech (model: kokoro)

## Costos de referencia

| Config | Costo/clip | Clips con $1 |
|---|---|---|
| 480p Mini 5s | $0.17 | 5 |
| 720p Mini 5s | $0.38 | 2 |
| 720p Full 5s | $0.76 | 1 |
| 1080p Full 5s | $1.87 | 0 |

## Prompt cinematografico (sequence shot)

Usar este template para Seedance (basado en tweet de @matthieu_ai):

```
SEQUENCE SHOT. NO CUT. Single unbroken handheld take throughout, [DURATION] seconds total.
[DESCRIPCION DE LA ESCENA]. [MOVIMIENTO DE CAMARA]. [ILUMINACION].
[PERSONAJE]: [DESCRIPCION FISICA], [ACCION].
[AMBIENTE]: [DESCRIPCION DEL ENTORNO].
```