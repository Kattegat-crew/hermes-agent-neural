---
name: elevenlabs-brand-voice
description: "Use when configuring a brand voice in ElevenLabs/AKARI."
tags: [elevenlabs, tts, voz-marca, akari, video, stt, sintesis]
version: 1.0.0
author: Sindri (Producer)
metadata:
  hermes:
    tags: [elevenlabs, tts, brand-voice, akari, video-ai-generator]
    related_skills: [vps-host-repo-access, video-ai-generator]
license: MIT
compatibility: hermes
---

# Voz de marca ElevenLabs → pipeline AKARI (procedimiento)

## When to use
Cuando piden configurar/cambiar/validar la voz de una marca o personaje (Goldie, Lucky, cliente nuevo) en el pipeline `video-ai-generator`, o auditar pronunciación de una voz antes de gastar en video.

Repo `/root/marketing-campaign-generator` en host .250 vía docker socket (patrones de acceso: skill `vps-host-repo-access`). El `.env` del repo tiene `ELEVENLABS_API_KEY` y `REEL_WORKER_JWT_SECRET` — **nunca imprimirlos**, solo nombres de claves.

## 0. Regla de oro
El Admin RENOMBRA las voces en ElevenLabs (ej. "Kate" → "Voz_Lucky"). Nunca proponer voces por nombre en memoria: SIEMPRE listar antes por `voice_id` y `generation_time`.

## 1. Listar voces (gasto $0)
`GET https://api.elevenlabs.io/v2/voices?page_size=100` con header `xi-api-key` (la v2 trae `generation_time`: null = premade, timestamp = creada/clonada reciente — ordenando por eso se detectan las voces nuevas del Admin). Script: `scripts/list_voices.py` (correr en contenedor con `-v /root/marketing-campaign-generator:/repo:ro`, la key se lee del .env). NO usar curl en alpine interpolando la key: el quoting se rompe fácil.

## 2. QA de pronunciación round-trip (antes de gastar en video)
1. Sacar las líneas reales de `planning/<proyecto>/<voz>-voice-lines.json` (si no hay, escribir 1 línea representativa: saludo + horario + sede + lugar).
2. Sintetizar vía el propio engine (prueba el dispatch a la vez):
   `docker run --rm --network host -i --entrypoint /bin/sh -v /root/marketing-campaign-generator:/repo -v /root/vag-audio/<proy>-lines:/out python:3.13-alpine -c 'apk add -q ffmpeg >/dev/null 2>&1; cd /repo/scripts && python3 -'` con stdin = `scripts/synth_brand_lines.py` (usa `_resolve_voice` + `_synth_narration` de reel_engine).
3. Concatenar preview: `printf "file 'scene-0N.wav'\n"... > list.txt && ffmpeg -f concat -safe 0 -i list.txt -c copy preview.wav` → `preview_ES.mp3` a 128k.
4. Transcribir con STT `scribe_v1` (multipart file=@mp3 + model_id, header xi-api-key): `scripts/stt_roundtrip.py`. **El texto transcrito debe ser 100% fiel al original** — revisar topónimos (Funza, sede), "aquí", acentos. Fiel = voz aprobable.
5. Entregar el preview al Admin como `MEDIA:` para el veredicto de oído (técnico = yo; carácter = él).

Para traer archivos del workspace del agente al host: `base64 -w0 f | docker run -i --entrypoint /bin/sh -v /root/vag-audio:/out alpine -c 'cat > /tmp/g.b64 && base64 -d /tmp/g.b64 > /out/f'` (el workspace /opt/data NO está montado en el docker del host — montar una ruta inexistente crea dir vacío en el host, pitfall clásico).

Ajustes de carácter sin cambiar de voz (re-grabar preview, centavos): más vendedora → `style` 0.5 + `speed` 1.05; más serena → `stability` 0.6, `style` 0.2.

## 3. Registro BRAND_VOICES (una vez por marca)
`scripts/reel_engine.py` (desde commit 2bad8da en main) ya trae el mecanismo: `BRAND_VOICES = {proyecto: voice_id}`, `_resolve_voice(brief)` (brief["voice"] > BRAND_VOICES[project] > DEFAULT_VOICE) y `_synth_narration` (dispatch: voz contiene "Neural" → edge-tts, si no → elevenlabs_client). Para marca nueva: agregar la entrada al dict. Parchar con script python vía stdin (assert old_string → replace → `py_compile.compile(doraise=True)`), NUNCA con sed inline.

## 4. Test + commit
- pytest del engine en contenedor desechable: `apk add bash` (varios tests lanzan bash por subprocess → sin él, 127 falsos FAILED) + `pip install -q pytest edge-tts pillow`. Esperado: `tests/test_reel_engine.py` → 36 passed. `apk add` combinado puede fallar silencioso → instalar por separado y verificar. Falsos FAILED conocidos del contenedor: test_review_page (playwright), test_security_credentials (creds viven en host), test_image_refiner (ffmpeg fallback), test_output_layout (preexistente).
- commit+push: `alpine/git` tiene ENTRYPOINT git → `--entrypoint /bin/sh`; montar `-v /root/.ssh:/keys:ro`, `GIT_SSH_COMMAND="ssh -i /keys/id_ed25519 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"`, identity `git config user.email "sindri@neuralcrewlabs.com"`.

## 5. Pitfalls de elevenlabs_client.py (todos fixeados 28/08 — verificar antes de fiarse de código viejo)
- `_headers`: SOLO `xi-api-key` (mandar también `Authorization: Bearer` → 401 "Only one of xi-api-key and authorization headers must be provided").
- Necesita `import tempfile` (NameError en `_to_wav` — bug histórico 8b4678b que nadie detectó porque el cliente nunca se había ejecutado: TODO cliente nuevo se prueba con una síntesis real, no leyendo código).
- Modelos: TTS = `eleven_multilingual_v2`; STTS (speech-to-speech) = `eleven_multilingual_sts_v2`. `output_format=mp3_44100_128` → ffmpeg a WAV 44.1k stereo.
- El error de ElevenLabs llega como JSON con `request_id` — citarlo si se escala al Admin.

## Valores de referencia (28/08/2026)
- Voz-Goldie = `qWWAqFomnJ99VwQLREfT` · Voz_Lucky = `U9tZtg3uJtVgXPkvosWR` (ex Kate) — en `BRAND_VOICES`.
- Preview QA Goldie: `workspace/vag-plan/voz/goldie-lines/goldie_preview_ES.mp3` (4 líneas, 18.6s, STT 100% fiel).
- Suite al cierre: test_reel_engine 36/36 · cleanup 10/10.
