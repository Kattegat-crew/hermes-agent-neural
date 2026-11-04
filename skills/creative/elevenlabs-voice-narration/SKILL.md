---
name: elevenlabs-voice-narration
description: "Use when a reel needs ElevenLabs TTS/STTS voice."
tags: [elevenlabs, tts, stts, voz, reels, narracion, audio, pronunciation]
---

# ElevenLabs Voice Narration (TTS / STTS) para reels

## Trigger
- El usuario tiene crédito en ElevenLabs y quiere que el audio de un reel "hable bien español" con otra voz (no la nativa de Seedance ni edge-tts).
- Corregir pronunciación en un reel **preservando la cadencia** del audio ya aprobado → STTS.
- Generar narración desde cero con voz natural latina → TTS.
- El pipeline (video-ai-generator) necesita un proveedor de voz drop-in de `edge_tts_client`.

## Conceptos clave
- **TTS** (`eleven_multilingual_v2`): texto → voz. `POST /v1/text-to-speech/{voice_id}`.
- **STTS / Speech-to-Speech** (`eleven_multilingual_sts_v2`): audio de referencia (cadencia/entonación del clip original) + texto corregido → **nueva voz que preserva ritmo del original pero REEMPLAZA la voz**. **⚠️ STTS hereda la pronunciación del audio fuente** (no la corrige — lección verificada 29/08: "Parodise" del clip nativo pasa intacto al STTS). **NO es solución para corregir pronunciación.** Solo útil para re-vozar un clip completo manteniendo la cadencia original. `POST /v1/speech-to-speech/{voice_id}` (multipart: model_id, audio) → JSON `audio_base64`.
- Cliente listo en el repo video-ai-generator: `scripts/elevenlabs_client.py` (drop-in de edge_tts_client: `synth_narration`, `synth_all`, `probe_duration`). Salida WAV 44.1kHz stereo, compatible con `mix-narration.sh` / `ffmpeg_client.mix_ducking`.
- Key: `ELEVENLABS_API_KEY` en `.env` del repo o env var. **Nunca se commitea ni imprime.**

## CLI
```bash
python3 scripts/elevenlabs_client.py --list-voices          # gratis (GET /v1/voices)
python3 scripts/elevenlabs_client.py --tts --text "..." --voice <id> --out out.wav [--speed 1.0]
python3 scripts/elevenlabs_client.py --stts --text "..." --voice <id> --ref ref.wav --out out.wav
python3 scripts/elevenlabs_client.py --synth-all --voice <id> --lines '{"scene-03": "..."}' --out-dir dir
```

## Integración con reel_engine.py
```python
from elevenlabs_client import synth_narration  # en vez de edge_tts_client
narration = synth_narration(name, scene["voice_line"], voice=<voice_id>,
                            out_dir=..., reference_audio=<audio del clip si STTS>)
```
El resto del flujo (mix ducking → audit → concat) no cambia. Documentado en `docs/elevenlabs-integration.md` del repo.

## Orden del pipeline con voz nueva
1. **Video** — clips Seedance/fal con audio nativo (referencia de cadencia).
2. **Audio** — ElevenLabs STTS: audio del clip + texto con respelling + voz objetivo → voz nueva con la cadencia del original.
3. **Sincronización** — `mix-narration.sh` (atempo + adelay + sidechain ducking) ajusta la voz a la duración del clip.
4. **Música** — (futuro) tercera pista opcional con ducking bajo la voz.

## Selección de voz SIN gastar crédito
- `--list-voices` (GET /v1/voices) — no cobra.
- Demos web de texto libre: elevenlabs.io/text-to-speech y minimax.io — escribir el guión real y escuchar la voz antes de pagar nada.
- Para nombres propios difíciles en español (Chiquinquirá, tragamonedas, Tunja) usar **respelling fonético en el texto** (funciona en ElevenLabs igual que en Seedance): "Chi-kin-qui-rá", "tra-ga-mo-ne-das", "Tun-ja".
- **Verificación obligatoria palabra-por-palabra (29/08 Goldie)**: transcribir cada WAV con faster-whisper (small, CPU int8) ANTES de publicar. Caso real: «bingos» → «vingos» (confusión b/v); fix con «BIN-GOS» (guiones + mayúsculas) regrabando solo esa línea — segundos y céntimos. El respelling SÍ obedece en ElevenLabs (a diferencia de Seedance).
- **Publicar en galería**: `voz/S{n}-<personaje>.wav` = pista de producción (CapCut monta esta, silenciando la nativa) + `voz/S{n}-nativa.wav` = referencia de timing labial. WAV ≤ duración del clip; si es más corta queda colchón de gesto sin hablar (deseable, no estirar con atempo).

## Reglas de negocio (NO negociables)
- **NUNCA generar audio VS pago sin autorización explícita del usuario** (postmortem fal 19/08: gasto no autorizado $2.45 = error grave). Aplicar el mismo espíritu de hard gate que `.fal-gate.json`.
- Costo: TTS/STTS se cobra **por caracteres de texto**, no por audio. Un reel de ~600 caracteres son céntimos. Validar SIEMPRE en el dashboard de ElevenLabs, no por estimación (lección postmortem).
- `--list-voices` no gasta.

## Pitfalls
- **Cifras con separador de miles** tipo `430.484 pesos` las lee mal eleven_multilingual_v2 (verificado 04/11/2026: «430 en 484» / «432,3484»). Solución: deletrear en el texto TTS («cuatrocientos treinta mil cuatrocientos ochenta y cuatro pesos») y verificar con whisper que oye el número completo. Decimales con coma (`284,8 millones`) y porcentajes (`95,9%`) SÍ los lee bien.
- El CLI deja además un `out.wav` duplicado del último `--out` en el CWD (byproduct): limpiarlo o ignoraarlo.
- Voz institucional por marca de la serie casinos: Golden=Angie `YPh7OporwNAJ28F5IQrm`, Paradise=Vivi `huuKaN52HlVabecRQ4Jt`.
- **Whisper normaliza**: la transcripción NO es verdad absoluta — puede oír correcto algo mal pronunciado. Combinar con oído humano o enfocar en palabras que fallan (nombres propios).
- No sustituir STTS por edge-tts (robótico, rechazado por usuario) ni re-generar video cuando el problema es solo de audio: el clip ya cuesta y quedó bueno.
- Seedance NO pronuncia bien nombres propios ni palabras >2 sílabas (Paradise→"Parodise", tragamonedas→"tragamulidas", Chiquinquirá→"Chicunquía"); sin crédito pago, fallback = respelling en DIALOGUE (ver skill video-tts-pronunciation-fix, user-owned).

## Verificación post-generación
1. `ffmpeg -y -v error -i clip.mp4 -vn -ac 1 -ar 16000 audio.wav`
2. Transcribir con whisper (NaN Builders, STT key en `/root/hermes-agent-legacy-docker/data/config.yaml` → `stt.openai.api_key`; UA de navegador obligatorio).
3. Comparar vs guion palabra por palabra; aprobar solo si coincide.

## Referencias
- `references/elevenlabs-api-quickref.md` — endpoints y shape de respuesta.