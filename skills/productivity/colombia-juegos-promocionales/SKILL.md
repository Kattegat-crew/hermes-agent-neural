---
name: colombia-juegos-promocionales
description: >-
  Use when drafting Colombia casino promotion compliance. Usar al redactar compliance de promociones en Colombia. hermes: tags: [colombia, legal, compliance, casinos, coljuegos, promociones, datos-personales]
tags: [colombia, legal, compliance, coljuegos, promociones, datos]
version: 1.0.0
author: hermes
license: MIT
metadata:
triggers:
  - T&C / términos y condiciones de promoción, sorteo, rifa o ruleta
  - casino / juegos de suerte y azar / Coljuegos / bono promocional
  - política de tratamiento de datos / aviso de privacidad Colombia (Ley 1581)---

# Compliance de Juegos Promocionales en Colombia (casinos, ruletas, sorteos)

Marco verificado el 2026-08-18 para la promoción «Ruleta Golden Game» (Golden Game S.A.S.).
Aplica a cualquier promoción con componente de azar en Colombia.

## 1. Marco normativo (verificado en fuentes oficiales)
| Norma | Qué exige |
|-------|-----------|
| Ley 643 de 2001 | Monopolio estatal. Art. 4: prohibido ofrecer juegos a menores de 18. Art. 5: los comerciantes pueden hacer juegos promocionales con finalidad publicitaria sin ánimo de lucro SI obtienen reconocimiento de exclusión ante Coljuegos. Art. 31: impuesto del 14% si hay azar con lucro (autorización + impuesto son concurrentes) |
| Coljuegos | Promoción digital = alcance NACIONAL → trámite ante Coljuegos (no entidad territorial). Si es solo municipal/departamental, entidad territorial. Requiere: reglas claras, plan de premios con respaldo, conservación de soportes |
| Resolución 20244000022654 de 2024 | JUEGO RESPONSABLE (deroga la 20214000036784). Publicidad debe: advertir riesgo de adicción, incluir mensaje de juego responsable y restricción +18. ⚠️ No citar la 20244000021144 — apareció en un reporte de cliente pero la vigente verificada es la 22654/2024 |
| Ley 1581 de 2012 + Decreto 1377/2013 | Datos personales: autorización previa, expresa e informada; finalidades; derechos del titular; consultas respondidas en 10 días hábiles (+5), reclamos en 15 (+15); casillas NO premarcadas (criterio SIC: silencio/inacción no es consentimiento) |
| Ley 1480 de 2011, art. 33 | Promociones y ofertas: informar tiempo, modo, lugar y requisitos; los términos obligan al anunciante |
| Ley 2300 de 2023 | Comunicaciones comerciales (SMS, correo, WhatsApp, llamadas): consentimiento previo, expreso, informado, SEPARADO y opcional; revocable en cualquier momento |

## 2. Paquete de documentos para una promoción de casino
1. **Términos y Condiciones** (18 cláusulas: organizador con razón social/NIT/contacto; autorización con número de resolución/radicado; vigencia; sedes y ámbito territorial; participantes +18; mecánica exacta; participación única; naturaleza del bono — NO es dinero en efectivo; regla de conversión «duplicar el bono» con definición matemática exacta; vigencia del bono; restricciones; procedimiento de redención con documento físico; fraude; datos personales; juego responsable; PQR; modificaciones; legislación/jurisdicción)
2. **Política de Tratamiento de Datos Personales** (responsable, marco, definiciones, datos, finalidades, autorización, derechos, canales, transferencias, seguridad, conservación, menores, cookies, vigencia)
3. **Aviso de Privacidad** (texto corto para footer/formulario)
4. **Textos del formulario**: 4 checkboxes separados y NINGUNO premarcado — (1) +18 obligatorio, (2) acepto T&C obligatorio, (3) autorizo tratamiento de datos obligatorio, (4) comunicaciones comerciales OPCIONAL
5. **Textos de Juego Responsable**: modal +18 («declaración/barrera, NO verificación de identidad» — la identidad se valida en caja con documento físico), banner «Juega con moderación… Prohibido para menores de 18», mensaje tras el resultado, correo de constancia
6. **Anexos**: tabla de datos pendientes del operador + checklist técnico

## 3. Pitfalls críticos
- **Concesión de operación ≠ autorización de la promoción**: un casino puede tener contrato de concesión Coljuegos (p. ej. C2005 de 2023 para tragamonedas) y AÚN ASÍ necesitar autorización o reconocimiento de exclusión específico para la promoción. No usar el sello de la concesión como si autorizara la ruleta.
- **Verificar la norma vigente**: no confiar en las citas de un reporte de cliente; confirmar en fuente oficial (normograma/SUIN) qué resolución derogó a cuál.
- **El bono no es efectivo**: dejar explícito que es crédito de juego y que el retiro en dinero solo opera bajo la regla aprobada (ej. saldo ≥ 2x del nominal → retiro hasta 100% del nominal). Si el cliente no definió la fórmula, proponerla y marcarla como PENDIENTE DE CONFIRMACIÓN.
- **Datos del operador entre corchetes**: redactar con placeholders [RAZÓN SOCIAL], [NIT], etc. y luego llenarlos desde la documentación real del cliente (RUT, Cámara de Comercio, contrato) — ver skill `google-drive-access`.
- **Responsabilidades**: el casino aprueba jurídicamente los textos; la agencia implementa técnicamente. Siempre nota final: «no sustituye el concepto jurídico del operador ni la autorización de la autoridad competente».

## Referencias
`references/estructura-paquete-compliance.md` — detalle cláusula por cláusula del T&C y de la política de datos, listos para adaptar.
