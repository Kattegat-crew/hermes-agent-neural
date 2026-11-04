---
name: video-transcript-extraction
description: Use when an embedded video needs a transcript, no paid ASR.
---

# Transcribir videos embebidos vía captions del player (sin ASR pagado)

## Cuándo
- Link de cliente/Admin con video embebido (Vimeo y similares) y pedido de "ver el video".
- Videos largos: la vía whisper (`media/audio-video-transcription`) exige chunks de ≤50 min, mínimo ~2 min y consume API pagada; las pistas de subtítulos del player son gratis, instantáneas y sin límite de duración (verificado con un video de 2h47m).

## Decisión
1. Player Vimeo → receta de abajo (VERIFICADA 16-sep-2026).
2. Otro player (Wistia, Brightcove, Mux, JW) → mismo patrón: HTML del player → lista de text tracks → VTT firmado. Etiquetar la variante como NO verificada al usarla.
3. Sin subtítulos disponibles → recién ahí caer a whisper por chunks de 50 min.

## Receta Vimeo (end-to-end probada)
1. Del HTML de la página anfitriona extraer id y hash: regex `player\.vimeo\.com/video/(\d+)` y `h=([0-9a-f]+)` (el `h` también vive en el src del iframe). Landings de marketing suelen traer varios ids: tomar el del iframe principal.
2. GET del PLAYER PAGE `https://player.vimeo.com/video/{id}?h={hash}` con UA de Chrome completa y `Referer: https://{dominio-anfitrion}/` (curl `-L -sS -w '%{http_code}'`). El HTML trae `window.playerConfig` embebido con `request.text_tracks[]`.
3. `text_tracks[]` da la pista por idioma (es/en) con URL `https://captions.vimeo.com/captions/{track_id}.vtt?expires=...&sig=...`: firmada y CON VENCIMIENTO → descargarla INMEDIATAMENTE, en la misma llamada, no guardar la URL para después.
4. Parsear el VTT con `scripts/vtt_to_text.py` (dedupe de cues repetidos + marcas [HH:MM] por minuto).
5. Analizar el texto como se analiza un video visto: declarar en la respuesta que se trabajó desde la transcripción (diagramas/pantallas no se ven) y citar minutos concretos.

## Pitfalls
- URL de captions muere por `expires`/`sig`: descarga + parseo en el mismo paso.
- El endpoint JSON `/video/{id}/config` existe pero en la sesión de verificación devolvió respuestas cortas sin cookies de sesión; el player page es el camino confirmado. Detalle en references/.
- Sin `h` correcto en videos con privacy hash → respuesta vacía o negada.
- Si la página anfitriona es SPA y no renderiza el iframe en HTML crudo, usar `browser_exec` con `js()` para leer el DOM.

## Referencias
- `references/agencia-productizada-vimeo.md` — caso real verificado (17-sep-2026): página anfitriona, forma de playerConfig, URLs de captions, gotchas y biblioteca condensada del video analizado.

## Scripts
- `scripts/vtt_to_text.py` — VTT → texto plano: dedupe de cues repetidos, marcas [HH:MM], reflow por minuto. `python3 vtt_to_text.py <file.vtt> [out.txt]`.
