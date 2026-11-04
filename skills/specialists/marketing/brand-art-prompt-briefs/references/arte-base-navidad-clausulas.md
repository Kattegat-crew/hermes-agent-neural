# Recetario de cláusulas para arte base navideño con mascota (Lucky trébol)

Caso verificado 29-oct-2026: arte base "El Aguinaldo de la Suerte" (Paradise), Flux 3 edit 1.5k con refs (lucky-master.jpg + view/front.png), v1 → QC de visión → v2 con correcciones. Cada cláusula nació de un defecto concreto del v1.

## Cláusulas que arreglaron el v1

- **Gorro navideño (anclaje):** decir que "se apoye en los lóbulos superiores" produce un LISTÓN, no un gorro. Fórmula que funcionó: brim sigue la curva superior de los lóbulos, situado "high, above the eyebrows, in the top 15% of the silhouette", "rests on the crown like a cap and never compresses or reshapes the body". La vincha/cinta ayuda como objeto externo a definir el borde superior del rostro y evitar deformaciones.
- **Accesorios adaptados al cuerpo (nunca descartarlos):** "no guantes ni zapatos" era esquivar el problema. Fórmula: mittens/botas de lana con puño de piel y pompón, "the green forearm visible above the cuff", "the accessories adapt to the character and never reshape the body".
- **Prop en mano a escala:** la boleta salió del tamaño del torso (parecía placa/pendón). Fórmula: "normal sized: it fits in his mitten and is about the length of his forearm — never oversized, never a banner, never hanging".
- **Mesa como mueble:** con el borde frontal cortado por el encuadre se lee como tapete. Fórmula: "ENTIRE front edge, its thickness and the marble floor beneath it are visible" + "his legs and the stem are hidden behind the table, not visible" (el tallo entre las piernas se lee ambiguo).
- **Pseudo-texto en el fondo:** aunque se pida cero texto, las máquinas/pantallas del fondo generan letras garbled. Cláusula: "NO LETTERING ON ANY OBJECT — machine screens and cabinets show only abstract glowing shapes and colored light".
- **Simetría espejada:** cascanueces/árboles/bastones duplicados espejados se percibe artificial. Cláusula: "the decor is ASYMMETRIC: different ornaments and props on each side, no mirrored duplication".
- **Zonas de aire para tipografía posterior:** "the top 18% and the bottom 12% of the frame stay visually calm and uncluttered (no props, no bright elements), because typography will be added there later". Adicionalmente "must still read when cropped to the central vertical 60% of the width" — habilita el recorte para la franja vertical izquierda de la boleta sin regenerar.
- **Color de competencia:** el verde navideño de fondo compite con el mascota verde. Cláusula: greenery "deep desaturated forest green (#0E3B2E), darker than the mascot, stays at the edges; the wreath and tree are darkened and out of focus" + detrás del personaje "deep wine and near-black, so his green cuts clean".

## Estructura del prompt en bloques (plantilla)

CHARACTER (identity locked, refs primero) → HAT → OTHER ACCESSORIES → TABLE/FURNITURE → ACTION (prop + escala) → HALL (asimétrico) → NO LETTERING ON ANY OBJECT → COLOR (zonas) → LIGHT → FRAMING (% de aire) → ABSOLUTELY NO TEXT.

Un bloque por tema, cada defecto del QC se convierte en cláusula específica (no en negativo genérico).
