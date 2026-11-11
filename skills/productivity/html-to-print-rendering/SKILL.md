---
name: html-to-print-rendering
description: "Use when rendering HTML to print-ready PDF and hi-res PNG."
tags: [pdf, png, render, headless, html, folleto, imprenta]
version: 1.0.0
author: Ragnar
triggers:
  - folleto / flyer / infografía / prompt card / tarjeta impresa → PNG/PDF imprimible
  - el usuario pide la imagen mejorada de un diseño basado en texto (folleto, guía, poster)
  - rendir HTML exacto a imagen o PDF sin rasterizadores locales (sin chromium/cairo/wkhtmltopdf)
metadata:
  hermes:
    tags: [pdf, png, render, headless, html, flyer, print]
---

# HTML → Print Assets (PNG hi-res + PDF vectorial) vía browser headless

Cuando el entregable es un **documento con mucho texto** (folleto, guía de cuidado, prompt card, spec sheet), NO se usa IA de imágenes (revuelve las letras). Se construye como HTML/SVG con el texto exacto y se rasteriza con el browser headless remoto — texto perfecto, layout controlado.

Útil cuando faltan rasterizadores locales (sin chromium/wkhtmltopdf/cairosvg/rsvg) pero `browser_exec` (browser-use CLI) está disponible.

## Pipeline verificado (22/08/2026 — folleto Snuffle Mat A5)

1. **Escribir el HTML** con CSS de impresión:
   - `body { width: <pts-intended>px }` (A5 @300dpi ≈ 1748px de ancho), fuente system (Liberation Sans/DejaVu).
   - `* { box-sizing:border-box; min-width:0 }` + `html,body { overflow-x:hidden }` para matar overflow horizontal.
   - `@page { size: A5; margin:0 }` para exportar PDF A5 exacto.

2. **Cargar por data-URL**, NO por file:// ni IP local:
   - `file://` suele estar bloqueado (`chrome-error://chromewebdata/`).
   - URLs de IP privada (127.0.0.1) se bloquean con "Blocked: URL targets a private or internal address" — el browser remoto no llega a tu servidor local.
   - `data:text/html;base64,<b64>` SÍ funciona.
   - En `browser_exec`, el acceso a archivos funciona si lees el HTML con Python dentro del exec (`Path(...).read_bytes()`).

3. **Render + captura en 2x** (calidad imprenta):
   ```python
   cdp('Emulation.setDeviceMetricsOverride', width=1748, height=3000, deviceScaleFactor=2, mobile=False)
   cdp('Page.reload', ignoreCache=True); time.sleep(1.2)
   m = cdp('Page.getLayoutMetrics')
   cw, ch = int(m['contentSize']['width']), int(m['contentSize']['height'])
   cdp('Emulation.setDeviceMetricsOverride', width=cw, height=ch, deviceScaleFactor=2, mobile=False)
   time.sleep(1.0)
   capture_screenshot(path='/abs/out.png', full=True)   # NOTA: kwarg es full, NO full_page
   ```
   - La primera medición con `width=1748, height=3000` da el alto real; luego se re-override con el alto exacto para que el PNG no tenga espacio vacío.
   - PNG resultante ≈ 2× las dimensiones de layout (p. ej. 3278×5625 → 6556×11250 hi-res).

4. **Exportar PDF vectorial** (texto seleccionable, imprime perfecto):
   ```python
   pdf = cdp('Page.printToPDF', printBackground=True, paperWidth=5.83, paperHeight=8.27,
             marginTop=0, marginBottom=0, marginLeft=0, marginRight=0, preferCSSPageSize=True)
   Path('/abs/flyer.pdf').write_bytes(base64.b64decode(pdf['data']))
   ```
   paperWidth/paperHeight en **pulgadas**: A5 = 5.83 × 8.27. Verificar con `/MediaBox` en el binario (A5 pt ≈ 420×595).

5. **QA visual obligatorio**: `vision_analyze` sobre el PNG renderizado antes de entregar — revisar desbordes, texto cortado, iconos rotos. En esta clase de tarea el QA del render ES parte del trabajo.

6. **Entregar ambos** vía `MEDIA:/abs/out.png` + `MEDIA:/abs/out.pdf` (preferencia de usuario validada: archivo real adjunto, nunca ruta).

## Pitfalls del harness browser-use (CDP)

- **`cdp()` toma params como kwargs, NO como dict.** `cdp('Page.printToPDF', {'printBackground': True, ...})` mete el dict en `session_id` y falla con `Message may have string 'sessionId' property`. Escribir `cdp('Page.printToPDF', printBackground=True, ...)`.
- **`capture_screenshot()` NO tiene `full_page=`** — su kwarg es `full=False` (captureBeyondViewport).
- **`Emulation.setDeviceMetricsOverride`** requiere recargar después del override para que `getLayoutMetrics` reporte el nuevo tamaño.
- **Cerrar servidores temporales** (`python3 -m http.server`) tras usarlos: `process(action='kill')`; no dejarlos corriendo.

## Copy para folletos de producto (lo que el usuario valora)

- Corregir todo texto que delate IA: "Tidy man" → "Pet Safe"/"Non-Toxic"; "massage fabric folds" → "fluff the fabric folds".
- Unificar temperatura (30 °C = cold) para evitar confusión.
- Añadir advertencias de seguridad reales ("not a chew toy!", "not for aggressive chewers") — protegen de devoluciones y reviews de 1 estrella.
- Mantener marcas normativas del mercado objetivo (p. ej. sello "AU DAFF Biosecurity" en AU): son diferenciadores, no errores.

## Alternativa sin headless

- fpdf2 (ver skill `productivity/pdf-deliverables`) para PDFs de texto simple; usa este pipeline cuando el layout es rico (tarjetas, 4 columnas, iconos).

## Render local directo + rescate de fotos desde PDF del cliente (validado 27-oct, propuestas Bendabal)
- Para un PDF multipágina con layout ya estable, el render local directo es más rápido que browser_use: `/opt/chrome-for-testing/chrome-linux64/chrome --headless=new --no-sandbox --disable-gpu --allow-file-access-from-files --print-to-pdf=<out.pdf> --no-pdf-header-footer file://<abs.html>`. El flag `--allow-file-access-from-files` es OBLIGATORIO si el HTML referencia assets relativos (`../assets/...`) — sin él las imágenes no cargan y el conteo de páginas sale diferente.
- **Chromium snap inservible incluso sobreescribiendo HOME** (`cannot use invalid home directory "/opt/data"`, verificado 29-oct-2026): cuando no existe Chrome for Testing, el wrapper `/usr/bin/chromium-browser` del snap falla porque exige un `$HOME` existente (en el contenedor Hermes apunta a `/opt/data`, que no existe; pasar `HOME=` NO lo arregla: el wrapper lo relee de passwd). La salida es llamar al binario REAL dentro del snap: `HOME=<dir escribible> /snap/chromium/current/usr/lib/chromium-browser/chrome --headless=new --no-sandbox --disable-gpu --user-data-dir=<scratch>/chrome-prof --hide-scrollbars --force-device-scale-factor=1 --window-size=W,H --screenshot=out.png "file://<abs.html>"` (los errores de dbus son inofensivos). Para altura exacta sin adivinar: renderiza con ventana muy alta (p. ej. 3400) y recorta con PIL escaneando desde abajo la última fila que difiera del color de fondo del body (+~50 px de margen) — nunca corta el pie.
- QA de páginas: `pdfinfo <pdf> | grep Pages` después de CADA cambio de layout (una foto más alta devuelve un doc de 2 a 3 páginas); `pdftoppm -r 90 -png out.pdf /tmp/p` + `vision_analyze` por página, y `pdftotext ... | grep -ic "termino-prohibido"` para verificar ediciones de copy (ej. pedir quitar 'maquillaje/ofrenda').
- Fotos del cliente insuficientes (se repiten o faltan): extraer del EPK/PDF existente con `pdfimages -j -p archivo.pdf prefijo` (convertir los `.ppm` con PIL); descartar logos/afiches y elegir las fotos reales con UNA sola llamada de visión armando antes una hoja de contactos PIL (grid de thumbnails con etiquetas numeradas) en vez de analizar imagen por imagen.
- Tiras de fotos SIN recortes: NUNCA forzar el mismo `width`+`height` a fotos de ratios distintos (se cortan feo). Usar `height:<X>mm; width:auto` por foto: alturas alineadas, cada una con su ratio natural. Verificar ratios con `identify` antes de maquetar, y si un recuadro de texto sigue mostrando contenido viejo tras 'arreglarlo', releer el HTML crudo: el old_string buscado puede diferir por una tilde y el reemplazo nunca aplicó.

## Archivos

- Guardar junto a cada entregable el HTML editable (`workspace/<carpeta>/`) para re-render rápido tras cambios de copy.