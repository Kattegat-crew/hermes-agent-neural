---
name: media-buying-pauta
description: "Use when sourcing or negotiating media rates for campaigns."
tags: [pauta, media-buying, radio, tarifas, cotizacion, clientes]
version: 1.0.0
author: Ragnar
platforms: [linux]
license: internal
hermes:
  tags: [pauta, media-buying, radio, tarifas, cotizacion, clientes]
  related_skills: [neuralcrew-letterhead, cunas-de-audio-campana]
---

# Media Buying / Pauta de Medios

## When to Use

Se activa cuando hay que pedir tarifas a un medio, evaluar una propuesta tarifaria que llegó,
negociar o armar la recomendación de pauta por cliente (radio hoy; prensa o exterior mañana).

Flujo para cotizar tarifas de medios externos (radio, prensa, exterior), evaluar propuestas
y armar la recomendación por cliente. Aplica a cualquier emisora o medio; los clientes
típicos son los casinos (Golden Game, Paradise).

## Procedimiento

1. **Solicitud de tarifas:** enviar correo a cada medio pidiendo tarifario vigente,
   cobertura y estudio de audiencia medido. Registrar remitente, correo y fecha de envío.
2. **Seguimiento a respuestas:** revisar la bandeja por respuestas ANTES de reportar estado
   — grep de remitentes y asuntos sobre el buzón, no memoria de sesiones pasadas. Si un medio
   no respondió en ~3 días hábiles, reportarlo como pendiente con fecha de envío, no como descartado.
3. **Descarga y archivo de la propuesta:** guardar el PDF que envíe el medio en
   `<proyecto>/_fuentes/<medio>/` — es la fuente de verdad contractual, no un chat.
4. **Verificar la tabla tarifaria leyendo el PDF**, nunca deduciendo: leer cada fila con
   vision_analyze (o extracción de texto) y transcribir valor unitario, paquete y total fila por fila.
   Un número citado de memoria o de un resumen previo es una cifra inventada en un documento
   que el cliente usará para pagar.
5. **Detectar inconsistencias numéricas en la propuesta** (cantidad que difiere entre columna
   y descripción, totales que no cuadran con unidad × cantidad) y pedir aclaración ESCRITA
   al medio antes de contratar o recomendar ese paquete.
6. **Extraer las condiciones**: exención de IVA, vigencia de la tarifa, NIT/razón social,
   costos de producción (cuña, reel, publicación), cobertura declarada. Si la propuesta no
   trae estudio de audiencia medido, anotarlo explícitamente en la recomendación.
7. **Recomendación por cliente:** documento por cliente sobre membrete oficial
   (skill `neuralcrew-letterhead`), con planes comparados, plan recomendado con justificación
   (ej. cuña producida por nosotros en vez del medio — ahorro y versiones por sede) y las
   inconsistencias pendientes. Entregar vía `MEDIA:`.
8. **Mensaje para el cliente final:** cuando el Admin va a reenviar la info a SU cliente,
   dar un mensaje corto de WhatsApp listo para copiar y pegar (saludo breve, a quién llega
   la pauta, planes con precios redondeados, recomendación). Conciso por defecto — el documento
   formal es para el archivo del Admin, no para el teléfono del cliente final.

## Reglas duras

- Cero cifras de tarifas fuera de la fuente: todo precio reportado debe poder trazarse a una
  fila del PDF de la propuesta.
- No recomendar un paquete con inconsistencia numérica sin resolver, aunque el precio parezca bueno.
- Cobertura y audiencia declaradas por el medio son marketing del medio: citarlas como
  "según el medio", no como dato verificado.
