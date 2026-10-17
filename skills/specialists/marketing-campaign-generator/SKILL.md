---
name: marketing-campaign-generator
description: End-to-end 9:16 vertical AI video generation pipeline (Reels, TikTok, Shorts) with ActivePieces, reel-worker (:8090), TTS, Image-to-Video, audio ducking, and automated rendering.
license: MIT
compatibility: hermes, opencode
---

# Marketing Campaign Generator — Automated 9:16 Vertical Video Pipeline

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
```bash
curl -X POST http://localhost:8090/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "brand": "NeuralCrew Labs",
    "topic": "Agentes IA para Automatización Empresarial",
    "aspect_ratio": "9:16",
    "voice": "es-PE-AlexNeural",
    "scenes": 4,
    "target_duration_s": 30
  }'
```

### 3. Verification & Video Quality Auditing
- Verify resolution: `1080x1920` (9:16 vertical format).
- Audio levels: Integrated loudness targeted at `-14 LUFS` to `-16 LUFS`.
- Subtitles: Clean auto-captioning with high contrast styling.
