# Producción rápida sin bajar calidad

## Secuencia recomendada
1. Preflight único: comprobar repo/branch/status, herramientas en el host real, voz exacta, referencias, esquema combinado imagen+audio, espacio y RAM. Resolver rutas una vez y guardarlas en el manifiesto del proyecto; no volver a descubrir todo en cada etapa.
2. Congelar guion y ficha de marca. Separar MASTER de identidad, reglas globales y bloques de escena en inglés detallado. Personas adultas CGI/Pixar si el vídeo lo exige. Reusar identidad, no copiar concepto de otra marca.
3. Con autorización y gate humano vigente, obtener voz normal y keyframes aprobados. Pueden prepararse independientemente; no confundir una propuesta de paralelización con un batch paralelo ya implementado.
4. Medir WAVs y diseñar el ritmo ANTES del montaje. Conservar voz1.0; calcular duración de clips según el esquema del proveedor y handles mínimos, luego recortar las colas necesarias. No dejar silencios largos para rellenar duración de generación.
5. Validar UN piloto de vídeo con el contrato exacto antes del lote. Foto+audio: reference_image + reference_audio. Exigir upstreamHTTP2xx, URL real, descarga y decode. Después continuar resto dentro del cupo aprobado, no reenvíos automáticos. No aumentar concurrencia sin comprobar límites y auditoría por escena.
6. Montar con el editor ya operado: para recortes usar Akari y su proyecto contenido, master visual sin audio, WAV originales y cama musical continua con ducking. Tipografías/CTA/logo/legal aprobados se reutilizan, no se rediseñan.
7. Dos rutas de QA: técnico automatizable (schema, hashes, decode, frames/fps/duración, loudness, integridad/posición de voz) y perceptual humano (ritmo, actuación, lectura, boca, atractivo). Los tests de texto/ASR no certifican boca perfecta.
8. Revisar independientemente el archivo real antes de cerrar; aprobación humana distinta de autorización de publicación. Guardar preset, manifiesto y aprendizajes; no crear otro script por marca para cada ajuste.

## Evitar vueltas innecesarias
- Mantener un único registro por etapa con insumos/hash, runID, estado y salida; reanudar por lectura de runID, no por reenviar generación.
- Clasificar un fallo antes de actuar: validación local, upstream rechazado, espera asincrónica o herramienta inaccesible. Un timeout de una llamada no demuestra ausencia de herramientas ni autoriza tocar configuración.
- No pedir de nuevo una autorización ya dada para el mismo alcance. Escalar solo cambios de gasto, estética, voz o publicación.
- Preservar bruto aprobado y proyecto editable; nunca regenerar imagen/voz para corregir un silencio o transición local.
- Automatizar comprobaciones deterministas y ejecutar lecturas independientes juntas; limitar renders pesados según RAM/CPU. Paralelizar QA técnica/visual cuando sus entradas ya existan.

## Medir antes de prometer
Registrar inicio/fin por etapa, latencia del proveedor, render, revisión, reintentos y gasto real conocido. Comparar reels de duración/complejidad parecida. No vender reducción de duración del vídeo como reducción del tiempo de producción. Un pipeline genérico de un comando y la planificación automática de pausas son mejoras pendientes hasta tener tests y ejecución real.
