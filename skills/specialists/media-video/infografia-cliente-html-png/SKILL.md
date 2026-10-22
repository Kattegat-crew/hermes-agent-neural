---
name: infografia-cliente-html-png
description: "Use when a client needs an explanatory infographic."
tags: [infografia, html, png, chrome-headless, cliente, vision]
version: 1.0.0
author: ragnar
triggers:
  - "explicame graficamente"
  - "de la manera mas simple"
  - "para cualquier persona"
  - "infografia"
  - "como funciona todo"
---

# Infografia para cliente: HTML -> PNG

Para explicar "como funciona todo" a alguien NO tecnico: una sola imagen, en palabras llanas, con las cifras REALES del sistema. Validado con el Admin 11-sep-2026 (generador de campanas).

## Regla de oro del contenido

- **El texto grande es para cualquiera** (cero jerga). La jerga va SOLO en una etiqueta gris pequena debajo (`<span class="tech">`): da credibilidad tecnica sin estorbar.
- Cada paso = **titulo llano + 1-2 frases de beneficio + etiqueta tecnica**. Nada mas.
- **Verifica las cifras ANTES de dibujar** (piezas por estado, servicios vivos, canales). Nunca inventes un numero en una imagen que el cliente va a mirar.
- Incluye las **reglas duras** del sistema (aqui: "nada se paga sin su firma") y los **estados** de una pieza como cadena de pildoras.
- Separa al final **que ya opera** de **que falta**: el cliente necesita saber donde esta el borde real.

## Estructura que funciono

1. Cabecera: titulo de 2 lineas + "quien eres" a la derecha.
2. **Flujo vertical numerado** (8-9 pasos): circulo de color + tarjeta blanca con borde izquierdo del color de la fase, unidas por una linea vertical (la ultima tarjeta no lleva raya).
3. **Columna lateral**: "quien hace que" (humanos vs IA), la regla dura en recuadro de alerta, y los 4 estados.
4. Pie oscuro con el resumen y 2-3 cifras grandes.

Paleta por FASES: idea/plan = azul `#1F3A5F`, produccion = oro `#B8860B`, control = rojo `#AB0F15`, publicacion = verde `#0E6B3A`. Fondo `#EEF2F7`, tarjetas blancas.

## Render (DEV)

```bash
/opt/chrome-for-testing/chrome-linux64/chrome --headless=new --no-sandbox --disable-gpu \
  --hide-scrollbars --force-device-scale-factor=2 --window-size=1400,1620 \
  --screenshot=/root/hermes-agent-legacy-docker/data/drafts/salida.png file:///root/hermes-agent-legacy-docker/data/drafts/salida.html
chown hermes:10000 /root/hermes-agent-legacy-docker/data/drafts/salida.{html,png}
```

Escribe el HTML en `/opt/data/drafts/` (= `/root/hermes-agent-legacy-docker/data/drafts/` en el host): el mismo archivo se ve desde los dos lados, y el PNG queda listo para `MEDIA:`.

### Altura exacta: probe magenta (verificado 19-oct-2026)

No adivines la altura vertical del `--window-size`: cualquier texto que crezca deja el pie cortado o una banda vacía. Renderiza una **sonda** con fondo magenta y ventana alta, mide la última fila NO magenta y re-renderiza el archivo real a esa altura:

```bash
sed 's/html,body { width:1400px; background:#080B10; }/html { width:1400px; background:#FF00FF; } body { width:1400px; background:#080B10; }/' salida.html > _probe.html
# screenshot de _probe.html a --window-size=1400,2400 y medir:
```

```python
from PIL import Image
im = Image.open('_probe.png').convert('RGB'); px = im.load(); w, h = im.size
last = 0
for y in range(h-1, -1, -1):
    r, g, b = px[5, y]
    if not (r > 240 and g < 20 and b > 240):
        last = y; break
print('css height', last / 2)   # dividir entre force-device-scale-factor
```

Re-renderiza el HTML real (sin magenta) con `--window-size=1400,<altura>` redondeada hacia arriba. Vuelve a medir tras CUALQUIER patch del HTML: un texto que pasa a 2 líneas no se nota en el diff pero sí en la altura.

## Fallback sin Chrome: render PIL puro (verificado 20-oct-2026)

Cuando NO hay Chrome for Testing (entorno sin ese binario y solo el chromium snap inservible), la misma infografía sale completa con PIL, sin HTML ni probe de altura (el canvas es de tamaño fijo, nunca crece):

1. **Fuente:** localizar TTF con `fc-match -f '%{file}\n' 'DejaVu Sans:style=Bold'` (DejaVu existe en casi todo Debian/Ubuntu; sin emojis, igual que en HTML).
2. **Helpers:** `d.rounded_rectangle(..., radius=..., fill=..., outline=...)` para tarjetas/píldoras; `d.textlength(texto, font=f)` para un wrap manual palabra por palabra (párrafos con retorno de línea propio); `d.line` para el raíl vertical del flujo.
3. **Layout:** posiciones Y calculadas a mano (paso fijo por tarjeta, ej. 184 px) y canvas de altura fija — no hay reflow, así que el pie no se corta NUNCA si las Y suman bien.
4. **Verificación idéntica:** guardar también una copia reducida (~700 px) para `vision_analyze` y validar texto pequeño, solapes y pie contra el script, no contra el recorte.

Si Chrome for Testing está disponible, preferir la ruta HTML (reflow automático y tipografía mejor); usar PIL solo como fallback verificado.

## Pitfalls verificados

1. **Sin emojis si no hay fuente de color**: `fc-list | grep -i emoji` vacio => salen cuadros. Usa numeros y formas CSS.
2. **Verifica SIEMPRE con vision antes de enviar**: la imagen completa (¿falta algo? ¿texto encimado?) y una **region del pie**. En la primera version la frase del pie se partio en dos lineas: se arregla con `white-space:nowrap` + acortando el texto, y el corte NO se ve en el HTML, solo en el PNG.
3. El **chromium del sistema puede ser un snap inservible headless**: usa Chrome for Testing.
4. Entrega **imagen + resumen en palabras**: el Admin pidio las dos cosas ("en palabras y graficamente"). El texto del chat sigue el mismo orden que los pasos de la imagen.
5. **Higiene**: chown a hermes y no dejar el HTML/PNG como root (rompe el reclamo de cero archivos ajenos).
6. **`vision_analyze` puede responder 408 (timeout) con imágenes grandes o de alta resolución**: no reintentar idéntico; reducir con PIL a ~700–800 px de ancho, JPEG q75–80, y reintentar. Para revisar detalle usa recortes por sección: el texto pequeño (sellos, pines del calendario) es ilegible a tamaño miniatura y el modelo de visión lo mal-lee en silencio (confundió "4 NOV" por "1 nov"); confirma fechas y cifras pequeñas contra el HTML, no contra el recorte.
7. **Paleta no es sagrada**: variante oscura validada con el Admin (casinos, oct-2026) — fondo `#080B10`, acentos dorados, tarjetas crema. Si la marca del cliente es oscura, usa la variante oscura en vez de forzar la paleta clara de arriba.
8. **Verificación final en 2 pasadas**: (a) imagen completa reducida para composición/solapes, (b) recortes por sección para detalle. Un "OK" del modelo sobre el thumbnail NO valida el texto pequeño.
