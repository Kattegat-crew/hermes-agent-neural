---
name: video-ai-generator
description: "Use when running the 9:16 AI reel pipeline (reel-worker)."
tags: [video, reels, pipeline, activepieces, tts, 9x16, vertical]
license: MIT
compatibility: hermes, opencode
---

# Video AI Generator — Automated 9:16 Vertical Video Pipeline

Complete operational guide for the AI Video Generation pipeline developed for NeuralCrew Labs, Golden Game, and Lucky Club.

## Pipeline Architecture
```
brief.json ──► ActivePieces (reel-orchestrator) ──► POST :8090/jobs
  ──► reel_worker.py (systemd: reel-worker.service on port 8090)
    ──► reel_engine.py:
      1. Scene breakdown & asset generation (9:16 ratio)
      2. Voiceover synthesis (TTS: es-PE-AlexNeural / Kokoro / Whisper)
      3. Image-to-Video generation (Seedance / ComfyUI / Flux)
      4. Audio ducking & BGM mixing (ffmpeg asplit)
      5. Auto-auditor (ffprobe + OCR + VAD quality check)
      6. Tokenized preview generation (/va/<token>/)
      7. Final concatenation ──► output/reel.mp4 (1080x1920)
  ──► Callback webhook ──► ActivePieces (reel-callback) ──► Telegram / WhatsApp notification
```

## Core Execution Commands & APIs

### 1. Worker Status & Health Check
```bash
systemctl status reel-worker.service
curl -s http://localhost:8090/health
```

### 2. Dispatching a Video Job via API
El worker exige JWT desde 2026-08-28 (`python3 scripts/make_worker_token.py --days 1 --sub <flow>`)
y el brief valida contra `contracts/brief.schema.json` — `scenes` es ARRAY de objetos
`{"name": "scene-0N", "voice_line": "..."}`, NO un número:

```bash
curl -X POST http://localhost:8090/jobs \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "job_id": "job-01",
    "project": "golden",
    "brand": "Golden Game",
    "topic": "Bingo Millonario",
    "aspect_ratio": "9:16",
    "scenes": [{"name": "scene-01", "voice_line": "Hola, bienvenido a Golden Game."}],
    "approved_to_spend": false,
    "max_cost_usd": 3.0,
    "budget": {"currency": "USD", "max_total_usd": 3.0},
    "delivery": {"target_format": "720x1280", "target_duration_s": 25}
  }'
```

Sin `voice` en el brief, el engine resuelve la voz de marca (`BRAND_VOICES`:
golden→Voz-Goldie, lucky→Voz_Lucky) — skill `elevenlabs-brand-voice`.

### 3. Verification & Video Quality Auditing
- Verify resolution: `1080x1920` (9:16 vertical format).
- Audio levels: Integrated loudness targeted at `-14 LUFS` to `-16 LUFS`.
- Subtitles: Clean auto-captioning with high contrast styling.
