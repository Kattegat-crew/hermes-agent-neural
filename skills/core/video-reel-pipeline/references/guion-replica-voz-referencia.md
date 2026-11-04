---
name: guion-replica-voz-referencia
description: "Réplica de guion desde la voz de un video de referencia."
version: 1.0.0
metadata:
  hermes:
    tags: [guiones, reels, voz, replica, casinos]
    related_skills: [guiones-campana-por-canal, audio-video-transcription, guion-video-campana]
---

# Guion-réplica desde la voz de un video de referencia

Clase de trabajo: el cliente manda un video (propio o de otra marca) y pide «un guion muy parecido
al que usa la voz en [ese video]» para otra marca/campaña. La referencia es **la locución de ESE
video**, no el guion interno de la marca ni la plantilla de la serie.

Caso semilla (2026-09-14, Paradise Club Casinos): se calcó primero el guion del reel Pacho
(guion interno recuperado de `scripts/run_pacho.py`) y el usuario corrigió «ojo, del video que te
acabo de mandar». Transcribir la voz del video adjunto ANTES de proponer estructura: la
transcripción es el mapa; adivinar la referencia obliga a escribir todo dos veces.

## Flujo validado

1. `ffprobe` del video adjunto (duración, streams) → extraer audio con ffmpeg.
2. Transcribir literal con la skill `audio-video-transcription` (API whisper NaN). Si el clip mide
   **menos de ~2 min**, pad con silencio hasta superar el mínimo:
   `ffmpeg -y -v error -i in.mp3 -af apad=pad_dur=60 -c:a libmp3lame -b:a 128k in_pad.mp3`
   (verificado: 74,8 s reales + 60 s pad → 134,8 s → transcripción completa con segmentos y
   timestamps en un solo POST; recortar la respuesta con los timestamps de `segments`).
3. Mapear la estructura REAL de esa voz bloque por bloque (p. ej. grito de apertura
   «¡Atención, atención!...» → bienvenida al casino → volteo al evento del mes → CTA de agenda con
   fechas → cierre). Cuando se pide réplica, esta estructura SUSTITUYE a la de la serie
   (dato curioso → suerte → mecánica → CTA), no la complementa.
4. Reescribir 1:1 por bloque cambiando SOLO: marca, nombre del evento, fechas y datos duros
   confirmados por el cliente. Conservar registro, tuteo y ritmo del original.
5. Entregar SOLO lo pedido (ver alcance), con el archivo real adjunto (MEDIA:) — no solo la ruta.

## Datos duros: nada se inventa

Si falta un dato (fecha de la final, sede, horario), preguntar UNA vez y esperar la respuesta;
nunca inferirlo de otra campaña ni de la plantilla. Las cifras y sedes NO se meten en la voz si el
cliente dijo que van «con texto sobre el video» (overlay en post).

## Restricciones numeradas del usuario: TODAS aplican a la vez

Cuando el Admin numera restricciones («1 ... 2 ... 3 ...»), cada número es un requisito
independiente y simultáneo. Ejemplo real:

- «es general, yo pongo las sedes con texto sobre el video» → la voz NO menciona sedes ni pueblo;
  tampoco aplica el bloque «dato curioso del pueblo» de la serie: sede genérica = estructura de
  EVENTO, no de pueblo. No re-preguntar por la sede: ya respondió.
- «la final es el 2 de octubre» → la fecha dada se escribe tal cual.
- «solo quiero el guion» → entregable = texto de la locución. CERO generación de voz, CERO ensamble
  de reel, CERO gasto (regla de control de gasto), CERO «lo completo con la producción» por
  iniciativa propia.

## Tratamiento de voz (constante de la serie)

- Tuteo del protagonista al espectador; el registro de «usted» del mostrador convive pero nunca en
  la misma frase (frontera de oración).
- Rótulos, cifras, logos y sedes en POST — jamás generados por IA ni dichos en la voz si van como
  overlay.
- Pie legal en pantalla: `+18 Juego responsable | Regulado por Coljuegos`.
- Personaje de marca bloqueado (GOLDIE / LUCKY): no rediseñar entre escenas.

## Cadena de skills

`audio-video-transcription` (transcripción, límites + pad de silencio) → esta skill (mapeo y
réplica) → `guiones-campana-por-canal` (gate del guion, lint y canales) → `guion-video-campana`
(producción, SOLO si el cliente pide seguir después del guion).
