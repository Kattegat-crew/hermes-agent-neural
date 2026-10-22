---
name: reel-voice-lipsync
description: "Use when a reel needs correct pronunciation and lip-sync."
tags: [reels, lipsync, voz, tts, elevenlabs, fal, pronunciacion, video]
---

# Voz de marca + lip-sync para reels de personaje IA

Clase de trabajo: darle a un reel de personaje IA (Seedance/Monid u otro
image-to-video) una voz de marca en español con pronunciación CORRECTA y labial
REAL, sin regenerar el video ya pagado.

## La decisión: 3 caminos y cuándo sirve cada uno (lección central 29/08)

| Camino | Pronunciación | Labial | Cuándo usar |
|---|---|---|---|
| Respelling en prompt de Seedance | ❌ no obedece (la voz nativa no es TTS que lee texto) | congelado | nunca como solución |
| **STTS ElevenLabs** (audio→audio) | ❌ **COPIA la pronunciación del audio fuente** (verificado: hereda "trevól"/"Parodise") | no lo toca | solo para cambiar TIMBRE conservando cadencia, cuando la pronunciación fuente ya es buena |
| **TTS desde texto corregido + sync-lipsync** | ✅ el texto lo escribe el agente (respelling funciona) | ✅ re-dibuja labios siguiendo la voz | **ESTÁNDAR** para reels de personaje hablando |

⚠️ La skill `elevenlabs-voice-narration` documentaba el STTS como "la solución para
re-hacer el audio" — es INCORRECTO para corregir pronunciación (user-owned, pendiente
`hermes curator adopt` para enmendar). No repetir ese camino.

## Receta validada (S1 Lucky, 29/08, end-to-end publicado)

1. **TTS desde texto corregido**: `POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id}?output_format=mp3_44100_128`, body `{text, model_id: "eleven_multilingual_v2", voice_settings:{stability:0.5, similarity_boost:0.75, style:0.15, use_speaker_boost:true}}`, header `Accept: audio/mpeg` → MP3 crudo. Respelling: "Paradais", sílabas separadas, números en palabras.
2. **Calzar voz al clip**: `ffmpeg -filter:a "atempo=<ratio>"` — ratio = dur_voz/dur_clip (8.59s→8.10s = atempo 1.0611, imperceptible hasta ~6-8%).
3. **Publicar WAV en URL https pública** (el proveedor descarga el audio; localhost no sirve). Regla vigente: verificar con fetch EXTERNO (web_extract), no curl del propio VPS.
4. **sync-lipsync (fal.ai queue async)**: POST `https://queue.fal.run/fal-ai/sync-lipsync` con `{video_url, audio_url, sync_mode: "cut_off"}` → `request_id` + `status_url`; poll cada 5-10s; al COMPLETED descargar de `response_url`. Duración real: ~5 min (no 2.5 como se estimó). Output viene RECORTADO a la voz (8.10s→8.04s: despreciable en clips de 8s).
5. **Publicar como versión NUEVA** y QA (abajo).

Costo real por escena: **$0.07 sync-lipsync** (fal) + TTS por caracteres (créditos ElevenLabs, céntimos). El clip de video NO se regenera — se aprovecha el ya pagado.

## QA del labial: frames RECORTADOS a la cabeza (falso negativo documentado)

Una grilla de frames de cuerpo completo hace que el modelo de visión diga "boca
congelada/idéntica" AUNQUE el labial esté perfecto (píxel de boca insuficiente).
Procedimiento correcto:
1. Extraer 4-6 frames (`-ss 0.5/1.5/2.5/4.0/5.5/7.0`).
2. Recortar cabeza: `-vf "crop=720:500:0:200"` para 720×1280.
3. `hstack` y preguntar: "¿la boca cambia de forma entre paneles (abierta con dientes / entreabierta / forma O) o es idéntica?".
Con crop se distingue articulación real de boca fija; sin crop, un falso negativo
lleva a re-pagar un lipsync innecesariamente (casi pasó 29/08).

## El camino sin lipsync: TTS calibrado para montaje en CapCut (Goldie Bingo, 30/08 — aprobado "quedó muchísimo mejor")

Cuando Seedance ya animó el labial al ritmo de SU voz nativa, no hace falta re-dibujar
labios: basta calzar la voz de marca al ritmo nativo. Script canónico:
`scripts/fit_voice.py` del repo video-ai-generator (commit 522a1ea). Receta:

1. STT palabra-por-palabra del audio nativo del clip (extraer a 16k mono) = guía del labial.
2. STT del WAV TTS crudo; `atempo = span_tts / span_nativo` (TTS español suele hablar
   12-40% más rápido; S1 Goldie quedó en 0.744, S4 con números largos en 0.609).
3. Pad de silencio INICIAL = onset(1ª palabra nativa) − onset(1ª palabra estirada), para que la
   primera palabra caiga donde la boca empieza (S3 necesitó 1.0s de pad).
4. `apad=whole_dur=<dura_exacta_del_clip>` → el WAV dura lo mismo que el video: en CapCut se
   silencia la pista nativa del mp4 y el WAV se suelta en el 0:00, sin afinar nada.
5. Loudnorm −16 LUFS integrado + highpass 90 Hz. QA automático: delta medio/peor por palabra
   (aceptable ≤0.2s medio; S1 Δ0.02 worst 0.18 → aprobado).
6. Opcional `--mp4`: pre-monta clips/S{n}-vozlimpia.mp4 (video+voz limpia) para que el Admin
   valide el resultado final sin abrir el editor.

**PITFALL GRAVE (causó queixa "se escucha Seedance al fondo")**: en una mezcla con
"ambiente", NO usar el audio del propio clip como fuente del ambiente — arrastra la voz
nativa (bleed) y suena doble. Verificar el entregable con STT: debe transcribir UNA sola
voz. Lo que el editor oye "de fondo" al montar es casi siempre la pista nativa sin silenciar
del mp4 → primero explicar "silencia el audio del clip en CapCut" antes de tocar nada.

## Reglas NO negociables

- **Gate humano para todo gasto** (`.fal-gate.json` firmado por el Admin, 6h; Monid análogo). 'dale/arregla la escena N' = autorización explícita registrable.
- **Galería versionada, JAMÁS borrar**: el Admin quiere ver la evolución (S1.mp4 nativa → S1-vozmarca STTS → S1-lipsync final). Cada versión se agrega, nunca se reemplaza; etiqueta textual de qué es cada una.
- El QA visual se hace ANTES de anunciar el resultado al Admin, no después.
- Verificación externa de URLs publicadas (el curl interno del VPS miente).

## Pitfalls

- `elevenlabs_client.py --stts` del repo puede devolver salida no-audio (bug wrapper): llamar el endpoint directo con `Accept: audio/mpeg` y decodificar con ffmpeg.
- El atempo >1.08 se nota (voz apurada); si la voz excede mucho el clip, recortar texto, no estirar más.
- **PITFALL GRAVE — el `pad` de fit_voice puede ser FALSO (verificado 19-oct-2026, Golden reel2)**: el pad depende de los timestamps de palabra de whisper sobre el audio NATIVO, y whisper puede perder la primera frase → pad inflado (S01 reportó pad=2.48s cuando el habla real empieza en 0.62s; mean delta -0.24s «inaceptable» sin causa real). SIEMPRE cruzar el `pad` del reporte contra `ffmpeg -af silencedetect=noise=-32dB:d=0.25` del clip ANTES de usar el WAV fitado. Si difieren >0.5s, descartar el fit y colocar la voz natural (atempo 1.0) manualmente en el onset real (ver `reel-audio-mixing`, montaje multi-escena con onsets manuales).
- Igual criterio para el atempo: si fit_voice pide atempo <0.7 (voz de marca 30%+ más lenta que la nativa = suena borracha), NO estirar; colocar la voz natural en el onset nativo y verificar con STT del master final.
- `sync-lipsync` v2 puede no existir/NoFound: el modelo base `fal-ai/sync-lipsync` verificado vivo 29/08.
- El wrapper de Monid (`monid-client.py`) no acepta params de audio/lipsync — la corrección de voz SIEMPRE es capa posterior, no parámetro de generación.
- El output de lipsync recorta el video a la duración de la voz: para tails sin diálogo, concatenar el tail desde el clip original en CapCut.

## Referencias

- **Herramienta principal**: `scripts/fit_voice.py` (repo video-ai-generator) — calibración TTS↔labial genérica por proyecto (`--project --scenes S1..S6 --voice-substr goldie --mp4`).
- Scripts históricos 29/08: `/tmp/tts_s1.py` (TTS directo), `/tmp/lipsync_s1.py` (submit+poll fal queue).
- Skills hermanas (user-owned, NO editar sin adopt): `elevenlabs-voice-narration` (timbre/STTS), `video-tts-pronunciation-fix` (respelling), `video-ai-generator` (repo/pipeline), `scene-consistency-qa` (QA de stills).


<!-- absorbido de creative/lucky-reel-voice-script (censo 2026-09-24) -->
# Guion de voz para reels con lip-sync pos-generado


Cadena aprobada (Lucky/Bingo Millonario, 29/08): `Seedance mini clip → fal-ai/sync-lipsync con WAV ElevenLabs`. El modelo no obedece visemas ni respeta la voz de marca (refoniza); el labial se hace sobre los píxeles DESPUÉS.

## Consecuencias para el guion de voz (mi lens, Content)


1. **El clip se recorta a la duración del audio** (sync-lipsync). Si una línea TTS mide más que la escena del storyboard, la escena final queda cortada o hay que regenerar TTS más rápido/rasurado. Regla: medir cada línea con Voz_Lucky ANTES de dar por aprobado un guion de video; presupuestar ≥1s de aire al final para gestos de cierre (saludo, "¡Suban!").
2. **Nada de música pedida al generador** — el Admin pone música en edición. Los prompts piden SFX diegéticos nombrados explícitamente (pasos sobre pavimento mojado, ruedas de maleta, ambiente terminal) y niegan música ("no music, no soundtrack, no singing").
3. **Ritmo del habla = ritmo del reel**: medir con Voz_Lucky real — **~2.2 palabras/seg** (medido por Sindri 29/08; no fiarse de estimaciones de 2.7). Digits se leen expandidos ("53" = "cincuenta y tres"). Las cinco líneas del guion maestro deben caber en sus tramos del §11 con ±0.5s. Si una línea no cabe, primero `--speed 1.1–1.3` en ElevenLabs (Sindri validó L3 a 1.3 → 6.5s), y solo si aún no cabe se acorta la FRASE, nunca la escena.
4. **Voz de marca siempre ElevenLabs** (Voz_Lucky), nunca la nativa de Seedance como plan A. La nativa solo como cadencia/referencia.

## Plantilla de prompt motion (lo que le toca a Content refinar por escena)


- Identity/style locks + acción + registro ("host, not performer") + SFX diegéticos + negaciones (no text, no morphing, no extra characters, no music).
- NO incluir órdenes de visemas (ineficaces en esta cadena).
- Entregar al lip-sync una cara claramente hablando: "talking directly to camera, mouth open mid-word".

Referencia: workspaces bragi/sindri (`PROMPT_MOTION_SC1_v2_lipsync.md`, `ANALISIS_GUION_IMAGENES_LUCKY_bragi.md`) y skill de pipeline de Sindri `scene-keyframe-qa-lipsync`.
