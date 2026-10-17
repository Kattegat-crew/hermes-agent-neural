---
name: documentos-legales-entregables
description: >-
  Use when producing complete legal deliverables as .docx. Entregables legales: verificar papeles, sin huecos, .docx. hermes: tags: [legal, compliance, entregables, docx, cliente, verificacion, placeholders, documentos]
tags: [legal, compliance, entregables, docx, verificacion]
version: 1.0.0
author: hermes
metadata:
triggers:
  - "mejora/revisa este documento legal con los datos que tenemos / no dejes campos por llenar"
  - "T&C, política de datos, aviso de privacidad u otro entregable legal de un cliente (casino, promoción, contrato)"
  - "ocultar/omitir/spacios vacíos/PENDIENTE/[CORCHETES] en un documento para entregar"
  - "generar un .docx profesional con portada, índice y tablas para un cliente"---

# Producción de documentos legales/compliance entregables para clientes

Clase de tarea: el cliente (o el Administrador) pide un documento legal/compliance **completo, profesional e íntegro** usando SOLO los datos que ya existen en los papeles de la empresa. Patrón validado con Golden Game S.A.S. v2→v3 (2026-08).

Para la sustancia jurídica en Colombia (qué exige Coljuegos/Ley 643/Ley 1581 etc.), cargar la skill user-owned `colombia-juegos-promocionales` (referencia de estructura del paquete). Esta skill cubre la **mecánica de producción y calidad** que esa skill no cubre.

## Flujo de trabajo (5 pasos, orden estricto)

1. **Leer el borrador existente íntegro** (el usuario casi siempre entrega una vN con errores). Extraer .docx con `read_file` y entender cláusula por cláusula ANTES de tocar nada.
2. **Verificar CADA dato contra los papeles oficiales** (no contra la memoria ni contra la landing):
   - RUT (última versión), Cámara de Comercio (CCB/CCX), contrato de concesión/licencia, resoluciones y otrosíes, informe corporativo existente, landing/repo si existe.
   - Buscar con grep/`search_files` patrones como `CASINO <NOMBRE>`, el NIT, números de resolución, direcciones.
   - OJO: datos de MARKETING (landing, informe de marca) ≠ datos LEGALES: la landing usa direcciones de sedes genéricas («Zona Centro», «Zona Rosa», «Plaza Principal») mientras el registro oficial (anexos SIICOL del contrato) tiene la dirección exacta por local. **SIEMPRE cruzar la tabla de sedes contra los anexos de máquinas del contrato/otrosíes**.
   - Contactos: el correo/teléfonos del RUT pueden tener un celular distinto al WhatsApp comercial confirmado por el cliente; usar el confirmado por el cliente para el bloqueo de contactos y anotar el del RUT como alternativo si hace falta.
3. **Redactar íntegro sin placeholders** cuando el cliente lo pida explícitamente:
   - NUNCA inventar permisos, resoluciones o números que no obran en los papeles: citar solo los que existen (contrato, resolución, otrosíes con radicado), y cerrar las cláusulas de autorización con «sujeto a las condiciones que apruebe la autoridad competente».
   - Para campos sin dato (vigencia exacta, plazos de redención, fórmula de conversión): reescribir la cláusula para que la definición quede CONDICIONADA al operador («el Organizador lo informará por los mismos canales de difusión», «dentro del término que el Organizador indique en la constancia») en vez de `[CORCHETE]`, `PENDIENTE`, `DEFINIR` o `FECHA`.
   - Distinguir pendientes LEGÍTIMOS de huecos: los tokens del correo transaccional por participante ([NOMBRE], [CÓDIGO], [VALOR], [SEDE], [FECHA LÍMITE]) NO son espacios por llenar; son plantilla dinámica y deben marcarse como texto transaccional.
   - Si la autorización específica de la promoción (Ley 643 art. 5) no obra: no dejar la cláusula vacía; dejarla redactada para soportar la resolución que llegue y advertir que no se publique hasta obtenerla (en nota, no como hueco).
4. **Generar .docx profesional** con python-docx (receta en la siguiente sección).
5. **Verificar la entrega programáticamente** antes de reportar terminado (ver Check de calidad).

## Receta .docx profesional (python-docx)

- Tamaño Carta (Letter): `section.page_width=Inches(8.5); page_height=Inches(11)`.
- Portada: título grande + tabla de datos del organizador (2 cols) con sombreado de encabezado (`w:shd` fill `8B0000` + texto blanco) y nota itálica de exención de concepto jurídico.
- Índice general en tabla (Documento | Uso) + sección «Estado del documento» que confirma la fuente de cada dato.
- Footer con número de página: usar `w:fldSimple instr='PAGE'` pegado a un run.
- Encabezados H1 en color de marca (rojo `8B0000`), H2 oscuro; cuerpo Calibri 10.5 justificado.
- Tablas de ancho fijo (`width in Inches` en cada celda) y `Table Grid`.

## Verificación post-generación (obligatoria)

Escaneo con python-docx sobre todos los párrafos + celdas de tablas con estas regex → TODAS deben dar 0:
```
\[[^\]]*\]    PENDIENTE    DEFINIR    REVISAR    ENUMERAR    \[N ...    \[FECHA ...
```
Excepción válida: los tokens dinámicos del correo ([NOMBRE], [VALOR], [CÓDIGO], [SEDE], [FECHA LÍMITE]) si el documento los declara plantilla transaccional. Verificar además que las claves duras (NIT, n.º de resolución, cada dirección corregida) estén presentes (`if k in full`).

## Pitfalls

- No confiar en la landing/repo para direcciones ni en el informe corporativo para fechas: los papeles oficiales (RUT, Cámara, contrato y sus anexos) mandan. Cualquier inconsistencia con la vN previa es un deliverable del análisis, no un capricho.
- En un casino el bono es «crédito de juego, NO dinero en efectivo» — obligatorio en T&C.
- «Botón +18» = declaración/barrera, no verificación de identidad; la identidad se valida en caja con documento físico. Dejarlo explícito.
- El departamento en los anexos SIICOL puede venir COARSE («CARMEN DE APICALÁ/TOLIMA» en líneas separadas); al parsear unir las filas adyacentes.
- El n.º de máquinas del contrato cambia con cada otrosí — no citar el número de la resolución original como vigente.
- Reportar el bloqueador crítico (p. ej. falta la autorización específica de la promoción) aunque el documento quede íntegro: es una obligación de verdad, no un pendiente de redacción.

## Referencias
`references/golden-game-ruleta-2026-08.md` — datos corporativos VERIFICADOS de GOLDEN GAME S.A.S. (sedes + dirección legal oficial C2005, contactos, resoluciones, representante), muestra del resultado completo; usar como plantilla de datos para futuros entregables del mismo cliente.