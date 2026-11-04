---
name: copy-quality-es
description: >-
  Eliminación de clichés de IA, tono robótico y slop. Redacción de copy humano, persuasivo, directo y con dialecto local para campañas, guiones y redes sociales.
tags: [copy, anti-slop, humanizar, redaccion, estilo, dialecto, bragi]
version: 2.0.0
author: NeuralCrew / Hermes Fleet
---

# Calidad de Copy y Redacción Humana (Anti-Slop)

Habilidad canónica para garantizar que cualquier texto, guion, post o mensaje redactado por la flota suene 100% humano, persuasivo y libre de los patrones estadísticos típicos de los modelos de lenguaje (AI slop).

---

## Cuándo usar esta Skill (Triggers y Síntomas)

Usa esta skill inmediatamente cuando se presente cualquiera de estas situaciones:
- El usuario pide *"humaniza este texto"*, *"quítale el tono de ChatGPT/IA"*, *"redacta un copy directo"*, o *"que no suene acartonado"*.
- Redacción o revisión de guiones para personajes y actores de voz (como Lucky o campañas de Casino Golden).
- Copy para redes sociales, cuñas radiales, perifoneo, volantes, correos o mensajes de mensajería (WhatsApp/Telegram).
- El borrador actual suena genérico, inflado, excesivamente corporativo o lleno de adjetivos vacíos.

---

## Principios No Negociables de Redacción

1. **Densidad sobre Relleno**: Cada palabra debe portar un dato, una acción o una emoción real. Si una oración puede eliminarse sin perder información, se elimina.
2. **Variabilidad Rítmica (Burstiness)**: Alterna frases telegráficas de 2 a 4 palabras con oraciones compuestas. Los LLMs escriben con longitudes de frase monótonas (~15-20 palabras); los humanos alternan pausas cortas, remates secos y desarrollos vivos.
3. **Especificidad y Anclaje**: Cero conceptos abstractos cuando existen datos concretos: nombres de lugares, números exactos, fechas, objetos tangibles y verbos activos.
4. **Voz Directa**: Háblale a una persona específica en segunda persona singular (*tú* o *usted* según la marca), nunca a una masa abstracta.

---

## Lista Negra de Clichés de IA (Vocabulario Prohibido)

Queda estrictamente prohibido el uso de los siguientes términos y estructuras en español:

### Palabras Tabú
* **Verbos**: *adentrarse, sumergirse, desentrañar, navegar (por), desbloquear (potencial), transformar, embarcarse, desatar, cautivar, revolucionar.*
* **Sustantivos**: *tapiz, panorama, testimonio, reino, sinfonía, faro, viaje (metafórico), catalizador, paradigma, lienzo, travesía.*
* **Adjetivos**: *crucial, fundamental, primordial, meticuloso, vibrante, vertiginoso, imprescindible, fascinante, inquebrantable, apasionante.*
* **Fórmulas de transición**: *en el vertiginoso mundo de hoy, en conclusión, vale la pena señalar, como todos sabemos, es importante destacar, no cabe duda de que, en última instancia, sin lugar a dudas.*

### Estructuras Sintácticas Prohibidas
* **La Regla de Tres Artificial**: Forzar tríadas predecibles de adjetivos (*"rápido, seguro y confiable"*, *"innovador, dinámico y eficiente"*).
* **El Eco del Prompt**: Comenzar la respuesta parafraseando la orden del usuario (*"A la hora de redactar un buen copy, es vital..."*). Ve directo al grano.
* **El Cierre Moralizante**: Concluir párrafos con reflexiones filosóficas no solicitadas sobre el futuro, la esperanza o la importancia de algo. Termina en una llamada a la acción o en el último dato.
* **Listas saturadas de negritas**: Evita formatear cada línea con negrita al inicio (`**Punto:** descripción`). La prosa fluida y natural es más humana.

---

## Adaptación de Dialecto Local (Colombia y Regiones)

Cuando el encargo sea *"que suene de acá"* (cuñas, perifoneo, guiones regionales, activaciones locales):

1. **El dialecto es sal, no el plato principal**: Un marcador bien puesto (ej. *"pilas"*, *"acérquese"*, *"venga le cuento"*) ancla la identidad; cinco modismos forzados en una frase convierten el anuncio en una caricatura.
2. **Prioridad absoluta de datos duros**: Antes de escribir, extraer las cifras, premios, vigencias, mecánicas y direcciones exactas de las piezas aprobadas del cliente en Google Drive o artes validados. Nunca inventar premios ni condiciones legales.
3. **Tono de entretenimiento y casino**: Mantener cercanía y emoción limpia. Sin tecnicismos financieros, sin sonar a estafa ni a documento notarial.

---

## Modos de Operación

### 1. Modo Edición (Predeterminado)
Toma el borrador, aplica la poda de clichés y entrega el resultado listo para publicar, agregando abajo una sección breve de 2 líneas:
`Qué se corrigió:` (resumen de clichés y vicios eliminados).

### 2. Modo Detección / Auditoría
Si el usuario solicita auditar sin reescribir, identifica cada patrón de IA presente, cita la frase exacta y explica por qué delata autoría sintética.

---

## Checklist de Control de Calidad Antes de Entregar

- [ ] ¿Supera la prueba de lectura en voz alta sin trabarse ni sonar a locutor de infomercial?
- [ ] ¿Está 100% libre de palabras de la lista negra?
- [ ] ¿Los datos duros (fechas, premios, direcciones, requisitos legales) coinciden con la pieza oficial?
- [ ] ¿Comienza directo con el gancho sin rodeos introductorios?
