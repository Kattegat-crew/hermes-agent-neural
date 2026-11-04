# Copy de casino que Meta aprueba (evidencia del kb, 11-sep-2026)

Fuente: `kb/ad.jsonl` del repo del generador — 54 anuncios de la **Meta Ad Library** con `semaforo`
(verde / amarillo). **13 en verde**, corriendo **48-85 días seguidos**: son el molde de lo que Meta
deja correr.

## Los verdes (cita literal)

| Anunciante | Categoría | Copy |
|---|---|---|
| Choctaw Casinos & Resorts | casino land-based US | *"A world-class casino and resort experience awaits in Durant, OK where you can game, dine, and relax all night"* |
| Choctaw Casinos & Resorts | casino land-based US | *"Come for the show. Stay for the fun. Live concerts and a full resort experience await"* |
| Choctaw Casinos & Resorts | casino land-based US | *"A state-of-the-art poker room. Fine dining. Epic concerts. A world-class casino and resort experience awaits in Durant, OK."* |
| Jamul Casino Resort | casino land-based US | *"San Diego's Closest Casino Resort to Downtown, Jamul Casino Resort!"* |

Patrón inequívoco: **lugar + experiencia** (comer, beber, shows, el resort, la cercanía). **Ninguno**
dice cuánto se gana, cómo funciona un premio, ni menciona cifras, balotas u odds.

> Nota: los verdes de "social casino" (`Ready to win big? Try over 100+ FREE Slot Machines`, `Continue
your play streak for bigger daily gifts`) son otra clase de anunciante — app de casino social/gratuito,
no un casino land-based con promoción real. **No usar ese registro como molde** para Golden/Lucky: es
justo el léxico que Meta sí tolera en apps gratuitas y castiga en promoción de juego real.

## Tabla de reparto

| Elemento | Ad de Meta | Copy del post + landing | Pieza de salón |
|---|---|---|---|
| Cifras ($400.000 / $1'600.000) | ✗ | ✓ | ✓ |
| Mecánica y "un bingo por jornada" | ✗ | ✓ | ✓ |
| Fechas exactas y dirección | ✗ | ✓ | ✓ |
| Pie legal `+18 / Coljuegos` | ✗ en la pieza | ✓ en el copy | ✓ en pantalla |
| Cuándo se canta, balota, "cae" | ✗ | ✓ | ✓ |
| Experiencia: pueblo, gente, música, comida | ✓ | ✓ | ✓ |
| Acumulado como **existencia** (sin cifra) | ✓ (a validar) | ✓ | ✓ |
| CTA | clic a la página | — | dirección física |

## Léxico vigilado

Levantan el flag: **"premio"**, **"gana / gánate"**, cifras de dinero, **"cae / se reparten"**,
balotas, **"apuesta"**, **"azar"**, y **"suerte" como promesa** (no como nombre del personaje).
El objetivo del ad es el **clic**: la mecánica y el registro viven en la página de destino.

## Camino que pasa la revisión limpio

Documentado en la operación el **08-sep-2026**: publicar primero el reel **orgánico** de la página y
luego **montarlo como anuncio desde Ads Manager**. Evita el subcode `1885183` de Composio al crear
creatives por API, hereda la prueba social de la publicación y **pasa la revisión de Meta sin
fricción**.

## Cómo auditar copy nuevo contra esta base

1. Buscar el nicho en `kb/ad.jsonl` (por `categoria` y `semaforo`) y leer los verdes de la categoría.
2. Comparar el guion candidato contra el patrón de esos verdes: ¿habla de lugar y experiencia, o de
   premios y mecánica?
3. Si el copy menciona cifras, balotas o dinámica de juego, sacarlo de la pieza y mandarlo al copy
   del post y a la landing — no "suavizarlo" dentro del anuncio.
