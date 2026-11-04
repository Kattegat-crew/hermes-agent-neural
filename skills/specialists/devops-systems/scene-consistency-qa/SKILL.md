---
name: scene-consistency-qa
description: "Use when QAing character consistency in AI scene stills."
tags: [qa, consistencia, personaje, reels, vision, seedance]
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [video, reels, qa, personaje, consistencia]
    category: creative
---

# Scene Consistency QA Skill

QA gate y estándar de generación para los stills de escenas de un reel con
personaje/mascota: asegura que cada imagen de escena mantenga la identidad del
personaje (anatomía, accesorios, textura, dirección de acción) antes de gastar en
image-to-video. No reemplaza el pipeline de generación (reel-pipeline /
video-ai-generator); se ejecuta ENTRE la generación de imágenes y el despacho de clips.

## When to Use

- Un reel con personaje recurrente va a animarse escena por escena (Seedance/Monid
  u otro image-to-video) y las imágenes de escena ya existen o se van a generar.
- El cliente o el equipo entrega un set de stills y hay que aprobarlas antes de pagar.
- Se va a definir el "estándar" de escenas de una campaña para producción en serie.

## Prerequisites

- Imagen HERO del personaje aprobada por el humano (es el CANON; toda divergencia
  se mide contra ella, nunca contra otra escena).
- Guion con reglas de escena (qué textos van a post, props prohibidos).
- Acceso a visión: `vision_analyze` o API directa del proveedor (ver references).

## How to Run

1. Analizar CADA imagen con visión (nunca solo la primera): identidad del personaje,
   maleta/accesorios, entorno, textos transcritos exactos, cámara, defectos.
2. Anotar veredicto por imagen (apta / ajustable / regenerar) en un doc QA con tabla.
3. Verificación cruzada para detalles críticos ambiguos (conteo de hojas/dedos,
   dirección de caminata): segunda pasada con pregunta cerrada y específica.
4. Consolidar los desajustes transversales y fijarlos como reglas del estándar
   (un solo valor por atributo; el hero manda).
5. Solo después de QA verde: despachar image-to-video (gate humano para el gasto).

## Quick Reference — checklist de continuidad por imagen

- [ ] Anatomía del personaje: nº de hojas/rasgos según hero, sin mutaciones
- [ ] Nº de dedos por mano (el drift 3/4/5 es el error más común entre modelos)
- [ ] Textura del cuerpo (lisa vs rugosa/granulada) según hero
- [ ] Color de cejas/rasgos faciales según hero
- [ ] Accesorios: corbatín/acessorio forma y color, lado de la maleta
- [ ] Dirección de caminata coherente con la serie (viaje continuo, no por escena)
- [ ] Iluminación/hora consistentes (golden hour, reflejos, paleta de marca)
- [ ] SIN texto promocional quemado (va a post-producción); solo letreros reales
      del entorno, y transcribirlos para verificar ortografía
- [ ] Sin props prohibidos por el guion (ej. máquinas protagonistas, multitudes)
- [ ] Pose-sheet/character sheet del estudio alineada al hero (no una versión distinta)

## Procedure

### Estándar de solicitud de escenas (4 bloques por escena nueva)

1. **Frame de identidad**: adjuntar el hero del personaje + el frame de la escena
   anterior (cadena de continuidad).
2. **Master prompt de personaje**: bloque FIJO en inglés, idéntico en todas las
   escenas — nunca se reescribe por escena. Ejemplo real validado (Lucky, trébol 3D):

   ```
   Lucky — premium 3D cartoon clover mascot, character lock: exactly four glossy
   deep-green clover leaves forming his round body (#3CB371, SMOOTH polished texture),
   large round white eyes with black pupils and catchlights, friendly arched brown
   eyebrows, rosy blush cheeks, wide open smile with white teeth, classic gold bow tie,
   five-fingered hands, stubby legs, rounded green feet. He pulls a dark-green vintage
   suitcase with gold trim by its telescopic gold handle. Pixar-grade 3D render,
   golden-hour cinematic lighting, wet pavement reflections, 9:16 vertical.
   NEGATIVE: no extra/missing leaves, no texture change, no finger count errors,
   no baked advertising text, no fake logos or QR, no slot machines as protagonist,
   no additional characters, no morphing.
   ```

3. **Bloque de entorno**: solo locación, hora y luz. Locaciones canonizadas por
   campaña (terminal, basílica, carretera con niebla, plaza...) se reusan tal cual.
4. **Checklist de continuidad** (Quick Reference) verificado antes de aprobar.

### QA con visión (dos caminos, en orden)

Ver `references/vision-qa-via-provider-api.md` para la receta completa del camino 2.

- Camino 1: `vision_analyze` con prompt estructurado (identidad/maleta/entornos+textos
  exactos/cámara/defectos). Si el backend rechaza imágenes ("Model do not support
  image input"), arreglar `auxiliary.vision` en config.yaml hacia un modelo CON visión
  (backup primero) y reintentar.
- Camino 2: API directa OpenAI-compatible del proveedor con la imagen en base64.

## Pitfalls

- **Hallucinación de visión**: con un backend roto o débil, algunas llamadas NO
  devuelven error sino una descripción inventada y plausible ("reconstrucción" sin
  haber visto la imagen). Ante respuestas genéricas o que ignoran detalles del
  prompt, verificar con una pregunta de control (ej. transcribir un texto concreto)
  o cambiar al camino 2.
- **Modelos con reasoning queman max_tokens**: content vacío con finish_reason=length
  → subir max_tokens a >= 3000 y pedir "responde directo, sin razonamiento".
- **Drift silencioso por imagen**: el set puede ser " consistente a simple vista"
  y aun así tener dedos 3/4/5, cejas de dos colores, texturas distintas y una
  dirección de caminata invertida. Por eso el QA es imagen por imagen, no muestral.
- **Texto quemado**: aunque la IA escriba los textos BIEN (pasa), la regla del guion
  manda: textos promocionales SIEMPRE a post-producción. Excepción aceptable:
  letreros reales del entorno.
- **Pose-sheet ≠ canon**: una hoja de poses de estudio generada aparte puede traer
  otra versión del personaje (otro nº de dedos, otras cejas). Regenerarla alineada
  al hero antes de producción.
- **Guardar el trabajo**: el doc QA + JSON crudo de análisis viven en el workspace de
  la campaña (regla del repo: commit por fase; lo no persistido se pierde).

## QA de CLIPS (image-to-video) — labial y falso negativo

Esto aplica al clip animado (no al still): después de generar con voz nativa
(Seedance `generate_audio:true`), el labial se QArea con frames EXPORTADOS, no
con el still.

- **Falso negativo de "boca congelada"**: una grilla de FRAMES DE CUERPO COMPLETO hace
  que el modelo de visión diga "boca congelada/idéntica" AUNQUE el labial esté perfecto
  (píxel de boca insuficiente). Igual que con stills: RECORTAR a la cabeza
  (`ffmpeg ... crop=W:H:0:arriba`) antes de preguntar "¿la boca cambia de forma entre
  paneles?". Con crop se distingue articulación real de boca fija.
- **Si el clip NACE con labial congelado** (no es falso negativo — el personaje queda
  pequeño/tapado y Seedance relajó el lip-sync), la causa suele ser el PROMPT: si pide
  "treat the dialogue as voice-over / mouth does NOT need to be visibly speaking",
  Seedance genera el audio pero NO anima la boca. Ver bloque de lip-sync abajo.
- **QA de voz SIEMPRE por STT** (faster-whisper `small` int8, beam 5) palabra por palabra
  contra el diálogo oficial — no confiar en un solo modelo: "vilo/Bingo" o "apnizdad/Amistad"
  es jerga de Whisper con oclusivas b/v y s/z, no necesariamente error de pronunciación.
  Confirmar los casos dudosos con el oído del Admin.

## Prompt de LIP-SYNC para Seedance (verificado 08/09, reel2-pacho)

El enfoque que FUNCIONA (lote agosto aprobado, `batch_golden_bingo.py`):
- `SEQUENCE SHOT. NO CUT. Single continuous take, Ns total.`
- `DIALOGUE (spoken by <personaje> OUT LOUD in Spanish, <tono>, looking at camera): "<texto>"`
- `His <screen-face/face> CLEARLY animates mouth and eyes IN SYNC with the spoken line.
  Lips and jaw move naturally word by word... never frozen, never stiff.`
- Bloque `AUDIO` explícito (voz nativa, sin música, sin subtítulos) + bloque CHARACTER fijo
  (identidad del personaje, idéntico en todas las escenas).

**LO QUE DESACTIVA el labial (no usar):** "The character's mouth does NOT need to be
visibly speaking... treat the dialogue as voice-over narration... if lips move keep it
subtle." → Seedance genera la voz NATIVA pero deja la boca congelada.

El clip con voz nativa NUNCA se regenera por labial si ya está pagado: el lip-sync final
se logra en post con `scripts/fit_voice.py` (calibrar la voz de marca al ritmo del labial
nativo, atempo ≈0.9). Ver skill `reel-voice-lipsync`.

## Verification

- El doc QA tiene fila por CADA imagen del set (contarlas contra lo entregado).
- Cada fila cita los textos visibles transcritos (o dice "sin texto").
- Los desajustes transversales quedaron fijados como reglas con UN valor por atributo.
- Ningún clip image-to-video se despachó antes del veredicto (verificar en el log
  del worker antes de afirmar que se hizo).

## References

- `references/vision-qa-via-provider-api.md` — receta validada de QA visual por API
  directa del proveedor: UA de navegador (Cloudflare 1010), base64 data URL, tokens,
  reintentos y detección de hallucinación.
- Ejemplo completo aplicado (reel Lucky Bingo Millonario, 10 imágenes QAeadas):
  workspace de la sesión 28/08 → `reel-bingo-lucky/ESTANDAR-ESCENAS-LUCKY.md`.
