---
name: video-frame-verification
description: "Verificar claims de demos en video extrayendo fotogramas."
version: 1.0.0
author: curator-ragnar
category: vision
metadata:
  hermes:
    tags: [vision, video, evidencia, verificacion, social]
    related_skills: [image-text-verification, web-research-briefing, ingest-pipeline]
---

# Verificación de demos en video (fotogramas como evidencia)

**Cuándo:** un video de terceros (demo en tuit, reel, screen-recording) es la fuente de un dato que vas a reportar o guardar y el dato vive EN PANTALLA (scores, latencias, métricas de UI, pasos de una app). El texto del post y la miniatura NO son evidencia de lo que muestra el video: pueden resumir, exagerar o contradecir la pantalla.

## Cadena (probada 17/09/2026)

1. **Descargar el mp4.** Para X: `api.fxtwitter.com/{user}/status/{id}` con UA Chrome da `media` con el mp4 en varias calidades — tomar la más alta. (Vía fxtwitter, no fixupx: 0 bytes en este host.)
2. **Extraer fotogramas distribuidos.** `ffmpeg -i demo.mp4 -vf "select='eq(n\,N)'" -vframes 1 f_NN.png` en varias posiciones, proporcional a la duración (en un clip de ~45 s funcionó n=10/40/80/120). NO confiar en una sola posición ni en la miniatura.
3. **Verificar cada dato con el protocolo de 2 pasadas** de `image-text-verification` SOBRE EL FOTOGRAMA (no sobre la miniatura): pasada completa + recorte ampliado de la zona del dato. IDs/scores/latencias son exactamente donde la visión rellena con algo plausible.
4. **Guardar como evidencia** los fotogramas que sostienen el dato: `brain/ingestas/<tipo>/assets/<slug>/` (ruta mapeada en brain/folder-maps/brain.md). En el entregable citar el fotograma (p. ej. f_04.png) y declarar «verificado en fotogramas».
5. En la ingesta/reporte separar lo que MUESTRA la pantalla de lo que el autor DECLARA (self-reported). Lo declarado va marcado como no verificado.

## Pitfalls

- **Ceder a la miniatura:** es un fotograma elegido por la plataforma, no necesariamente donde vive el dato.
- **Un solo fotograma "por si acaso":** los datos aparecen en momentos distintos (un score a los 10 s, la latencia a los 30 s).
- **Reportar el claim del tuit como verificado** porque el video "lo acompaña": el video puede mostrar otra cosa.
- **No guardar los fotogramas:** sin evidencia en disco el claim queda tan incierto como leerlo del texto.
- **Videos largos (>2 min)** con el dato en momento desconocido: extraer primero ~1 fps a baja resolución para localizar el timestamp, luego recortar el fotograma bueno en alta calidad.

## Referencias

- `references/caso-riley-viral-analyzer-17sep2026.md` — caso completo (demo de analizador de viralidad en vivo; qué dato se confirmó en qué fotograma).
