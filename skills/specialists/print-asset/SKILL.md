---
name: print-asset
description: "Trigger: boleta, volante, flyer, imprenta, print layout, SVG a PDF, QR reusable. Build vector print pieces with real measurements and production-safe art."
license: Apache-2.0
metadata:
  author: "neuralcrew"
  version: "1.0"
---

# Print Asset

## Activation Contract

Load this skill for physical print pieces (tickets, flyers, stubs). All text is real vector text: the image model is never used for print copy. In social pieces a short decorative headline may come from the model; binding copy (dates, amounts, legal, addresses) is always composed and verified against source.

## Hard Rules

- Build layouts in SVG with physical units (mm) matching the approved size; export PDF for print plus PNG previews for review.
- Keep production notes (safe zones, specs, internal labels) OUT of printable art; they live in the manifest and previews only.
- Embed brand assets only from real repository files; record their hashes. Never redraw logos or QR matrices.
- Generate QR codes from a pinned library version into versioned SVG+PNG assets with documented URL, error correction, and quiet zone.
- NEVER invent legal, privacy, or authorization copy: use only approved text, mark pending fields explicitly.
- Identity before art: read the character registry (`assets/sheets/registry.json`) and attach only the sheet marked `locked` and current. Never attach a `deprecated` sheet, not even for comparison. When identity changes, version a new sheet and mark the old one deprecated — never overwrite the approved file.

## Decision Gates

| Situation | Action |
|---|---|
| Missing tool (cairosvg, reportlab) | Deliver SVG + PNG and record the exact gap; install nothing without pinned version plus human approval |
| Slot/cut/substrate unknown | Use the standard proposed size, flag provider validation as blocking for the final master |
| Numbering or personalization | Placeholder in art (`Nº ______`); consecutive numbering applied by the print shop |

## Execution Steps

1. Confirm size, sides, fonts (pinned system fonts), colors, and copy sources with their approval status.
2. Compose front and back with safe margins, fold/cut marks, and writable light areas for hand-filled fields.
3. Export print PDF at final size, PNG previews, and a manifest with dimensions, fonts, hashes, method, cost 0.00, and QC.
4. Verify visually: exact spelling, no production marks in art, occlusion, contrast, safe zone.

## Raster path (Pillow) para piezas con arte fotográfico/mascota

Cuando la pieza lleva hero art o mascota integrada (no solo vectores), el layout SVG puro pierde; usar raster 300 dpi con Pillow sobre un lienzo calculado desde unidades físicas:

- Helper `px(mm)` único: `round(mm / 25.4 * 300)` — TODAS las coordenadas pasan por él; jamás mezclar píxeles crudos con mm.
- Frente y reverso en UNA orientación de lienzo: componer ambos en landscape horizontal y rotar el reverso 90° para la tarjeta vertical final. Evita duplicar todo el layout en dos sistemas de coordenadas.
- Formato estándar talonario 85×54 mm (boleta) y su vertical 54×85 mm (tarjeta de sellos); un solo tamaño para toda la campaña (semanales y final comparten matriz de imprenta).
- Pliego A4 8-up (2480×3508 px a 300 dpi): 2 columnas × 4 filas alternando frente/reverso; márgenes resultantes ≥10 mm validados por cálculo (`(A4 - n*pieza)/2/300*25.4`).
- **Regla de composición verificada (QA de visión, 3 iteraciones):** el título NUNCA va sobre el personaje, ni con scrim. El hero sangra el tercio superior y el título va sobre fondo liso debajo del degradado de fundido. Un scrim 235/255 sobre cara amarilla deja contraste oro-sobre-oro ilegible en la zona del texto.
- Casillas para marcar con lapicero: cuadrados DIBUJADOS (`d.rectangle`) de ~2.8 mm, nunca corchetes `[ ]` tipográficos — el gap no da para una X legible a mano y en mostrador.
- Pieza diligenciada de pie (boleta) = cero ornamento, máx. 4 campos; pieza que el cliente conserva semanas (tarjeta) = mascota y ornamento. Firma doble (cliente + quien entrega) al reverso.
- Pie legal pendiente: banda sólida con placeholder explícito tipo "PIE LEGAL PENDIENTE (C6) – 18+" dentro del arte; es el único marc interno permitido porque reemplaza texto obligatorio aún no aprobado.
- Pie legal: mínimo 5,5 pt (Coljuegos). Medir el ancho real con `d.textlength` ANTES de fijar el cuerpo; si no cabe, ampliar la banda (p. ej. de x0 del formulario al borde del arte) en vez de bajar la fuente, y dejar `assert ancho <= banda` en el generador para que ningún ajuste futuro lo degrade en silencio.
- Arte de panel = la escena ACORDADA con el cliente, no un recorte del maestro de campaña. Si la escena dedicada aún no existe: montar la pieza con el recorte marcado como PROVISIONAL en la spec, dejar el prompt de la escena escrito en `prompts/<cliente>/` con modelo/refs/costo, y hacer que el generador acepte el swap vía spec (`arte.fuente` + `arte.centro_x_pct`) SIN tocar el diseño — el re-render tras generar debe ser cambio de dos valores, no re-layout.
- Ornamento de margen separador: los motivos repetidos a intervallos/ángulos irregulares (guirnalda de ramos sueltos) leen como "sucio" en QA de visión. Usar una banda sólida (color de acento) con patrón de período fijo, ángulos alternados consistentes y margen sólido a cada lado del motivo; además debe empatar cromáticamente con la banda del pie para cerrar el sistema.
- Nivel de elaboración del reverso = espejar la ESTRUCTURA del reverso ya aprobado de referencia (mismo cliente hermano, p. ej. Golden): banda de título, discos numerados, cajas con etiqueta interna, cláusula, doble firma y sello legal. El estándar está en la estructura, no en el adorno; subir el estándar implica rehacer AMBAS caras versionadas (v2), no retocar la v1.
- Un solo sistema tipográfico por cara: si el frente usa serif display para el titular, el reverso hereda la misma familia; mezclar fuentes entre caras lee como pieza de proveedores distintos.

## Verification

- Cada pieza pasa QA de visión con checklist de colisiones (título vs cara, fechas vs notas, filas vs banda legal) ANTES de subir a Drive; las correcciones se re-renderizan y re-QA — nunca se entrega la primera pasada.
- Verificar dimensiones de pliego programáticamente (PIL `im.size`) y márgenes por cálculo; el QA de visión sobre PNG >2000 px puede fallar intermitente — downsample 1/3 o confiar en el cálculo.

Return: SVG/PDF/PNG paths, verified physical dimensions, hashes, QC results, and the pending list blocking the final print master.

- Raster/Pillow para piezas con hero art o mascota: ver `references/pil-raster-printables-recipe.md` (mm→px 300 dpi, frente/reverso espejados, pliego A4 8-up, regla título-bajo-fundido).

## References

- `references/print-asset-checklist.md` — pre-press checklist and manifest fields.
