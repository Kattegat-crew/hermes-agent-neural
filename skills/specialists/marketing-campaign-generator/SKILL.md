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

## Publication Chain (publish.py + Composio CLI, verified live)
- Composio CLI DOES work headless as uid `hermes` when run with the right env — the old "CLI roto sin TTY" diagnosis was an env problem, not a CLI problem:
  ```bash
  export HOME=/opt/hermes-agent-data
  export PATH=/opt/hermes-agent-data/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
  composio execute INSTAGRAM_GET_USER_INFO -d '{"ig_user_id":"<ig_id>"}' --account instagram_<alias>
  ```
  Credential resolution order in `composio_mcp`/CLI: env key → `/tmp/composio-cred.json` → CLI; with HOME/PATH set correctly the CLI alone suffices (no TTY needed).
- `publish.py` window rule: the ±2 h slot check (`abs(now - slot) < 2h`) only gates the NO-`--id` auto-discovery mode. With `--id <rid>` the only hard gate is `estado == 'aprobado'` — an approved row can be published outside its slot (e.g. hours late) without `--force`.
- Pre-copy verification of a finished reel (repeatable pattern): `ffprobe` for specs (duration, 9:16, H.264/AAC) plus a contact sheet — `ffmpeg -i reel.mp4 -vf "fps=1/4,scale=300:-1,tile=3x3" -frames:v 1 contact.jpg` — then read the burned-in cartelas visually so the copy never contradicts on-screen text (amounts, dates, disclaimers).
- Casino copy standard for these reels: single block, hook within the first ~125 chars (IG preview cut), zero prize amounts / zero mechanics / zero +18 in the TEXT (that disclaimer is already burned into the artwork); ~8 hashtags on IG vs ~3 on FB; publisher appends the standard footer (bio link + site) automatically.
