---
name: video-post-content-analysis
description: Use when a social video or post link needs deep analysis.
---

# Video Post Content Analysis

Analiza un video corto o post social (reel de Instagram, TikTok, video de X) que llega como link suelto: descarga el medio real, transcribe lo visible, lee métricas públicas SIN inventar nada, persiste la ingesta en la bodega de la agencia y entrega el informe en chat.

## Pipeline canónico (en este orden)

1. **Sondear metadatos sin login**: `curl -A "facebookexternalhit/1.1" <url>` y leer `og:url` (handle real del autor), `og:description` y `og:image`. Nunca asumir el autor por el nombre del canal mostrado.
2. **Descargar el medio con yt-dlp + cookies** (cookies de IG en `/opt/data/drafts/ig_cookies.txt`): `yt-dlp --cookies <file> -o "/tmp/ig_%(id)s.%(ext)s" --write-info-json <url>`. El info-json trae likes, comentarios, fecha, duración y resolución. Para tuits de X usar primero `api.fxtwitter.com` (receta en la ingesta de tuits).
3. **Rejilla de frames con ffmpeg**: 1 frame cada ~4 s. Si el contenido relevante es una UI/overlay (comandos, interfaces de app), RE-EXTRAER bisecando a resolución de segundo alrededor del tramo: una cadencia fija se salta el overlay (verificado 21-sep-2026, el overlay de comandos slash solo existía en ~2 frames de 80 s).
4. **Transcribir con vision_analyze** frame por frame pidiendo SIEMPRE "transcribe literalmente todo texto visible". Cruzar texto entre frames: un comando ilegible en un frame suele ser legible en otro.
5. **Métricas con regla de honestidad**: solo lo que el info-json exponga. Instagram NO expone vistas públicas: decirlo, no estimar. Citar la fecha de lectura de las métricas.
6. **Persistir** con `/opt/data/scripts/ingesta_externa.py` (--tipo x|post|tiktok|repo; un reel de IG va como `tiktok`, tabla catch-all de videos cortos). Verificar la fila en la wiki Outline y el .md en brain/ingestas ANTES de declarar "guardado".

## Formato del informe en chat

- Título: **tipo · plataforma** — url corta.
- ⭐ relevancia 1-5 · **Resumen** (2-3 líneas con tesis y hook) · **Key takeaway / herramienta** · **Métricas** con fecha de lectura · **Acción sugerida** para los módulos (Content, Ads, Connect).
- Cierre "Guardado en wiki + brain/ingestas ✅" solo tras re-leer la fila.

## Pitfalls

- No leer métricas del HTML de la página: IG ofusca. La fuente es el info-json de yt-dlp o la API del proveedor.
- No promediar ni estimar vistas. "No disponible públicamente" es una respuesta válida y preferible a inventar.
- Texto parcialmente legible en un frame = re-extraer a resolución de segundo, no conformarse.
- El comando/nombre de la herramienta mostrada en pantalla es parte del hallazgo: identificarla y anotarla.

## references

- `references/video-extraction-recipes.md` — comandos exactos (og, yt-dlp, ffmpeg, ingesta_externa.py), formato de fila wiki y caso de referencia DdXljuvo6rq del 21-sep-2026.


---

## Procedencia

Absorbido por F3 el 20260923-055337 desde la autoskill `data/skills/video-post-content-analysis` (sin versión en git hasta hoy).
El procedimiento se conserva íntegro; el paraguas `video-reel-pipeline` es su punto de entrada.

