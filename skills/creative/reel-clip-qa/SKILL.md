---
name: reel-clip-qa
description: "Use when approving or debugging a Seedance reel clip."
version: 1.0.0
author: Ragnar (NeuralCrew Labs)
license: MIT
category: creative
tags: [reels, seedance, monid, qa, stt, cdn, prompts]
---

# Reel Clip QA — Seedance/Monid clips: STT verification, CDN cache truth, and dialogue prompts

QA estándar para clips de reel generados con Seedance 2.0 (Monid) y su publicación
en reels.neuralcrewlabs.com. Nacido del lote Pacho 07-08/09 (3 runs, una toma muda,
CDN sirviendo el video viejo). Cero afirmaciones sin evidencia: todo se verifica con
STT, hashes y lo que el CDN realmente sirve.

## When to Use

- Un clip Seedance/Monid terminó (COMPLETED) y hay que aprobarlo ANTES de publicarlo o de lanzar la siguiente toma.
- El usuario reporta "no habla / sin voz / se ve mal" en un clip publicado.
- Se van a lanzar nuevas tomas de una escena (lote por gate) y hay que conciliar gasto real vs estimado.
- Se sube/regenera un asset en el portal y hay que garantizar que el usuario vea el NUEVO contenido.

## Regla de oro de transparencia (gasto)

**NUNCA afirmar cuántos videos se pagaron sin LISTAR los runs reales en la API de Monid**
(`GET /v1/runs` → filtrar por fecha). El historial propio (pollers, procesos background) miente
por descuidos de relanzamiento; la API no. Reclamo de Jonathan 08/09: "pura basura socio, muy
mentirosito" — afirmé "fue UN solo video" y eran 2 ($1.82). Desde entonces: listar runs
primero, luego narrar. Reportar SIEMPRE costo real por run vs estimado del lote.

**Anti-doble-cargo:** antes de cada submit, listar runs ACTIVOS (PENDING/QUEUED/RUNNING) del
mismo keyframe/slug y abortar si ya existe (`has_active_run()` en run_pacho.py). Un submit
fallido (400) NO cobra, pero un relanzamiento en paralelo SÍ — jamás relanzar mientras hay
un run vivo, ni "probar manual" mientras el script corre en background.

## QA de un clip terminado (orden obligatorio)

1. **ffprobe**: duración, resolución, fps, ¿tiene stream de audio?
2. **STT palabra-por-palabra** (faster-whisper small, es, beam 5) del audio extraído.
   - Transcribe la locución completa → el clip HABLA. Comparar contra el DIALOGUE del prompt.
   - Transcribe solo ruido/hallucination tipo "Subtítulos realizados por la comunidad de
     Amara.org" → el clip está MUDO (el STT hallucina ese slogan con silencio; es el marcador
     clásico de audio sin habla).
   - Ejecutarlo en TODAS las tomas, no solo la oficial. El usuario puede preguntar por cualquiera.
3. **QA visual con grilla**: 6 frames (ffmpeg -ss t -frames:v 1, t=1,3,5,7,9,11, scale 360)
   → montar grid PIL 3x2 → `vision_analyze` con checklist (personaje consistente, caminata,
   props, entorno, texto inventado, glitches). Nota: vision_analyze a veces responde
   "text input only" → reintentar con JPEG -q:v 3.
4. **Veredicto por toma** con defectos concretos (ej. marquee «GOLDY» vs «GOLDIE», brazo
   desunido en 1 frame, GG quemado) y una recomendación única.

## Cómo forzar la locución (la toma muda)

Seedance 2.0 puede IGNORAR el bloque DIALOGUE si va a mitad del prompt: el resultado es un
clip con ambiente sin voz (pasó $0.91 en Pacho S1 toma 1).

**Fix probado (regen 01M1ZJ4E4RPEVJZ312WCJA0CAW habló):** bloque AUDIO REQUIREMENT AL FRENTE
del prompt, antes de DIALOGUE:

```
AUDIO REQUIREMENT (MANDATORY):
The final video's audio track MUST contain a single warm adult narrator voice speaking
the ENTIRE DIALOGUE text below, in Spanish, starting within the first second of the clip.
A silent video or a video with only ambient sound is an INCOMPLETE and REJECTED result.
No music. No extra voices. No background noise.

DIALOGUE (Spanish. Native generated voice-over narration — ...):
"..."
```

La locución es estocástica: misma escena, mismas duraciones → una toma muda y otra hablando.
Por eso el STT de cada toma es obligatorio antes de publicar.

## Guardar cada toma bajo un nombre ÚNICO (nunca sobrescribir)

El poller de regeneración descargó sobre `S1-seedance.mp4` y BORRÓ la toma 1 que vivía en
ese archivo. La toma sobrevivió solo porque el video_url del run COMPLETED sigue vivo en el
TOS (~24h). Reglas:

- Filename de descarga SIEMPRE con run id o marca de toma: `S1-<runid-suffix>.mp4` o
  `S1-tomaN-<desc>.mp4`. Nunca un nombre fijo para resultados distintos.
- Si una toma se perdió localmente, recuperarla del run: `GET /runs/{rid}` →
  `output.content.video_url` → curl antes de que expire (24h).
- Guardar `state.json` por toma: run_id, costo real, transcripción STT, veredicto QA.

## CDN cache: el usuario ve lo que Cloudflare sirve, no lo que subiste

reels.neuralcrewlabs.com está tras Cloudflare con `max-age=14400` (4h). Sobrescribir un
asset con el MISMO nombre deja al usuario viendo el clip VIEJO hasta 4h aunque el origen
tenga el nuevo. Además Cloudflare también cachea 404s de assets recién subidos.

**Diagnóstico (cuando el usuario dice "no lo veo" o "sigue sin voz"):**
1. Descargar el asset POR EL CDN (curl -A "Mozilla/5.0 Chrome/126") → md5sum → comparar
   contra el archivo de origen en prod. Si difieren: el CDN está sirviendo la copia vieja.
2. `curl -sI` → `cf-cache-status: HIT` + `age: N` + `last-modified` confirman caché.
3. Para audio/voz: STT del descargado del CDN.

**Fix inmediato sin purge:** renombrar a un nombre nuevo (`S1-regen-voz.mp4`) y publicar ese
URL — una URL nunca servida no tiene copia en caché. Sacar el nombre viejo del listado.

**Purge quirúrgico vía API:** requiere token Cloudflare con permiso **Zone → Cache Purge**.
Al 08/09 NINGUNO de los 2 tokens del Vaultwarden lo tiene (POST /zones/{id}/purge_cache →
403 code 10000 "Authentication error"; el token NeuralCrew sí lista zonas pero solo tiene
#query_cache:read/edit). Pendiente: Jonathan crea token con Cache Purge y lo guarda en
Vaultwarden. Mientras tanto, cache-buster rename es el método canónico.

## Verificación del portal (misma noche)

Después de publicar un clip: regenerar el portal (gen-portal-spa.py) → scp → y verificar en
navegador real que la sección Clips lista la toma nueva. Jonathan revisa el PORTAL, no el
workspace local — "no la veo en la página" = el portal no se regeneró o el CDN sirve viejo.

## Pitfalls

- **"fue un solo video" sin listar runs** = el error #1 de esta noche. La lista de runs de la
  API es la única verdad sobre el gasto.
- **DIALOGUE a mitad de prompt** = riesgo de clip mudo. AUDIO REQUIREMENT al frente.
- **Descargar sobre filename existente** = pérdida silenciosa de la toma anterior.
- **Confiar en lo que hay en prod** = el CDN puede servir otra cosa. Verificar el CDN.
- **Seedance Mini: NO mezclar first_frame + reference_image** (400 "cannot be mixed") —
  solo first_frame + bloque CHARACTER para continuidad.
- **Respelling en Seedance no corrige pronunciación** de nombres propios («casista» en vez
  de «cacique») — el STT lo detecta; si molesta, va a re-dubbing ElevenLabs (fit_voice),
  no a regenerar el clip.
- **Texto inventado por el modelo** (plato «PACHO» en el pecho, marquee «GOLDY»): revisar
  en la grilla; si rompe marca, es criterio de descarte de toma.

## Verification

- Lista de runs de Monid conciliada con lo que se afirma haber pagado.
- STT de CADA toma publicada, pegado en la respuesta (o en state.json).
- md5 del CDN = md5 del origen para todo asset publicado esta sesión.
- Portal regenerado + verificado en navegador real (desktop + móvil 390px).
- Costo real del lote reportado (suma de cost.value de los runs).
