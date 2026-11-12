---
name: launch-video-kit
description: "Use when producing a campaign video's audio and mix."
version: 1.0.0
author: NeuralCrew
license: MIT
platforms: [linux, macos]
tags: [video, audio, tts, mezcla, campana, reels]
---

# launch-video-kit (vendorizado)

> Alcance: audio y montaje para vídeo de campaña con las piezas vendorizadas en
> `vendor/launch-video-kit` — locución TTS por líneas, análisis y loop de música,
> verificación de mezcla por números.

Fuente: <https://github.com/borjaperfra/launch-video-kit> (MIT), vendorizada en
`vendor/launch-video-kit/`. El README vendorizado es la referencia completa con
el porqué de cada decisión y los números que la respaldan. Esta skill es el
procedimiento y las reglas que se saltan solas.

## Qué aplica a nuestro pipeline

- `vendor/launch-video-kit/scripts/gen-voice.mjs` — locución por líneas contra
  un endpoint TTS OpenAI-compatible. **Si el endpoint es pagado, registrar
  autorización con `scripts/spend_gate.py` antes de llamarlo** (invariante del
  repo: ninguna API pagada sin spend gate). El defecto apunta a
  Helmcode/Kokoro; sin clave en `.env` no genera nada.
- `vendor/launch-video-kit/scripts/analyze-music.mjs` — BPM, fase, arco de
  energía y rejilla de compases de un track. Local, gratis, solo ffmpeg.
- `vendor/launch-video-kit/scripts/loop-music.mjs` — alargar un track hasta la
  duración necesaria sin costura audible. Local, gratis. Verifica sus propias
  costuras: si alguna no cae en silencio, elegir otros dos huecos.
- `vendor/launch-video-kit/src/*` (helpers Remotion: ducking, subtítulos,
  cámara) — **NO aplican al `draft_renderer` three.js actual**. Son referencia
  por si el pipeline migrara a Remotion.

## El orden importa

1. **Voz primero, montaje después.** `gen-voice.mjs` imprime la duración real
   de cada línea en frames; esos números fijan los tiempos de escena. Si
   montas primero, cada toma real descuadra el montaje.
2. **Música después**, elegida por su arco de energía (`analyze-music.mjs`) y
   alargada si hace falta (`loop-music.mjs`).
3. **Cortes** atados a la rejilla de compases del análisis.
4. **Subtítulos al final**, y solo lo que no está ya escrito en pantalla.

## Reglas que se saltan solas

- Un fichero de voz por línea, nunca una toma larga.
- Normalizar la voz (`loudnorm=I=-16:TP=-1.5`): Kokoro entrega a ~-25 dB y la
  música de librería anda sobre -14; sin normalizar la voz no se impone.
- `DUCK.base` no pasa de ~0.85: los tracks masterizados a 0 dB clipean.
- La voz sobre música debe medir aproximadamente lo mismo que la voz sola. Si
  mide más, la música sigue sumando energía y se come la locución.
- Iterar sobre los tiempos, no sobre el contenido: un bucle que indexe un
  array de tiempos más corto tumba el render al quitar un beat.

## Verificar en vez de opinar

Un agente no ve ni oye el vídeo. Todo lo que parece subjetivo tiene un número:

```bash
# la mezcla, por tramos: la voz sobre música debe medir como la voz sola
ffmpeg -hide_banner -ss 27 -t 4 -i out.mp4 -af volumedetect -f null /dev/null

# el pico global debe quedar por debajo de -1 dB
ffmpeg -hide_banner -i out.mp4 -af volumedetect -f null /dev/null

# contact sheet en vez de revisar fotogramas uno a uno
ffmpeg -v error -i f_%d.png -vf "scale=560:-1,tile=5x4" -frames:v 1 sheet.png
```

## Uso rápido

```bash
node vendor/launch-video-kit/scripts/analyze-music.mjs --file <track>
node vendor/launch-video-kit/scripts/loop-music.mjs --file <track> \
  --loop <a>,<b> --target <segundos> --out <salida>
# gen-voice: requiere .env con clave TTS y voiceover.json (ver .env.example
# y voiceover.example.json en el vendor)
```

## Actualizar el vendor

Clone superficial nuevo + `rsync -a --exclude .git --exclude .claude` sobre
`vendor/launch-video-kit/`, revisar `git diff` y correr la prueba de humo
(`analyze-music.mjs` sobre un track existente) antes de commitear.
