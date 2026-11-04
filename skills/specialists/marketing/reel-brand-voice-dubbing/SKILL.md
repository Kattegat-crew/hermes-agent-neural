---
name: reel-brand-voice-dubbing
description: "Use when dubbing a reel with ElevenLabs brand voice."
tags: [reels, dubbing, elevenlabs, monid, stts, capcut, voz-marca]
---

# Reel Brand-Voice Dubbing (Monid → ElevenLabs STTS → CapCut)

## Cuándo usar
- Reel 9:16 de cliente con personaje animado que necesita la VOZ DE MARCA de ElevenLabs (Voz_Lucky `U9tZtg3uJtVgXPkvosWR`, Voz-Goldie `qWWAqFomnJ99VwQLREfT`) con labios sincronizados.
- Es el pipeline que Jonathan APROBÓ (29/08) para Bingo Millonario. Sustituye al pase completo de `fal-ai/sync-lipsync` como ruta estándar. Skills de proveedor: `creative/monid-seedance-clips` y `media/elevenlabs-voice-narration` (user-owned — consultar, no editar).

## Pipeline por escena (5 pasos)

1. **Frame 9:16 del cliente** (Jonathan los genera y sube a Drive; QA con vision_analyze: personaje consistente, cara con detalle suficiente para labios, cero defectos). Publicarlo como first_frame en `goldengame.com.co/va/<proyecto>/bingo/` (https obligatorio para Monid).
2. **Monid seedance-2.0-mini** 720p, `generate_audio: true`, prompt SEQUENCE SHOT con bloque DIALOGUE en español con respelling → clip con voz nativa y boca animada, coherentes por construcción.
3. **QA de audio**: extraer audio (`ffmpeg -i clip.mp4 -vn audio.wav`) + transcribir (Whisper/Scribe) y verificar que dijo el texto del guion.
4. **ElevenLabs STTS** (`eleven_multilingual_sts_v2`): audio del clip como referencia + voz de marca + texto corregido → WAV final. La cadencia del original se PRESERVA → los labios siguen calzando sin pase de lipsync. Se cobra por caracteres (céntimos).
5. **Handoff CapCut**: entregar clips + WAVs emparejados por escena (nombres `scene-0N.mp4` / `scene-0N-voz.wav`). Jonathan monta el reel completo en CapCut: música, logo, rótulos, publicación. NO entregar video final sin su edición.

## Plantilla de prompt (8 bloques, validada 29/08)

```
SEQUENCE SHOT. NO CUT. Single continuous take, N seconds total.

SETTING: <lugar completo, luz, elementos clave con posiciones>
CHARACTER: <bloque fijo idéntico en TODAS las escenas: colores, ojos, cejas,
mejillas, dientes+lengua, extremidades, accesorios y mano de cada cosa>
ACTION: <pose + mirada a cámara>
DIALOGUE (spoken by <CHAR> in Spanish, warm cheerful Colombian tone, looking at camera): "<línea con respelling>"
CAMERA: <movimiento inicio → final>
MOTION: <movimientos naturales> Lips clearly articulating the dialogue.
STYLE: High-quality 3D animated film render, vibrant but natural colors, cinematic lighting, consistent character rendering every frame. NO text overlays, no subtitles, no extra characters, no camera cuts, no changes to the setting or character design.
```

## Reglas y costos

- **Respelling DIALOGUE**: "trebol" (sin tilde), "Paradais", "esta" — Seedance/ElevenLabs pronuncian mejor; los acentos que el TTS lee bien ("suerte") quedan normales. Ver skill `creative/video-tts-pronunciation-fix` (user-owned).
- **Timing**: Seedance habla ~2.7 palabras/s; Voz_Lucky (ElevenLabs) ~2.2 pal/s (medido con silencedetect 29/08). Elegir duración del clip con la voz de marca, no con la nativa: N = palabras_del_bloque / 2.2 + pausas de dirección. Si no cabe, se rasura la frase en el guion, NUNCA la escena.
- **Costos reales Monid mini 720p 9:16** (fórmula verificada): 4s=$0.31 · 5s=$0.38 · 7s=$0.53 · 8s=$0.60 · 9s=$0.69. Reel completo Lucky ≈$2.30 · Golden ≈$1.15. Presupuesto aprobado para ambos reels: $5.00.
- **VETO**: modelos full ($0.30/s en fal, $0.76/clip Monid) vetados por Jonathan para este proyecto (gastó $6 en una escena el 28/08).
- **Gate humano**: dry-run por escena + costo estimado por escena + "corre" explícito de Jonathan antes del primer run pago (gate `.fal-gate.json` en `/root/marketing-campaign-generator`).
- **Fallback lipsync**: si STTS desincroniza labios en un primer plano de diálogo, ESA escena recibe un pase de `fal-ai/sync-lipsync` (~$0.07 por 6s; recorta el clip a la duración de la voz — el tail se concatena en edición). Contingencia, no regla.
- fal seedance mini ya NO reporta billing por API: costo firme solo en el dashboard fal (irrelevante si se usa Monid, que sí reporta `cost.value`).

## Verificación post-escena

1. `ffprobe`: h264 720×1280, duración pedida, pista aac.
2. Transcripción = texto del guion (palabra por palabra en anclas: cifras, fechas, nombre del evento).
3. Frames a 6fps: variación de visemas (la boca NO queda fija) + personaje consistente con el frame de referencia.
4. STTS: duración WAV ≈ duración del tramo hablado original (±10%); sino, `--speed` en TTS o rasurar frase.

## Pitfalls

- Seedance re-foniza con su voz nativa y puede congelar la boca aunque el prompt pida visemas — el labial real nace del clip nativo, y la voz de marca entra DESPUÉS por STTS, no en el prompt.
- No re-generar video cuando el problema es solo de voz: el clip ya se pagó; el arreglo va por STTS (y lipsync solo como fallback puntual).
- Frames de escenas con diálogo: la cara debe ocupar buen encuadre (close/medio) o el labial se ve borroso.
- Guardar sidecars `.response.json` de Monid (costo real) y el prompt exacto usado por escena — re-generar barato solo es posible con el prompt versionado.
- Frontmatter de SKILL.md: si la description lleva `:`, va entre comillas o el parser YAML la rechaza.
