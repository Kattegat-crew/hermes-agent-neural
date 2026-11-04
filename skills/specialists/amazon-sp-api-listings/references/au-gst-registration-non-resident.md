# GST Australia — registro para seller no-residente con FBA (verificado 2026-11-03)

Procedimiento y criterios, no asesoría fiscal: el cliente decide con su contador.
Fuentes: ATO *GST for non-resident businesses*, ABR *applying for an ABN from
outside Australia*, Amazon Seller Central *Australia GST*, y agentes AU (SimplyVAT,
Epic Tax, AusBusinessRegister).

## Regla que decide todo: dónde está el stock

- Stock vendido desde fuera de Australia vía Amazon (EDP/LVIG): Amazon recauda el
  GST, el seller puede no registrarse.
- **Stock en un fulfilment center australiano (FBA) = obligación de GST desde el
día 1.** El ATO lo dice explícito: la venta ocurre donde están los bienes, así que
  el umbral de AUD 75.000 no protege a nadie con inventario local.
- Por eso FBA-AU ⇒ **GST estándar con ABN**, no GST simplificado (el simplificado
  usa ARN y aplica solo a ventas desde el exterior bajo el umbral).

## Secuencia real (3 + 1 pasos)

1. **ABN en el ABR.** Una compañía extranjera califica sin director ni dirección
   australiana y **sin ARBN**: el ABR admite el criterio "making supplies connected
   with Australia's indirect tax zone". Identidad se acredita con copia certificada
   del Certificate of Incorporation del país de origen (proceso *proof of identity
   for non-residents*). Gratis si se hace directo; agentes cobran AUD 400-800.
2. **Registro de GST estándar en el ATO** con ese ABN + verificación de identidad
   del representante (myID / Online services for business).
3. **Agente BAS australiano.** Desde fuera de Australia no se puede presentar el
   BAS electrónicamente; se necesita BAS agent (AUD 300-800 por trimestre según
   volumen).
4. **Entregar el ABN a Amazon** (Seller Central → Tax settings). Mientras no esté,
   Amazon cobra 10% de GST sobre sus fees; con ABN registrado deja de cobrarlo.

Documentos a reunir: Certificate of Incorporation, EIN letter, pasaporte del socio,
comprobante de domicilio, datos del seller account, ubicación del inventario FBA.

## Costo y riesgo

- Año 1 estimado AUD 1.200-2.500 (ABN + registro + 4 BAS).
- **Punto gris a decidir con el contador:** si la LLC "hace negocios" en Australia,
  ASIC puede exigir registro de compañía extranjera (ARBN, ~AUD 1.500+/año). La
  mayoría de sellers FBA pequeños no lo tramita; es riesgo, no certeza. No afirmarlo
  como obligatorio ni como innecesario.
- Registrar voluntariamente antes del umbral corta la exposición retroactiva: si no
  está registrado y vende, el GST igual se debe.

## Cómo se refleja en el modelo de márgenes

Precios en `amazon.com.au` son GST-inclusive: `neto = P / 1.10`, y el referral fee
se calcula sobre el precio con GST. Si el seller está registrado, el GST pagado en
las fees de Amazon es recuperable → no lo metas como costo muerto sin decirlo.
Detalle de fórmulas en `references/unit-economics-and-sales-watcher.md` §2.

## Lo que NO se debe hacer

- Enviar correos a agentes/ATO sin aprobación explícita del usuario.
- Prometer un plazo de aprobación: depende de la verificación de identidad del ABR.
