---
name: reel-audio-mixing
description: "Use when mounting brand TTS voice onto a reel clip."
tags: [reels, audio, mixing, atempo, voz, ffmpeg, elevenlabs]
---

# Reel Audio Mixing — voz de marca sobre clip pagado (mix local $0)

Clase de trabajo: el clip de video YA está generado y pagado (Seedance/Monid con voz nativa
que guió el labial); hay que montarle la voz de marca de ElevenLabs encima con sincronización
verificable, sin regenerar video ni pagar lipsync. Aplica a personajes con pantalla-rostro
LED (Goldie) o cuando el labial nativo es aceptable. Para bocas de carne que requieren
re-dibujado, ver `reel-voice-lipsync` (sync-lipsync de fal).

## Receta validada end-to-end (Goldie S1, 29/08 — Δ medio 0.06s, publicado)

1. **STT palabra-por-palabra de ambas pistas** con faster-whisper (`small`, int8, CPU,
   `word_timestamps=True`), idioma es:
   - pista A = `voz/S{n}-nativa.wav` extraída del clip (ffmpeg `-vn` si hace falta) → **GUÍA del labial**
   - pista B = WAV crudo de ElevenLabs → lo que se monta
2. **Calibrar atempo = (fin de última palabra en B) / (fin de última palabra en A)**.
   NO usar duraciones de archivo. Caso S1: 3.60/4.84 ≈ **0.75**. Sin calibrar (atempo 1.0)
   el desfase acumulado llegó a +1.34s al cierre.
3. **Mezclar** con `scripts/mix-narration.sh` del repo marketing-campaign-generator (usa layout del
   engine: `assets/<proyecto>/<scene>/v<N>/mixed/mixed.mp4`, versionado, nada se pisa):
   ```bash
   cd /root/marketing-campaign-generator && set -a && source .env && set +a
   bash scripts/mix-narration.sh --clip <clip.mp4> --narration <voz.wav> \
     --project <slug> --scene <slug> --atempo <ratio> --start-ms 0
   ```
4. **Si se quiere ambiente del clip bajo la voz a nivel broadcast**, la cadena del script
   original no duckeaba bien (mezcla a −27 dB con ambiente tapando la voz). Cadena propia
   verificada (v4, Goldie):
   ```bash
   ffmpeg -y -i clip.mp4 -i voz.wav -filter_complex \
    "[0:a]volume=-16dB,afade=t=out:st=<fin_última_palabra>:d=0.25[amb]; \
     [1:a]atempo=<ratio>,apad=whole_dur=<clip_dur>,highpass=f=90,volume=1.75,alimiter=limit=0.92[voc]; \
     [amb][voc]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[a]" \
    -map 0:v -map "[a]" -c:v copy -c:a aac -b:a 192k mixed.mp4
   ```
   - `afade` al cierre de la última palabra: sin él queda ~1s de ambiente solo = parece error.
   - `normalize=0` en amix es CLAVE (con normalize el nivel cae a la mitad).
   - Mix 100% limpio (sin ambiente): descartar la rama `[amb]`, mapear solo `[voc]`.
5. **Verificación obligatoria antes de anunciar**: re-STT del mix final, tabla Δ por palabra
   contra la guía nativa → aprobar con **Δ medio ≤0.1s**. Y QA de nivel:
   `ffmpeg -i mixed.mp4 -map 0:a -filter:a volumedetect` → mean_volume ≈ nivel del clip fuente (−17 dB).

## Montaje multi-escena con onsets manuales (validado 19-oct-2026, master Golden 20s)

Cuando hay varios clips (S01..S04) que deben entrar en un timeline duro (p. ej. 20.00s) y
fit_voice da pads falsos o atempo <0.7, NO usar los WAV fitados. Receta:

1. **Onset real del habla nativa por clip**: `ffmpeg -i clip.mp4 -af silencedetect=noise=-32dB:d=0.25 -f null -` → primer silence_end = onset (más fiable que whisper para el arranque).
2. **Presupuestar el timeline** por segmento: `dur_seg >= onset + dur_tts + cola`, recortando video (`trim=start=0:duration=…`) y audio (`adelay=<ms>|<ms>,apad,atrim=0:<dur_seg>` por toma, luego `concat=n=5:v=0:a=1`).
3. **Cola gráfica**: estirar el último clip con `tpad=stop_mode=clone:stop_duration=…` y montar la cartela legal con `drawtext` + `textfile=` (3 archivos .txt evitan escapar `:` y `·` en el filtro).
4. **loudnorm VA DENTRO de filter_complex** (`concat=…,loudnorm=I=-16:TP=-1.0:LRA=11[aout]`): `-af` y `-filter_complex` no combinan sobre el mismo stream mapeado — con `-af` falla o se ignora.
5. **QA obligatorio**: (a) STT del MASTER final con faster-whisper — las líneas deben salir completas, en orden, en los tiempos previstos y nada cortado; (b) `ebur128` → I ≈ −16 LUFS; (c) frame de la cartela recortado (`crop`) pasado a visión para verificar legibilidad/sin cortes.

Resultado verificado: 5 líneas STT en 0.27/2.91/6.17/10.67/12.77s, −15.1 LUFS, sincronía aceptable sin atempo artificial.

## Reglas del proyecto (no negociables)

- **Nada de pago sin OK explícito del Admin** (este mix cuesta $0, pero el clip que lo
  recibe ya fue aprobado). Presentar experimento con una escena → informe con números
  (Δ por palabra, niveles, costo) → gate para el resto del lote.
- **Galería versionada, jamás borrar**: el mix se publica como archivo NUEVO
  (`clips/S1-mix.mp4`) junto al `S1-seedance.mp4`, con tarjeta que explica qué es cada uno.
- Cada escena necesita su propia calibración de atempo (la brecha varía por frase).

## Pitfalls

- `--speed` de ElevenLabs NO estira el audio (verificado 29/08: `--speed 0.75` devolvió la
  misma cadencia, Δ +1.28s persistente). El timing SIEMPRE se corrige con atempo de ffmpeg
  post-grabación.
- atempo ≤0.7 empieza a sonar artificial; si la brecha es mayor, ajustar el texto del TTS,
  no forzar el estirado.
- faster-whisper small puede transcribir «bingo»→«pingo» en audio procesado — no es defecto
  del mix; compara guía vs mix con el MISMO modelo (error simétrico = Δ válido).
- `mix-narration.sh` con `--project/--scene` escribe en `assets/` (no `output/`) — respeta
  output_layout.py; `--out` tiene precedencia si se pasa ambos.
- El shell de una cadena larga de ffprobe+ffmpeg puede exceder timeouts del terminal →
  separar mix y QA en llamadas distintas, o subir timeout.

## Overlaps conocidos (candidatos a consolidar por el curador)

- `reel-voice-lipsync` — misma clase general (voz+labial); esa cubre bocas de carne con
  sync-lipsync de fal; esta cubre mix local sin gasto. Si `reel-voice-lipsync` se adopta,
  fusionar como dos caminos de una tabla de decisión.
- `elevenlabs-voice-narration` (user-owned, pendiente `hermes curator adopt`) — generación
  del WAV; esta skill consume ese WAV.
- `monid-seedance-clips` (user-owned para writes de fondo) — produce el clip nativo que
  esta skill mezcla.
