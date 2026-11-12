---
name: video-reel-pipeline
description: "Use when producing an AI video reel end to end."
version: 2.0.0
author: NeuralCrew
license: Apache-2.0
platforms: [linux, macos]
tags: [reel, video, ia, pipeline, voz, lipsync, fal, produccion]

---

# Video Reel Pipeline

## Propósito y Alcance
Habilidad consolidada de clase que centraliza los flujos de:
- `ai-video-model-costing`
- `ai-video-pricing-research`
- `akari-video-editing`
- `audio-video-transcription`
- `character-sheet-locking`
- `cunas-de-audio-campana`
- `guion-replica-voz-referencia`
- `reel-audio-mixing`
- `reel-brand-voice-dubbing`
- `reel-clip-qa`
- `reel-gallery-deploy`
- `reel-performance-analytics`
- `reel-pipeline`
- `reel-portal-protocol`
- `reel-produccion-pagina`
- `reel-voice-lipsync`
- `scene-consistency-qa`
- `video-ai-generator`
- `video-ai-provider-integration`
- `video-frame-verification`
- `video-reel-pipeline`
- `video-transcript-extraction`

- `analisis-video-post-externo`

- `reel-preproduccion`

- `reel-stills-production`

- `gate-de-gasto-media`

## Arquitectura y Protocolos
Esta skill opera como despacho unificado. El detalle procedural y gotchas específicos de cada caso se encuentran preservados en:
`references/`

## QA de video con input nativo
- `scripts/qa_gate.py` — gate determinista, coste 0: frames vacíos por segundo, ventanas
  toleradas con `--allow`, exit 0/1/2 (2 = no pudo medir, nunca pase).
- `scripts/video_native_qa.py` — manda el mp4 completo al VLM junto al guion, contrato JSON de
  7 claves, techo de llamadas (`--max-passes`, 2 por defecto), cache por hash del artefacto y
  exit 0/1/2 fail-closed. La decisión se toma sobre la evidencia declarada (voids, collisions,
  narration_sync, legibility, pacing), no sobre el flag `passed`.
- Orden obligatorio: gate determinista primero, VLM después. Si el determinista falla, no se
  gasta un token.
- Detalle, evidencia medida, límites y política de pasadas: [references/qa-video-nativo.md](references/qa-video-nativo.md)

## Lecciones duras (pagadas en producción)

- **El entregable viaja en el mismo mensaje que el «listo».** Decir «el video está hecho» sin `MEDIA:/ruta` obliga al humano a pedirlo («A ver el vídeo») y convierte una entrega en dos turnos. Si el resultado es un archivo, la frase de cierre y el adjunto van juntos, siempre.
- **La estimación de tiempo se desglosa, no se redondea.** El coste real de un corte es `frames/fps medido` (render) + mezcla + encode + QA, y sale de los fps que ya imprimió el render anterior. Decir «14 minutos» cuando el ciclo medido son 5 es una cifra inventada aunque suene prudente: se da el desglose o no se da nada.
- **Voz de reels de campaña (Golden/Lucky) = SIEMPRE ElevenLabs, NUNCA kokoro.** Corrección dura del Admin (12-nov-2026): para piezas de marca la voz es la del personaje ya contratada en ElevenLabs (`ELEVENLABS_API_KEY` del `.env` del repo, modelo `eleven_multilingual_v2`) — Goldie `qWWAqFomnJ99VwQLREfT` ("Voz-Goldie"), Lucky `lWweqHoPFkas8ijavnVj` ("Lucky final") — cubierta por el plan ($0). Kokoro/nan (ver `voz-es-coste-cero-nan`) es SOLO para drafts internos sin marca; proponerlo para un reel de campaña es un error que ya costó un reproche.
- **Catálogo de video i2v de fal (precios verificados 12-nov-2026):** `fal-ai/veo3*` está DEPRECADO. Vigentes: Kling v3 Pro y Standard image-to-video $0.14/s, Kling 4.0 $0.157/s (3–30 s, multi-shot), Kling AI Avatar v2 Pro $0.115/s (lipsync con audio propio), MiniMax H3 Max i2v $0.035/s, Wan 3.0 i2v $0.05/s. Estrategia de mezcla por reel: planos hero del personaje en Kling v3 Pro, planos de ambiente/local en Wan 3.0 o H3 Max (4× más barato). Ver `references/reel-campana-video-modelos-voz.md`.
- **"Gente real" en video IA tiene solo dos vías:** animar la foto real de la persona (image-to-video con su foto) o avatar-lipsync con su audio (Kling Avatar / Omnihuman). Ambas exigen consentimiento de uso de imagen — en publicidad de apuestas, doblemente sensible. Sin foto + permiso, lo único posible es gente fotorrealista generada.

## Casos de Uso Disponibles
- **ai-video-model-costing**: Ver [references/ai-video-model-costing.md](file:///root/hermes-agent-legacy-docker/skills/core/video-reel-pipeline/references/ai-video-model-costing.md)
- **ai-video-pricing-research**: Ver [references/ai-video-pricing-research.md](file:///root/hermes-agent-legacy-docker/skills/core/video-reel-pipeline/references/ai-video-pricing-research.md)
- **akari-video-editing**: Ver [references/akari-video-editing.md](file:///root/hermes-agent-legacy-docker/skills/core/video-reel-pipeline/references/akari-video-editing.md)
- **audio-video-transcription**: Ver [references/audio-video-transcription.md](file:///root/hermes-agent-legacy-docker/skills/core/video-reel-pipeline/references/audio-video-transcription.md)
- **character-sheet-locking**: Ver [references/character-sheet-locking.md](file:///root/hermes-agent-legacy-docker/skills/core/video-reel-pipeline/references/character-sheet-locking.md)
- **cunas-de-audio-campana**: Ver [references/cunas-de-audio-campana.md](file:///root/hermes-agent-legacy-docker/skills/core/video-reel-pipeline/references/cunas-de-audio-campana.md)
- **guion-replica-voz-referencia**: Ver [references/guion-replica-voz-referencia.md](file:///root/hermes-agent-legacy-docker/skills/core/video-reel-pipeline/references/guion-replica-voz-referencia.md)
- **reel-audio-mixing**: Ver [references/reel-audio-mixing.md](file:///root/hermes-agent-legacy-docker/skills/core/video-reel-pipeline/references/reel-audio-mixing.md)
- **reel-brand-voice-dubbing**: Ver [references/reel-brand-voice-dubbing.md](file:///root/hermes-agent-legacy-docker/skills/core/video-reel-pipeline/references/reel-brand-voice-dubbing.md)
- **reel-clip-qa**: Ver [references/reel-clip-qa.md](file:///root/hermes-agent-legacy-docker/skills/core/video-reel-pipeline/references/reel-clip-qa.md)
- **reel-gallery-deploy**: Ver [references/reel-gallery-deploy.md](file:///root/hermes-agent-legacy-docker/skills/core/video-reel-pipeline/references/reel-gallery-deploy.md)
- **reel-performance-analytics**: Ver [references/reel-performance-analytics.md](file:///root/hermes-agent-legacy-docker/skills/core/video-reel-pipeline/references/reel-performance-analytics.md)
- **reel-pipeline**: Ver [references/reel-pipeline.md](file:///root/hermes-agent-legacy-docker/skills/core/video-reel-pipeline/references/reel-pipeline.md)
- **reel-portal-protocol**: Ver [references/reel-portal-protocol.md](file:///root/hermes-agent-legacy-docker/skills/core/video-reel-pipeline/references/reel-portal-protocol.md)
- **reel-produccion-pagina**: Ver [references/reel-produccion-pagina.md](file:///root/hermes-agent-legacy-docker/skills/core/video-reel-pipeline/references/reel-produccion-pagina.md)
- **reel-voice-lipsync**: Ver [references/reel-voice-lipsync.md](file:///root/hermes-agent-legacy-docker/skills/core/video-reel-pipeline/references/reel-voice-lipsync.md)
- **scene-consistency-qa**: Ver [references/scene-consistency-qa.md](file:///root/hermes-agent-legacy-docker/skills/core/video-reel-pipeline/references/scene-consistency-qa.md)
- **video-ai-generator**: Ver [references/video-ai-generator.md](file:///root/hermes-agent-legacy-docker/skills/core/video-reel-pipeline/references/video-ai-generator.md)
- **video-ai-provider-integration**: Ver [references/video-ai-provider-integration.md](file:///root/hermes-agent-legacy-docker/skills/core/video-reel-pipeline/references/video-ai-provider-integration.md)
- **video-frame-verification**: Ver [references/video-frame-verification.md](file:///root/hermes-agent-legacy-docker/skills/core/video-reel-pipeline/references/video-frame-verification.md)
- **video-reel-pipeline**: Ver [references/video-reel-pipeline.md](file:///root/hermes-agent-legacy-docker/skills/core/video-reel-pipeline/references/video-reel-pipeline.md)
- **video-transcript-extraction**: Ver [references/video-transcript-extraction.md](file:///root/hermes-agent-legacy-docker/skills/core/video-reel-pipeline/references/video-transcript-extraction.md)
- **analisis-video-post-externo**: analizar un reel o post social externo que llega como link: descarga del medio, transcripcion por vision, metricas con regla de honestidad y persistencia en la ingesta — ver [references/analisis-video-post-externo.md](file:///root/hermes-agent-legacy-docker/skills/core/video-reel-pipeline/references/analisis-video-post-externo.md)
- **reel-version-usuario-comparacion**: el Admin edita nuestro master y lo entrega por Drive: comparación frame a frame (mapa de timeline por correlación normalizada), ASR word-level del nuevo audio y reparación de subtítulos quemados con placas limpias del clip original, respetando su edición como base y el alcance acotado que indique — ver [references/reel-version-usuario-comparacion.md](file:///root/hermes-agent-legacy-docker/skills/core/video-reel-pipeline/references/reel-version-usuario-comparacion.md)
- **reel-preproduccion**: etapa pre-gasto del reel a coste cero: lint de guiones, brief de prompts y render draft three.js — ver [references/reel-preproduccion.md](file:///root/hermes-agent-legacy-docker/skills/core/video-reel-pipeline/references/reel-preproduccion.md)
- **reel-stills-production**: stills pagados de un reel via fal con dry-run, gate de gasto firmado por humano y verificacion visual — ver [references/reel-stills-production.md](file:///root/hermes-agent-legacy-docker/skills/core/video-reel-pipeline/references/reel-stills-production.md)
- **gate-de-gasto-media**: protocolo obligatorio antes de lanzar CUALQUIER generacion que consuma saldo (fal, monid, elevenlabs): autorizacion, gate y verificacion del artefacto — ver [references/gate-de-gasto-media.md](file:///root/hermes-agent-legacy-docker/skills/core/video-reel-pipeline/references/gate-de-gasto-media.md)
- **qa-video-con-modelos**: escalera de QA barata→cara (qa_gate.py determinista → manifiesto de layout → VLM glm5.3-flash → arbitro qwen3.8-max), tokens medidos por pasada y maximo de pasadas por corte; el mp4 puede entrar nativo al VLM sin extraer frames, con contrato estricto de veredicto y decisión sobre la evidencia declarada (no sobre `passed`) — ver [references/qa-video-con-modelos.md](references/qa-video-con-modelos.md) y [references/qa-video-nativo.md](references/qa-video-nativo.md)
- **voz-es-coste-cero-nan**: voz ES a coste cero sin gate: kokoro (em_alex/ef_dora) + whisper word-level timestamps via nan.builders, verificado 12-nov-2026; fallback tts_aligned.py ElevenLabs /with-timestamps con gate — ver [references/voz-es-coste-cero-nan.md](references/voz-es-coste-cero-nan.md)
- **film-determinista-canvas**: motor de film 9:16 sin IA de video paga: canvas 2D + puppeteer-core + ffmpeg, cue sheet colgado de la voz, fuentes DM embebidas, ducking −16 LUFS, N renders paralelos como procesos background — ver [references/film-determinista-canvas.md](references/film-determinista-canvas.md)
- **reel-campana-video-modelos-voz**: producción de reels de campaña casino (lote canónico `lote-preparado.json` como SSOT, voces ElevenLabs por marca, catálogo/precios de video i2v en fal con estrategia de mezcla hero/ambiente, reglas de fotos de sedes como referencia-only y logo compuesto, Codex CLI en host DEV para keyframes) — ver [references/reel-campana-video-modelos-voz.md](references/reel-campana-video-modelos-voz.md)
