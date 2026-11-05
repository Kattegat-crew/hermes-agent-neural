# Seedance: referencia de audio y sincronía con voz final

## Contrato multimodal
- Al combinar foto y audio, enviar la foto con `role: reference_image` y el WAV con `role: reference_audio`. No mezclar `first_frame`/`last_frame` con medios de referencia: el esquema de inspect enumera roles, pero omite esa restricción cruzada y el proveedor rechaza el payload.
- Este modo guía identidad/composición, no fija el primer fotograma píxel a píxel. Explicar esa diferencia; no prometer ambas capacidades juntas.
- Validar una escena corregida con output real antes de enviar el resto del lote. Respetar permisos de reenvío y presupuesto; no repetir voz ni imágenes por un rechazo de video.

## Estados y costo
- No interpretar `status: COMPLETED` del wrapper como generación exitosa. Verificar `providerResponse.httpStatus`, ausencia de `providerResponse.error`, URL de salida y MP4 decodificable. HTTP400 + output null + billedUnits0 es rechazo sin video, no un clip completado.
- Persistir run ID antes de esperar y recuperar por GET después de un timeout; nunca reenviar por falta de respuesta local. Separar solicitudes rechazadas, correctivas y costo real del proveedor.

## Voz y labios
- Resolver voz por nombre/ID real; un nombre parecido no autoriza sustituirla. Si el usuario exige velocidad1.0, conservar el PCM original y verificarlo en la pista previa a mezcla. No acelerar ni ralentizar voz para encajar labios.
- El audio de referencia condiciona la generación, pero no garantiza cadencia exacta. Transcribir voz original y audio nativo localmente; ajustar tiempos del VIDEO con límites de palabras/frases, preservando la voz original final.
- Mantener transcripciones crudas. Un nombre propio transcrito fonéticamente requiere asistencia temporal explícita y anotada; no renombrar tokens para fingir coincidencia léxica ni declarar precisión fonémica perfecta. La revisión perceptual humana sigue pendiente.
- Separar la coincidencia de palabras, la continuidad visual y la sincronía fonémica: ASR o fotogramas estáticos no prueban las tres.

## Montaje verificable
- Colocar disoluciones reales entre handles sin habla, sin cortar sílabas ni solapar locuciones. Normalizar FPS/timebase antes de xfade.
- Inspeccionar duración del stream de VIDEO además del contenedor: AAC puede alargarlo y ocultar faltantes de cuadros. Completar solo la cola silenciosa con clon del último cuadro antes de trim/xfade y hacer smoke real de duración.
- Medir loudness del MP4 entregado, no solo el objetivo del filtro. Ajustar ganancia local conservando versión anterior y verificar LUFS/true peak otra vez.
- Probar helpers offline RED/GREEN; código en scripts/, no assets ignorados. Declarar upscale cuando la entrega1080p parte de fuentes720p.
