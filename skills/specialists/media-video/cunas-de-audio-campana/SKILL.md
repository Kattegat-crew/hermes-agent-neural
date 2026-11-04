---
name: cunas-de-audio-campana
description: "Use when writing a perifoneo or radio audio spot."
tags: [perifoneo, radio, cuna-audio, campana, casino, guion, coljuegos]
version: 1.0.0
author: hermes
license: MIT
metadata:
  hermes:
    tags: [audio, perifoneo, radio, campaña, guion, casino, drive]
triggers:
  - "guion para el perifoneo de <sede>"
  - "cuña de radio / cuña de ruleta / audio de calle"
  - "perifonear la promoción / carro con altavoz"
---

# Cuñas de audio de campaña (perifoneo / radio local)

Entregable: **texto de cuña de audio** para perifoneo (altavoz en carro) o radio local.
NO es video: no pedir keyframes, Seedance ni lipsync. Si además hay reel, ese va por `guion-video-campana`.

## Paso 0 — Levantar los datos duros ANTES de escribir (no negociable)
La cuña se escribe sobre el material aprobado de esa sede, nunca de memoria.
- El material por sede (afiche, banners de TV, reel) vive en el **Drive de la cuenta NeuralCrew**, no en el Drive del cliente ni en el repo: credenciales `/opt/data/secrets/<cuenta>-drive.json` (`jonathan`, `nancy`, `helmer`, `jacqueline`, `neuralcrew` = misma cuenta NC; las `*-drive.json` traen scope de Drive, las `*-gmail/-calendar` responden 403).
- Recorrido verificado: buscar la carpeta `<Sede>` → `Afiche <sede>.png`, `Banners TV's/TV1..N.png`, `Reel N- <sede> ya listo/`.
- **Atajo más rentable:** `vision_analyze` sobre el afiche y 1-2 banners TV con la pregunta *"Transcribe literalmente TODO el texto visible (titular, promoción, premios, fechas, horas, dirección, avisos legales)"* → devuelve evento, fecha, premios, dirección y pie legal sin abrir el mp4 ni transcribir audio.
- **Pitfall de ficha vieja:** las fichas del brain pueden contradecir el material vigente (Funza figuraba "CERRADA / excluida del bingo" mientras el afiche y los banners promocionan Bingo Millonario en Funza el 18/09/2026 y los informes KASSIUSS reportan operación diaria). El material aprobado manda: si contradice la ficha, decírselo al Admin y NO descartar la sede por la ficha.

## Paso 0.5 — Confirmar SEDE y ALCANCE antes de redactar (costó rehacer el guion completo, 10/09/2026)
- **El pendiente del backlog y la petición del momento pueden apuntar a sedes distintas.** El backlog decía "guion ruleta perifoneo" y el Admin pidió "el perifoneo de Funza"; al entregar corrigió: *"No Ragnar, el anuncio del Perifoneo es para Chiquinquirá"*. Cuando el ítem no nombra sede de forma explícita, decir en UNA línea "voy con <sede>, mensaje <X>" y esperar OK antes de escribir las tres cuñas.
- **Dos sedes en el mismo municipio.** Chiquinquirá tiene dos locales Paradise (Cra. 9 No. 17-51 y Cra. 8 No. 17-40). Si la novedad (ruleta nueva, sala, remodelación) está en UN solo local, la cuña DEBE decir en cuál: sin dirección, manda gente al local equivocado. Pedirla antes de grabar.
- **Confirmar si la novedad ya ocurrió:** "llegó" vs "estrena este fin de semana". El Admin suele decir "se va a poner" / "le van a instalar", y la cuña sale días después.
- **Novedad sin cifras:** si no hay monto verificado para la ruleta nueva, "acumulados que crecen" — nunca inventar montos, probabilidades ni cifras.

## Cuña de doble mensaje (novedad permanente + evento con fecha)
Cuando la sede estrena algo **y** además hay promoción con fecha, la cuña lleva los dos mensajes y el set cambia:
- **A mixta (~43 s):** novedad + evento + legal. Es la que se repite toda la tanda.
- **B solo novedad (~19 s):** sirve cuando el evento ya pasó y la novedad sigue vigente.
- **C solo evento (~22 s):** las semanas del evento.
La novedad va PRIMERO (es lo que no tiene nadie) y el evento con fechas después; el cierre de marca y el pie legal no cambian. Caso completo en `references/perifoneo-chiquinquira-2026-09.md`.

## Humanizar a registro regional: dosis, no caricatura
Cuando el Admin pide "que suene de acá" (boyaco, costeño, paisa…):
1. **Investigar antes de escribir**, con subagentes en paralelo (4 tareas): (a) glosario dialectal con fuente por entrada, (b) patrones de habla al invitar/vender — fórmulas de saludo, invitación y cierre, y manejo usted/tú/sumercé, (c) límites: clichés quemados, errores de agencias de fuera y regla de dosis, (d) contexto real del municipio (economía, días fuertes, si su habla se parece al altiplano o al norte del departamento). En cada tarea: *"prohibido inventar; fuente por hallazgo; marcar confianza"*.
2. **Regla de dosis:** 1-2 marcadores auténticos por cuña de 20-45 s, en la apertura (saludo) y en el cierre; el resto neutro para que se entienda con ruido de calle. Nunca el mismo marcador dos veces.
3. **Cliché = caricatura:** el marcador repetido en cada frase, o el que usa el de afuera para burlarse, rompe la voz. Pasar el borrador por `humanizer` antes de entregar.
4. **Sin fuente, no entra:** ni acento fingido ni léxico "turístico" de la región.

## Formato de la cuña (referencia real del cliente)
`Guion cuña ruleta.docx` (Golden Game · Tunja · ruleta Gold Club):

```
[Sonido envolvente de monedas, luces parpadeando y aplausos de fondo]
[Base musical moderna y energética, estilo pop-electrónica]
[Voz dinámica y emocionada, tono más informal pero envolvente]
<locución corrida: gancho local → qué es → beneficios → CTA → claim de marca>
```

Líneas de ambiente entre corchetes + UNA sola voz corrida. Cierra con el nombre del casino y su claim.

## Entregable mínimo
- **Cuña A (principal, ~40 s)** — todos los datos; se repite toda la tanda.
- **Cuña B (corta, ~20 s)** — gancho + datos clave, para rotar.
- **Cuña C (día del evento, ~19 s)** — "hoy es el día", solo el día.
- **Pauta de rodaje**: ciclo de 60 s (A → música sola → B), días (3 antes + el día del evento), zonas (centro comercial, vías de entrada, barrios vecinos), franjas (10:00-13:00 y 15:00-19:00).
- Voz: locutor masculino enérgico (mejor inteligibilidad) o la voz del personaje (TTS) si el cliente quiere coherencia con el reel publicado.

## Duración: medir, no estimar
Perifoneo habla a **2.2-2.6 palabras/s** (más lento que el reel TTS 2.8-3.0: la calle come agudos y hay que pausar los datos).

```python
for w in (cuna_a, cuna_b, cuna_c):
    n = len(w.split()); print(n, f"{n/2.6:.0f}-{n/2.2:.0f}s")
```

Reportar el rango de segundos dentro del entregable (referencia Funza: 91 pal ≈ 35-41 s · 45 ≈ 17-20 s · 47 ≈ 18-21 s).

## Reglas de calle y compliance
- **Voz seca**: sin reverb ni efectos sobre la locución.
- **Repetir dos veces los datos duros** en la cuña A (día, lugar, dirección): la dirección y el nombre del C.C. son los primeros en perderse.
- Cada pasada cierra con **+18 · Autorizado por Coljuegos · juego responsable** (es publicidad exterior: mismo pie que las piezas gráficas).
- Prohibido en audio: "gratis", "plata fácil", "garantizado", "sin jugar". El cartón/tabla va ligado a jugar.
- **Discrepancia de mecánica ⇒ avisar ANTES de grabar** (caso real: el afiche de Funza decía 4 bingos $50K/$50K/$100K/$300K + cena y bebidas, y el T&C v6 de Lucky decía 3 bingos + tabla con registro). No asumir: señalarlo al Admin en la entrega.

## Cierre del entregable
- Guardar en `/opt/data/plans/GUION-<SEDE>-PERIFONEO-<FECHA>.md` (convención de guiones de campaña ya existente) y entregar las 3 locuciones en el chat para OK.
- Preguntar SOLO los datos que el material no trae (típico: hora de inicio, si se menciona ruleta/máquinas) — en una sola tanda.

## Referencias
- `references/perifoneo-funza-18sep2026.md` — caso completo (datos verificados, decisiones) + receta de Drive API en urllib puro con IDs verificados.
- `references/perifoneo-chiquinquira-2026-09.md` — caso de doble mensaje (ruleta nueva + Bingo Millonario): datos verificados de los banners TV, corrección de sede Funza→Chiquinquirá y ruta de recuperación de material en Drive.
