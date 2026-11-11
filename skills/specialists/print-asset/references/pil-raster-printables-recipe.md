# Recipe: imprimibles raster con Pillow (verificado 28-oct-2026, campaña Aguinaldo Golden)

Contexto: tarjeta de sellos 54×85 mm, boleta 85×54 mm y pliego A4 8-up para imprenta, con mascota (Goldie) como hero art. Script canónico: `marketing-campaign-generator/scripts/print/aguinaldo_print.py`.

## Estructura del script

1. `MM = 25.4 * 300 // 25.4` → `px(mm) = round(mm * 300 / 25.4)`; helper único para todo el layout.
2. Fondo: degradado vertical de la paleta (interpolación por fila) + marco doble dorado.
3. Hero art a sangre: `resize` del PNG de mascota a ancho completo, crop proporcional al alto de banda, fundido a fondo con gradiente alfa (numpy: `a = 0 if t < X else int(250*(t-X)/(1-X))` por fila).
4. Texto: fuentes locales (DM Serif Display para títulos, DM Sans para UI), soportan tildes/UTF-8 — usar "miércoles", "años", nunca texto sin tildes por miedo a la fuente.
5. Reverso espejado: componer en canvas landscape y rotar.
6. Export: PNG 300 dpi + PDF (img2pdf) + pliego A4.

## Iteración de layout con QA de visión (ciclo real de 3 pasadas)

| Pasada | Defecto detectado | Corrección |
|---|---|---|
| 1 | Título sobre la cara de la mascota con scrim; fechas fila 2 casi tocando nota | Mover título bajo el fundido; aumentar espacio |
| 2 | Scrim 235 deja contraste oro-sobre-oro sobre cara amarilla | Sacar el título del hero definitivamente: fondo liso |
| 3 | 8/10, margen inferior ajustado, print-ready salvo pie legal | Congelar |

Lección: scrim fuerte NO salva texto sobre mascota; reposicionar el texto fuera del hero es la única corrección que pasa QA.

## Boleta de mostrador (4 campos máx.)

- Orden de llenado real: número (campo más grande arriba), sorteo, sede, fecha.
- Casillas dibujadas 2.8 mm con `d.rectangle(outline, width=px(0.28))` + etiqueta al lado.
- "FECHA" ambiguo → "FECHA DE VENTA" (el cajero duda entre fecha de venta y de sorteo).
- Sin mascota: cada elemento gráfico retrasa el llenado con fila esperando.

## Pliego A4 8-up

- 2 col × 4 filas, alternando frente/reverso verticalmente (al cortar, cada pila intercala caras).
- Márgenes: `(3508 - 4*709)/2 = 336 px = 28.4 mm` vertical, 14 mm horizontal — validar por cálculo, no a ojo.

## Pendientes de bloqueo por aprobación humana

- Pie legal real (C6): Coljuegos provee sellos oficiales («SELLO AUTORIZA COLJUEGOS», «JUGAR LEGAL ES APOSTARLE A LA SALUD») — incorporar como imagen en la banda una vez confirmado vigencia.
- Número de sellos (5 vs 6) y fecha de arranque: ajustar filas, fechas impresas y TyC juntos.