---
name: manual-operativo-promociones
description: >-
  Use when writing casino staff operating manuals. Manual operativo de casino para cajeras y personal. hermes: tags: [manual, operativo, cajeras, casino, promociones, bingo, redes-sociales, deliverable]
tags: [manual, operativo, casino, cajeras, promociones, docx, redes]
version: 1.0.0
author: hermes
license: MIT
metadata:
triggers:
  - manual para cajeras o personal de local de casino
  - promocion presencial (bingo, ruleta, sorteos) que necesita instrucciones operativas por local
  - manual a partir de terminos y condiciones de una promocion de casino
---

# Manual operativo de promociones (personal de local / cajeras)

Clase de trabajo: a partir de los T&C aprobados de una promoción de casino (bingo, ruleta, sorteo), producir el manual operativo que el personal del local (cajeras, piso) sigue en cada jornada. Validado con el Bingo Millonario × Amor y Amistad (Golden Game + Lucky Brothers, sept-oct 2026): estructura aprobada por el Admin sin cambios.

## Flujo

1. **Leer los T&C de TODAS las empresas participantes** (p. ej. un PDF por empresa — Golden y Lucky tenían NLC-0002 y NLC-0003 con la misma mecánica y sedes distintas). Extraer: organizador/NIT, vigencia, sedes, mecánica, premios/acumulado, evidencia obligatoria, restricciones.
2. **Pre-work con el cliente en UNA tanda de clarify** (5 preguntas independientes, batch):
   - Alcance: ¿manual genérico multi-empresa (con campos por local) o uno por empresa? → Jonathan eligió genérico.
   - Sedes: ¿confirmadas? Si no, marcarlas «por confirmar» — NUNCA inventar direcciones.
   - Rol operativo: ¿quién hace registro obligatorio + verificación de saldo + entrega de cartón? (respuesta típica: la cajera).
   - Redes sociales: ¿a dónde envían fotos/videos? (respuesta típica: WhatsApp interno/Drive, publica el Admin).
   - Formato: DOCX editable + PDF imprimible (preferencia de Jonathan).
3. **Generar DOCX (membrete NeuralCrew) + PDF** y entregar AMBOS con `MEDIA:` en el chat.
4. **Puntos abiertos quedan en el DOCX editable** con la marca «Por confirmar» — el cliente los completa; no bloquear la entrega por ellos.

## Estructura validada del manual

1. Portada: membrete NeuralCrew (CLIENTE/FECHA/ASUNTO/DOC Nº), título, temática, vigencia.
2. Datos de la promoción (empresas organizadoras + NIT, vigencia, acumulado independiente por local).
3. Sedes participantes (tabla empresa/sede/dirección; marcar lo que falte).
4. Reglas rápidas: bingos por jornada, cartón por persona, +18 con documento físico, saldo mínimo en máquina, registro obligatorio, empleados NO / parientes 2.º grado SÍ.
5. Paso a paso de la cajera: verificar documento → confirmar cliente activo → verificar saldo → registrar datos → entregar cartón → explicar mecánica (gritar «¡Bingo!», cartón a disposición del personal).
6. Premios y acumulado: tabla escalera por jornada + reglas de pago (≤53 balotas = acumulado, >53 = premio fijo, gran final sin regla, empate se divide).
7. Entrega de premio + evidencia (obligatorio): verificar identidad + cartón válido, pagar en efectivo, diligenciar constancia, adjuntar copia del cartón, conservar.
8. **Apoyo en redes sociales** — sección que el Admin valora especialmente (ver abajo).
9. Contacto y soporte.
Anexo A: constancia de entrega de premio (campos = los de la cláusula de evidencia).
Anexo B: planilla de registro de participantes (una fila por persona).

## Sección de redes sociales (crítica para el cliente)

- Objetivo: capturar material para publicar; NADIE publica directo — todo se envía al equipo (WhatsApp interno/Drive).
- Qué capturar: fotos del ambiente (mín. 3), fotos del ganador con premio (mín. 2-3), videos verticales para stories (mín. 2 de 10-15 s por bingo: desarrollo, grito «¡Bingo!», entrega), bono: testimonio de cliente.
- Cómo: celular en vertical, buena luz, varias tomas, cuidar que no salgan pantallas de máquinas con datos de clientes.
- Reglas de oro: nunca capturar menores (+18), preguntar permiso al ganador («¿Autoriza que publiquemos su foto?»), no publicar directo, solo participantes activos.
- Etiqueta de envío: local (sede) + fecha + jornada (ej. «Chiquinquirá S1 - 04/09 - J1»); separar por bingo si hay varios ganadores.
- Checklist por jornada (7 ítems imprimible).

## Generación técnica

- **DOCX**: adaptar el patrón de la skill `neuralcrew-letterhead` (script de referencia: `gen_manual_asistentes.py` — headers con tabla invisible fixed, líneas doradas con `w:pBdr`, metadata, footer). Ejecutar con `uv run --with python-docx --with pillow python3 script.py`.
- **PDF**: fpdf2 (ver skill `pdf-deliverables`) con DejaVuSans; **NO existe DejaVuSans-Oblique.ttf en el VPS** → para itálica registrar la fuente regular (`pdf.add_font("sans","I",FONT)`). Tablas con `cell(border=1)` fila a fila.
- **Verificar SIEMPRE ambos** con `read_file` (extrae texto de .docx y .pdf) antes de entregar — no confiar solo en que el script corrió.

## Pitfalls

- **Errores de sintaxis python-docx**: coma colgante en llamadas (`heading("x", )`) y `enumerate([...]` sin cierre `], start=1):` — el lint los atrapa; corregir antes de ejecutar.
- **No inventar datos pendientes**: direcciones, contactos, cuentas de redes → «Por confirmar» en el DOCX editable. Nunca rellenar de memoria.
- **Los T&C no son instrucción operativa**: el manual traduce cláusulas legales en pasos de cajera; no copiar el texto legal tal cual.
- **El PDF no se genera desde el DOCX** (sin LibreOffice en el VPS): generar ambos por separado con el mismo contenido.

## Referencias

`references/bingo-millonario-2026.md` — detalle del caso validado: sedes Golden/Lucky, escalera del acumulado, estructura del manual entregado (NLC-0004).
