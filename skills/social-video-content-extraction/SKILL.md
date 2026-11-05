---
name: social-video-content-extraction
description: Use when the Admin shares a Facebook/Instagram/TikTok/X reel or post whose content is INSIDE the video (on-screen lists, captions, tutorials) and must be transcribed or added to a ticket. Web extractors and remote browser get blocked; the working path is yt-dlp + ffmpeg frames + vision_analyze.
---

# Extracción de contenido desde videos sociales (reels/posts)

## Cuándo
El Admin manda un link tipo `facebook.com/share/r/...`, reel de IG, TikTok o X y pide
"agrega esta lista" / "transcribe esto". El contenido vive EN EL VIDEO, no en el texto
del post. `web_extract` NO sirve (FB bloquea extractores: devuelve login/captcha) y el
navegador remoto puede no responder. Pipeline verificado 27-oct con un reel de FB (91K vistas).

## Pipeline (verificado end-to-end)
1. **Descargar** el video directamente (yt-dlp resuelve los links `share/r/` de FB sin
   resolver el enlace primero):
   `yt-dlp -f mp4 -o /tmp/reel.mp4 "URL"` — si falla con la URL de share, resolver el
   link real y reintentar con el `facebook.com/<page>/videos/<id>`.
2. **Duración:** `ffprobe -v error -show_entries format=duration -of csv=p=0 /tmp/reel.mp4`
3. **Frames por segmento** (no todo el video de golpe): para la sección con la lista,
   `ffmpeg -y -v error -ss <start> -i /tmp/reel.mp4 -vf fps=3-4 /tmp/frames/seg_%02d.png`
4. **vision_analyze** frame por frame pidiendo transcripción EXACTA (los ítems de listas
   aparecen progresivamente: los primeros frames tienen los primeros ítems, los últimos
   los finales). Ignorar lo que se superpone con el fondo, pero transcribir fielmente
   incluso con typos del original (anotarlos).
5. **Verificar completitud contra el título** (ej. "20 cosas" → contar 20). Si faltan los
   últimos ítems, extraer densamente el tramo final (`-ss <end-3s> fps=4`): los creadores
   dejan la lista completa en pantalla el último segundo.

## Salida
Devolver la lista al Admin en el chat y, si pidió agregarla a un ticket de Discord,
seguir `hermes-secrets-v022x-ops` (token import-only + threads de foro archivados).
Formatear la lista agrupada por bloques temáticos y citar fuente + fecha + verificación.

## Pitfalls
- Facebook: ni `web_extract` ni curl ni el navegador remoto obtienen el contenido —
  no perder tiempo, ir directo a yt-dlp.
- Transcribir con `vision_analyze` en 2-3 tandas cortas de frames, no un frame gigante:
  el OCR de listas densas se pierde si el frame está a media transición.
- Contar los ítems extraídos vs el número del título antes de entregar (la sesión del
  27-oct dejó 2 ítems sin capturar en la primera pasada y los recuperó del tramo final).
