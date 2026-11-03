---
name: scene-keyframe-qa-lipsync
description: "Use when QAing reel keyframes and Seedance lip-sync."
tags: [video, seedance, lip-sync, keyframes, qa, reels]
version: 1.0.0
author: Sindri
license: MIT
metadata:
  hermes:
    tags: [video, seedance, qa, lip-sync, lucky]
    related_skills: [reel-pipeline, elevenlabs-brand-voice, ai-image-provider-api]
---

# QA de keyframes de escenas + prep lip-sync Seedance

## When to Use
- El Admin/usuario entrega keyframes de escenas de un reel (Lucky/Goldie) y pide
  análisis imagen-por-imagen contra el guion antes de animar.
- Preparar o ejecutar un test de sincronización labial con voz TTS sobre una escena.

Pipeline probado 28/08 (reel Lucky Bingo Millonario). Produce: informe por escena,
detección de character drift, bloques de master prompt, y el run reference2video
con audio (lip-sync nativo) listo para el gate.

## 1. Visión programática (workaround del aux-vision roto)
El `vision_analyze` del perfil puede fallar (aux pointing a un modelo sin visión o
401 de la key). No bloquear por eso — usar qwen3.6 vision en api.nan.builders con
la `NAN_API_KEY` de `/root/marketing-campaign-generator/.env`:
- Script de referencia: `profiles/sindri/workspace/lucky_qa.py` (imágenes → JPEG b64
  data-URL vía PIL, payload con `curl --data-binary @file` porque argv directo da
  E2BIG; `content` puede venir vacío y la respuesta real en `reasoning_content`).
- Dos pasadas: (a) por-imagen con prompt específico de escena vs guion,
  (b) compare hero-vs-escena listando drifts (hojas/ojos/cejas/mejillas/boca/
  corbatín/textura/tono/pies/proporciones) + veredicto IDÉNTICO/DERIVA LEVE/
  MODERADA/ROTO. Batch de 10 imágenes ≈ 2-3 min con 2 por llamada.
- El primer `The user wants...` es reasoning: recortar hasta el primer marcador.

## 2. Checklist de keyframe premium (estandar Bingo Millonario)
882×1568 (9:16) · prop crítico AGARRADO con contacto físico (maleta suelta en el
suelo = ❌, ver sc5) · dirección de caminata y hora de luz constantes entre planos
consecutivos · signage legible o inexistente (cero garble) · cero tipografía
publicitaria incrustada (regla edición) · un solo protagonista, sin extra props
que imposibiliten la acción del guion (manos ocupadas en sc3 → sin gesto posible) ·
espacio de encuadre para el movimiento de cámara pedido · hero/ancla: multi-pose
sheet es mejor referencia que una sola frontal.

## 3. Master prompt blocks (reutilizables)
IDENTITY-LOCK (prefijo todo run): descripción atómica del personaje + "Do not
redesign, do not add clothing or accessories". STYLE-LOCK: paleta/materiales/cámara.
NEGATIVOS: no text/logos/watermark/extra characters/morphing/floating objects.
En Seedance r2v se referencian con @Image1/@Image2/@Audio1.

## 4. Lip-sync test (Seedance 2.0 reference-to-video)
1. Voz: `python3 scripts/elevenlabs_client.py --tts --text "..." --voice <id>
   --out x.wav` (Voz_Lucky U9tZtg3uJtVgXPkvosWR; Voz-Goldie qWWAqFomnJ99VwQLREfT).
   Verificar duración < clip (5/10s).
2. Servir assets: copiar a `/var/www/golden-webproxy/va/<campana>-qa/` → URL
   `https://goldengame.com.co/va/...` (verificar 200 + content-type image/audio
   antes de POSTear; audio mp3 vía ffmpeg; Seedance rechaza data-URLs).
3. Run: `fal-client.py --mode reference2video --model r2v --resolution 720p
   --duration 5 --ratio 9:16 --image <escena> --image <hero> --audio <voz>
   --prompt "@Image1 ... @Image2 identidad ... @Audio1 lip-sync" --dry-run`
   (~$0.07/clip 5s full; mini $0.011/s). El script exige
   `/root/marketing-campaign-generator/.spend-gate.json` creado por HUMANO (approved_by,
   purpose, expires_at ISO 6h) — NUNCA crearlo el agente; dry-run no lo necesita.
4. QA del clip: mouth shapes vs sílabas, identidad preservada, sin morphing;
   comparar contra `reference_audio` nativo si STTS.

## QA de movimiento en video animado: no juzgar la boca con frames sueltos

Un clip puede parecer «boca congelada» y estar articulando. Falso negativo real (28/10/2026):
una hoja de contactos a 10 fps con `crop` ajustado al rostro concluyó «sin visemas»; el usuario,
viéndolo en reproducción, dijo lo contrario y tenía razón.

**Método correcto (coste 0, determinista):**

1. Extraer a gris pequeño (`scale=270:480,format=gray`) con `ffmpeg -f rawvideo` (~120 frames).
2. `std` por píxel sobre el eje temporal → mapa de movimiento; guardar normalizado como PNG y mirarlo
   con visión: se distingue la zona de boca de la de ojos y del idle del cuerpo.
3. Comparar celdas (std medio por celda 30×30) para localizar dónde hay movimiento propio.
4. Para encuadre e identidad, comparar **frame del clip vs keyframe aprobado** en una hoja 2×N;
   un `crop` estrecho sobre un blanco pequeño pierde detalle y produce conclusiones falsas.

Regla: una afirmación sobre articulación o parpadeo se sostiene con `std` temporal por región, no con
la impresión de una tira de frames.

## Pitfalls
- ⚠️ **Seedance NO preserva tu pista de voz** (ni full ni mini, ni r2v con
  audio_urls): RE-FONIZA con su propia voz (v4-mini Scribe: "el Trepu de la
  suerte" — pronunciación rota) y la boca queda FIJA a 6fps aunque pidas visemas.
  audio_urls solo da cadencia de referencia.
- ✅ **Ruta correcta voz de marca + labial (probada v5 29/08)**:
  1. Animar con **Seedance 2.0 mini** (`R2V_APP=bytedance/seedance-2.0/mini/
     reference-to-video` en r2v_run.py) — solo movimiento, ignorar su audio.
  2. Voz: ElevenLabs TTS Voz_Lucky → WAV a URL pública.
  3. **`fal-ai/sync-lipsync`** (POST `{video_url, audio_url}`, ~2.5 min): recorta
     el clip a la duración del audio y anima la boca SOBRE la voz de marca.
     Verificado v5: transcripción exacta + variación de visemas a 6fps.
  4. Ambiente: los SFX nativos del clip base se conservan; si no bastan, post-mix
     en edición.
- `fal-client.py` crashea 422 al leer `response_url` tras COMPLETED (y no escribe
  sidecar). El resultado viene en el `payload` del `status_url`: usar wrapper
  `profiles/sindri/workspace/r2v_run.py`.
- STTS ElevenLabs `speech-to-text`: campo de archivo **`file`** (no `audio`).
- Gate `.fal-gate.json`: con autorización verbal del Admin en chat, el agente lo
  firma con approved_by="Jesús (Admin)" + authorized_via citando el mensaje; nunca
  sin ese OK explícito.


<!-- absorbido de creative/keyframe-script-qa (censo 2026-09-24) -->
# QA guion × keyframes (pasada de Content sobre arte del producer)


Clase de tarea: cuando llegan renders escena-por-escena (caso: reel Lucky / Bingo Millonario, room Video-prod 29/08) y se pide analizarlos junto con el guion para fijar el estándar de futuras producciones. El rol de Bragi aquí NO es duplicar el QA técnico del producer: es la **verificación independiente con lens de historia y marca**, y el aderezo de voz al master prompt.

## Regla de oro: pasada propia, nunca eco

- Analizar **cada imagen con visión real** y cruzar contra el guion maestro. El valor para la sala es confirmar O corregir al teammate con evidencia. (Aquí se cazó que los dedos fusionados estaban en la mano del asa de Sc1, no en el saludo de Sc5 como reportó el producer; y signage extra no reportado: "EXPRESOS", "TERMINAL INTERMUNICIPAL".)
- Aprobar de memoria el informe ajeno = pasada perdida. Si el informe ajeno acierta, igual se declara "confirmado en mi pasada" por ítem.

## Qué mirar por imagen (checklist derivado del guion Seedance)

1. **Identidad del personaje vs hero**: nº/forma de hojas, ojos+catchlight, pajarita, **pies desnudos (NO shoes)** — las escenas tienden a poner botines (deriva leve-moderada). Hero + studio sheet (multi-pose) siempre como image_urls de identidad en cada run.
2. **Contacto físico de props**: todo objeto que menciona el guion debe estar agarrado con mano real o no entra al frame (maleta abandonada en Sc5 = error grave → regenerar o cubrir en motion).
3. **Continuidad del viaje**: vector de caminata y azimut del sol constantes entre planos consecutivos (Sc2C sesgada a la derecha vs frontal 2A/2B → fijar en prompt de movimiento). La hora dorada con suelo mojado refleja era "gratis" en todas → subirla a regla del STYLE-LOCK: *"unified by a single golden hour… every shot reads as one continuous journey"*.
4. **Textos ambientales**: legibles y bien escritos o inexistentes (cero garble). Los rótulos de un tríptico/tablero de intención NO deben imitarse dentro de las escenas — gráficos de venta van en edición (§13 del guion). Verificar citando textualmente qué dice cada letrero.
5. **Aptitud lip-sync** (para la escena del test): boca abierta con dientes definidos, contacto visual, aire de encuadre para el movimiento de cámara pedido; audio ÷ duración del clip debe dejar aire al final (3.34s en clip 5s ✅).
6. **Compliance Colombia**: máquinas tragamonedas/rótulos "JACKPOT" visibles → bokeh/DOF garantizado en motion + negativo *"no gambling UI, no jackpot machine as focal point, no winner celebrations"*. Cartones/fichas con números inventados rozan "no cartones inventados" → se señala como **decisión del Admin**, con voto de marca propio.
7. **Dictados de campaña** (mes del amor y la amistad, frases vetadas, una línea sutil por pieza): verificar que ninguna imagen los contradiga.

## Formato de entrega (lo que validó el Admin)

Archivo .md en workspace + resumen denso en sala, con:
- **Tabla de veredicto cruzado**: claim del teammate → qué vio mi pasada → estado (✅ confirmado / ⚠️ matiz / ✗ corregido).
- Sección "lo que las imágenes cuentan como historia" (lens Content: registro del personaje *"host, not performer"*, firma lumínica, qué escena vende la oferta sin decir de más).
- **Master prompt en 3 bloques** (IDENTITY-LOCK atómico / STYLE-LOCK / NEGATIVOS) heredado del producer + aderezos de voz, sin tocar anatomía.
- Checklist del estándar que se lleva la agencia para futuras campañas.
- Pendientes que requieren nombre/aprobación del Admin (gate de gasto, cartón de Sc4, regeneraciones).

## Workaround cuando auxiliary.vision del perfil no acepta imágenes

Síntoma: `vision_analyze` responde descripciones HIPOTÉTICAS construidas desde tu propio prompt ("no se ha proporcionado ninguna imagen, pero…") — output inventado, peligroso. Fix (script `workspace/lucky_qa_bragi.py`): llamada directa a qwen3.6 vision en `https://api.nan.builders/v1/chat/completions`, NAN_API_KEY del `/root/marketing-campaign-generator/.env`, imagen a ≤768px JPEG base64. Pitfalls del endpoint: `max_tokens`≥3000 (con 900 trunca → `content` vacío con finish_reason=length; leer `reasoning_content` como fallback), curl --max-time 240, 3 intentos. Nota infra: reportar en sala el config roto (`auxiliary.vision: deepseek-v4-flash@B.AI` no soporta visión) para que lo arregle quien tenga permisos — no hardcodear la limitación como permanente.

## Gate de gasto

Nunca disparar Seedance/fal sin `/root/marketing-campaign-generator/.spend-gate.json` creado por humano (approved_by + purpose + expira 6h). Pedir aprobación con nombre explícito en la sala.
