---
name: ai-audio-pronunciation-qa
description: "Use when verifying AI voice pronunciation vs a script."
tags: [audio, tts, whisper, pronunciation, qa, reels, ffmpeg, espanol]
---

# AI Audio Pronunciation QA

## Cuándo usar
- El usuario pregunta si la voz de un video/TTS pronuncia bien (sobre todo español con nombres propios: marcas, ciudades, anglicismos).
- QA de reels antes de aprobar: verificar que la voz del modelo (ej. voz nativa Seedance) dice exactamente el guión.
- Determinar si un error de pronunciación es del modelo de voz o del ensamblaje.

## Pasos
1. **Extraer audio** de cada clip a WAV mono 16kHz:
   ```bash
   ffmpeg -y -v error -i clip.mp4 -vn -ac 1 -ar 16000 scene-0X.wav
   ```
2. **Transcribir con whisper** (NaN Builders, OpenAI-compatible):
   - Endpoint: `POST https://api.nan.builders/v1/audio/transcriptions` — multipart: `file`, `model=whisper`, `language=es`.
   - Requiere User-Agent de navegador (sin él → Cloudflare 403 code 1010).
   - Leer la key con Python (`yaml.safe_load`) — nunca copiarla de salida enmascarada.
   - Config real: `/root/hermes-agent-legacy-docker/data/config.yaml` → `stt.openai.api_key`. **OJO:** scripts viejos apuntan a `/opt/data/config.yaml` y fallan con FileNotFoundError — verificar ruta antes de transcribir.
3. **Comparar** transcripción vs texto esperado, palabra por palabra, en tabla: escena | esperado | pronunciado | estado (✅/⚠️/❌).
4. **Conclusión**: si los errores son sistemáticos en palabras largas o nombres propios y TODOS los clips usan el mismo TTS → es del modelo de voz, no del pipeline ni del audio del usuario.

## Pitfalls
- **Whisper normaliza — la transcripción NO es verdad absoluta.** Puede transcribir correctamente una palabra mal pronunciada (caso real: whisper oyó "Paradise" cuando el humano oyó "Parodise"). Combinar con oído humano o enfocar en las palabras conocidas por fallar (nombres propios).
- **Errores típicos de la voz nativa de Seedance 2.0 Mini en español** (verificado 19/08): Paradise→"Parodise", tragamonedas→"tragamulidas", Chiquinquirá→"Chicunquía", La Calera→"La Calala", Funza→"Funga", Tunja→"Tunga". Fallan nombres propios y palabras >2 sílabas; las frases cortas y comunes suelen salir bien.
- **Fix estándar (costo $0)**: regenerar NO hace falta — el video visual está bien. Silenciar la pista nativa y mezclar edge-tts `es-PE-AlexNeural` (gratis, pronuncia perfecto) sobre el clip con `mix-narration.sh`. En Monid, pedir los clips con `--no-audio` y montar la voz en post.
- Audio más corto que el video (ej. voz 4.85s en clip de 6s) es normal — el resto es ambiente; no es un bug.

## Verificación post-fix
- Re-extraer audio del clip mezclado, re-transcribir, comparar de nuevo contra el guión.
- Solo aprobar cuando la transcripción del clip arreglado coincida con el texto esperado.
