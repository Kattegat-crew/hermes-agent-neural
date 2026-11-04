---
name: voice-message-transcription
description: "Use when a voice message (ptt) arrives and needs a reply."
tags: [voz, audio, transcripcion, whisper, stt, whatsapp, telegram]
---

# Voice Message Transcription

## Trigger
- Llega un mensaje de voz (ptt) en WhatsApp/Telegram/Discord (`[ptt received]`, nota de voz, audio adjunto).
- El usuario pide transcribir un audio o procesar una nota de voz.

## Protocolo de respuesta
- **Nunca repetir, citar ni hacer eco de la transcripción** en la respuesta (no escribir `🎙️ "..."`).
- Responder directamente a la petición hablada, como si se hubiera escrito.
- Si la transcripción tiene artefactos del dictado (p. ej. "ayudamos" por "ayúdanos"), interpretar la intención y corregir en la entrega.

## Pasos
1. **Localizar el audio entrante:**
   ```bash
   find /opt/data/cache/audio -type f \( -iname "*.ogg" -o -iname "*.opus" -o -iname "*.m4a" -o -iname "*.mp3" \) -mmin -10
   ```
   El archivo más reciente es el mensaje nuevo (`aud_*.ogg`).
2. **Transcribir** con el script listo:
   ```bash
   python3 scripts/transcribe_audio.py <audio.ogg> es
   ```
   (relativo al skill dir; el script lee la key de config.yaml, arma el multipart y devuelve el texto).
3. **Procesar la petición** y responder directamente.

## STT endpoint (NaN Builders / OpenAI-compatible)
- `POST https://api.nan.builders/v1/audio/transcriptions` — multipart form-data: `file`, `model=whisper`, `language=es`.
- Config STT en `/opt/data/config.yaml` → `stt.openai` (`api_key`, `base_url`, `model`).

## Pitfalls
- **Cloudflare 403 code 1010:** sin User-Agent de navegador la API rechaza TODOS los endpoints, incluido `/audio/transcriptions`. Header obligatorio:
  `Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36`
- **Key enmascarada:** Hermes muestra la API key truncada (`sk-JzB...ohYw`) en la salida de grep/read. No copiarla de la salida — leerla con Python: `yaml.safe_load(open('/opt/data/config.yaml'))['stt']['openai']['api_key']`. En disco la key está completa.
- **No usar `curl -F` si no se puede leer la key** (env var vacía al extraer de salida enmascarada) — usar Python para leer config.yaml y armar el request en el mismo script.
- Idiomas: pasar `language=es` para español (evita artefactos bilingües).

## TTS (salida de voz)
Si el usuario pide responder con audio o responder en canal de voz, usar la herramienta `text_to_speech` — no generar audio por defecto en respuestas de texto.
