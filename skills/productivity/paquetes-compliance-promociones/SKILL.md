---
name: paquetes-compliance-promociones
description: >-
  Use when one campaign needs a legal pack per company. T&C multi-empresa: un documento legal por organizador. hermes: tags: [legal, compliance, docx, promociones, multi-empresa, casinos, colombia]
tags: [legal, compliance, docx, promociones, multiempresa, casinos, colombia]
version: 1.0.0
author: hermes
metadata:
triggers:
  - T&C / términos y condiciones de una promoción que une a DOS o más empresas (cada una con su propio documento)
  - "generar documento legal por empresa / no pueden compartir documentos"
  - verificar que un .docx no tenga huecos ([CORCHETE], PENDIENTE) ni contenido contaminado de otro cliente
  - el operador decide NO tramitar autorización de la promoción (posición: es marketing)
---

# Paquetes de compliance para promociones de casino multi-empresa

Capa de ENTREGA y VERIFICACIÓN para paquetes legales de promociones. La sustancia jurídica
Colombia (Ley 643, Coljuegos, Ley 1581, Res. 20244000022654/2024) y la mecánica de redacción
cláusula por cláusula viven en skills de usuario que NO se editan:
- `colombia-juegos-promocionales` (marco normativo + estructura 18 cláusulas)
- `documentos-legales-entregables` (flujo de producción .docx + verificación de datos contra papeles)
Si esas skills están desactualizadas, proponer `hermes curator adopt <nombre>`; no intentar parchearlas.

Patrón validado: campaña Bingo Millonario sept 2026 (Golden Game S.A.S. + Lucky Brothers SAS).

## Reglas duras de esta clase de trabajo

1. **Una promoción conjunta = UN documento POR empresa.** Cuando la campaña une a dos
   organizadores (misma mecánica, misma marca paraguas), NUNCA entregar un T&C compartido
   con dos organizadores. El cliente lo rechaza («no pueden compartir documentos»). Cada
   documento debe ser autónomo: organizador (razón social/NIT/domicilio/rep. legal/contacto),
   sedes propias, acumulado/premios propios, anexos propios.
2. **Verificar aislamiento programáticamente, no solo completitud.**
   - Claves propias presentes: `if k in full` (NIT, sedes, contactos, resolución).
   - Claves del DOC VECINO ausentes: en el doc de la empresa A, confirmar que NIT/sedes/
     contactos de B NO aparecen y viceversa. Un check de solo «claves presentes» NO detecta
     contaminación cruzada entre documentos.
3. **Regex de huecos con límites de palabra** en el escaneo post-generación:
   `\[[^\]]*\]|\bPENDIENTE\b|\bDEFINIR\b|\bREVISAR\b|\bENUMERAR\b`.
   Sin `\b`, `PENDIENTE` da falso positivo dentro de `INDEPENDIENTE` (verificado).
   Excepción válida: tokens transaccionales dinámicos ([NOMBRE], [CÓDIGO], [SEDE]) si el
   documento los declara plantilla de correo.
4. **Decisión regulatoria del operador.** Si el operador decide NO tramitar la autorización
   del juego promocional (posición: «esto es marketing, no necesitamos Coljuegos», Ley 643
   art. 5), respetar la decisión: redactar la cláusula de régimen conforme a ella y dejar una
   advertencia jurídica de RASTREO (no bloqueante) en «Estado del documento», citando que una
   promoción con azar y premio en dinero puede encuadrar en el régimen de juegos promocionales
   (reconocimiento de exclusión). La entrega NO se bloquea por esa decisión, pero queda
   registrada quién la tomó.
5. **Confirmaciones del operador → anexo CONFIRMADO / ABIERTOS.** Cuando el cliente resuelve
   los puntos pendientes por chat o reunión: incorporarlos como listas «CONFIRMADO por el
   Operador» y «PUNTOS ABIERTOS / POR VERIFICAR» en un anexo; no reescribir cláusulas ni dejar
   huecos en el borrador. Subir versión nueva solo cuando el cliente lo pida o los puntos
   queden cerrados.

## Patrón de implementación (scriptable)

- Un script Python por entrega, con un dict `*_CFG` POR EMPRESA (razon, nit, replegal,
  contacto, sedes, accent, confirmados, abiertos, checklist) y una función `build_tc(cfg, path)`
  que genera el .docx completo. Cambiar un dato = editar el dict, no el script.
- Acumulado/premios compartidos o por local: si la mecánica dice «independiente por local»,
  decirlo explícito en la cláusula y en una nota bajo la tabla referencial.
- Evidencia de premios (constancia firmada + copia del cartón) como cláusula propia + checklist
  técnico cuando el cliente lo exige («cuando ganen tiene que quedar evidencia»).

## Verificación previa a reportar terminado

Escaneo con python-docx sobre párrafos + celdas de tablas: 0 tokens (regex con `\b`),
claves propias presentes, claves del vecino ausentes. Imprimir el detalle (huecos/faltan/fuga)
antes de declarar OK.

## Referencias
`references/golden-lucky-bingo-2026-09.md` — campaña Bingo Millonario (Golden + Lucky, sep 2026):
mecánica confirmada por el operador, decisión de documentos separados, rutas de entregables y
puntos abiertos. Plantilla de datos para futuras promociones conjuntas de estos clientes.
