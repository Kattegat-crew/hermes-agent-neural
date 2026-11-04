---
name: brand-logo-composites
description: "Use when compositing client logos into one brand image."
tags: [logos, pil, composicion, marca, branding, imagen, neuralcrew, glow]
---

# Brand Logo Composites (PIL, estático)

Componer logos reales (PNG/JPG) en una sola imagen de marca con fondo temático — p.ej.
la red neuronal cian de NeuralCrew con hexágonos, nodos y cables — SIN depender de
generación por modelo (los logos quedan fieles). Patrón verificado 2026-08-19.

## Workflow

1. **Inspecciona primero.** `Image.open(p).convert('RGB')` con la imagen RGB, muestra
   las 4 esquinas (`getpixel`), confirma fondo uniforme (blanco/gris ~247). Anota
   tamaños para el layout.
2. **Quitar fondo** con flood-fill desde las 4 esquinas. ⚠️ `ImageDraw.floodfill`
   es FUNCIÓN de módulo, no método:
   ```python
   from PIL import Image, ImageDraw
   im = Image.open(p).convert('RGBA'); w, h = im.size
   for (x,y) in [(2,2),(w-3,2),(2,h-3),(w-3,h-3)]:
       ImageDraw.floodfill(im, (x,y), (0,0,0,0), thresh=22)   # NO im.draw.floodfill
   bbox = im.getbbox()
   if bbox: im = im.crop(bbox)
   ```
   - Texto gris/metálico (p. ej. "CREW" gris) → thresh BAJO (~22) para no comerse el gris.
   - Contenido de color vivo → thresh ~28.
3. **Fondo temático:** gradiente navy por píxel + overlay de hexágonos con alpha baja
   (~22) + capa de partículas (puntos cyan aleatorios).
4. **Capas de glow:** elipses concéntricas de alpha decreciente detrás de cada logo
   (color por nodo: cyan para NeuralCrew, dorado para casinos).
5. **Conexiones neuronales:** 2 pasadas — halo ancho (alpha ~40) + núcleo fino
   (alpha ~200) — con "pulsos de datos" (puntos a lo largo del cable).
6. **Sombras:** capa RGBA con el alpha del logo → GaussianBlur → offset (~+6,+16)
   debajo del logo, luego `alpha_composite` del logo encima.
7. **QA obligatorio antes de entregar:** `vision_analyze` del PNG final — preguntar si
   los logos quedaron limpios (sin cajas blancas ni halos que parezcan "pegados") y
   temática coherente. No entregar sin verificar; si el vision describe bordes o
   franjas, subir thresh del floodfill y regenerar.

## Alta resolución y realce de logos (corrección usuario: "está en baja resolución")

- **Canvas mínimo 3000-3600px de ancho** (no 2400×1600). Los logos comprimen y se ven
  borrosos: renderizar SIEMPRE en alta resolución (p. ej. 3600×2400).
- **Realzar CADA logo antes de componer** (los logos fuente son 500-1500px y llegan
  suaves). Ayuda `rgb` a recortar y subir calidad:
  - `clean_alpha`: limpiar el halo blanco del recorte → alpha → `GaussianBlur(1.2)` →
    threshold 130 → `MaxFilter(3)`.
  - `enhance`: `ImageEnhance` (Color 1.05-1.16, Contrast 1.05-1.12, Sharpness 1.05-1.20)
    — separar canales RGB e integrar el alpha al final (no enhancar RGBA directo).
  - `upscale`: redimensionar con Lanczos ×1.5-1.6 + `UnsharpMask(radius=1.6, percent=110)`
    para nitidez. ⚠️ Unsharp agresivo (radius 2.2+, percent 130+) amplifica el ruido de
    los logos AI-vector → el logo queda "glitchy/noise". Usar valores suaves.
- **Glow exterior** por logo (alpha 0.45-0.55) para integrar cada marca con el tema;
  un glow muy brillante (0.62+) crea halo blanco pegajoso.
- `vision_analyze` del PNG final y comparar contra la v1 si hay una — pregunta por
  franjas, halos blancos y nitidez. Iterar.

Funciones reutilizables (clean_alpha / enhance / upscale / outer_glow): ver
`references/pil-composite-utilities.md`.

## Pitfalls
- `MaxFilter(n)` exige n **impar** (3, 5, 7...) — `MaxFilter(2)` revienta con
  `ValueError: bad filter size`.
- `outer_glow` con mask: no se puede `paste(gcol, (0,0), mask)` con mask de tamaño
  distinto al obraz del paste → `ValueError: images do not match`. Construir el glow
  sobre canvas padded: `ga = Image.new('L', (w+2*bl, h+2*bl)); ga.paste(a, (bl, bl));`
  y ahí sí `GaussianBlur` + `putalpha`.
- floodfill muta la imagen y pinta con el color de relleno; el anti-alias deja franja
  clara → sombra + glows la disimulan sobre fondo oscuro.
- Nombrar la capa Image y también una función igual (`wire = Image.new(...)` +
  `def wire(...)`) — la def pisa la variable → `alpha_composite(im, wire)` pasa una
  función. Renombrar la función (`draw_wire`).
- Verificar SIEMPRE con vision antes de enviar; confiar solo en que el script corrió
  no basta.

## Alternativa con modelo
Para un look "generado" (no fiel a los logos) usar flux-2-klein (ver skill
`devops:nan-builders-api` text-to-image). Para piezas de marca con logos reales, la
composición PIL es mejor.