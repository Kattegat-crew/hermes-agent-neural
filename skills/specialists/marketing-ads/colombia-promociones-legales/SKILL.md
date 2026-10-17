---
name: colombia-promociones-legales
description: >-
  Use when drafting Colombia promo legal packs. Colombian promo legal docs: T&C, datos, juego responsable. author: Ragnar — NeuralCrew Labs / Digital Expressions created: 2026-08-18 jurisdiction: Colombia
tags: [colombia, legal, terminos, datos-personales, coljuegos, juego-responsable]
category: legal
triggers:
  - términos y condiciones/T&C de promoción/ruleta/premio/bono/sorteo
  - política de tratamiento de datos personales/aviso de privacidad Colombia
  - juego promocional/juego de azar/Coljuegos/casino
  - juego responsable/Ley 1581 de 2012/Ley 2300 de 2023
  - reporte de compliance/promoción digital con azar
metadata:---

# Promociones y Marketing — Documentos Legales en Colombia

Clase de tarea: redactar el paquete legal de una promoción digital (ruleta, sorteo, bono) para un cliente colombiano — casinos, retail, cualquier marca que use azar con finalidad comercial — y entregarlo como documento Word.

## Marco normativo (resumen operativo — ver references/ para detalle)

| Norma | Aplica a | Punto clave |
|-------|----------|-------------|
| Ley 643 de 2001 | Juegos de suerte y azar | Monopolio estatal. Art. 5: comerciante con sorteo publicitario sin ánimo de lucro puede pedir reconocimiento de exclusión a Coljuegos. Art. 31: impuesto 14% si hay azar con lucro. |
| Coljuegos (trámite promocionales) | Promociones con azar | Promoción digital = alcance nacional → autorización ante Coljuegos; municipal/departamental → entidad territorial. Sin autorización/reconocimiento NO se publica. |
| Resolución 20244000022654 de 2024 | Juego responsable | **Vigente** (derogó la 20214000036784). Publicidad debe advertir riesgo de adicción, incluir mensaje de juego responsable y restricción +18. |
| Ley 1581 de 2012 + Decreto 1377 de 2013 | Datos personales | Autorización previa, expresa e informada; casillas no premarcadas; plazos: consultas 10+5 días hábiles, reclamos 15+15 (arts. 14 y 15). |
| Ley 1480 de 2011, art. 33 | Promociones y ofertas | Informar tiempo, modo, lugar y requisitos; los términos obligan al anunciante. |
| Ley 2300 de 2023 | Marketing (SMS, correo, WhatsApp, llamadas) | Consentimiento comercial SEPARADO y opcional + mecanismo de cancelación. |

## Workflow (verificado 2026-08-18, caso ruleta Golden Game/Paradise Club)

1. **Leer el reporte de compliance del cliente primero** (read_file extrae .docx automáticamente). El reporte ya enumera la mecánica, los bloqueadores y el marco normativo: úsalo como mapa.
2. **VERIFICAR las normas citadas en el reporte antes de escribir** — pitfall crítico: el reporte citaba la Resolución 20244000021144 como la vigente de juego responsable; la operativa es la **20244000022654 de 2024**. Nunca confiar en el número de resolución citado por el cliente; verificar en normograma.supersalud.gov.co / suin-juriscol.gov.co / funcionpublica.gov.co (curl + strip HTML).
3. **Investigar lo que falte** con `/opt/data/tools/web_search.py` (si web_search/web_extract de Hermes no están configurados, este script local es el fallback) y curl de las páginas oficiales.
4. **Redactar el paquete** con campos del operador entre corchetes [ ] — nunca inventar razón social, NIT, nº de autorización ni fórmula del bono.
5. **Generar .docx con python-docx** (preferencia del usuario: el .docx es la entrega al humano; el markdown es para el repo). Estilo: portada, encabezados dorado/oscuro, tablas para checkboxes y bloqueadores.
6. **Verificar** releyendo el .docx extraído (read_file) antes de entregar; enviar con `MEDIA:/ruta/archivo.docx` en Discord.
7. **Cerrar con el siguiente paso crítico** (p. ej. "necesitamos razón social + NIT + autorización Coljuegos antes de producción").

## Estructura del paquete legal (plantilla)

1. Términos y Condiciones de la Promoción (18 numerales — ver references/)
2. Política de Tratamiento de Datos Personales (Ley 1581 completa)
3. Aviso de Privacidad (texto corto para footer)
4. Textos del formulario (checkboxes separados)
5. Textos de Juego Responsable y barrera +18
6. Anexo A — Datos pendientes del operador (tabla: dato | responsable | estado)
7. Anexo B — Requisitos técnicos (código único, backend, estados de reclamación)

## Pitfalls

- **Casillas de consentimiento**: NUNCA premarcadas. Separar +18, T&C, tratamiento de datos (obligatorios) y comunicaciones comerciales (opcional e independiente). El silencio no es consentimiento (criterio SIC).
- **+18 es barrera de acceso, no verificación de identidad** — la validación real es con documento físico en caja. Decirlo explícito en T&C.
- **Bono ≠ efectivo**: dejar claro que el bono es crédito promocional de juego; la regla de conversión a dinero ("duplicar el bono") debe ser matemáticamente exacta y marcada [CONFIRMAR CON EL OPERADOR].
- **No mezclar T&C con tratamiento de datos ni con marketing** — cada consentimiento se guarda por separado con fecha/hora y versión del documento.
- **No inventar datos del operador** — todo lo no confirmado va entre [ ] y pasa al Anexo A como bloqueador.
- **Dejar constancia de que el documento no sustituye el concepto jurídico del operador ni la autorización de Coljuegos** — NeuralCrew implementa técnicamente lo aprobado.

## Referencias

- `references/promociones-juegos-azar-colombia-2026-08.md` — investigación normativa verificada, detalle de la Resolución 22654/2024, esquema completo del T&C y guion del generador python-docx.
