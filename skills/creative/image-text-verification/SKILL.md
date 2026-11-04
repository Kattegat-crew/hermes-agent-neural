---
name: image-text-verification
description: "Use when reading text from an image before acting on it."
tags: [vision, ocr, captura, verificacion, qa, imagen, alucinacion]
version: 1.0.0
author: curator-ragnar
category: vision
metadata:
  hermes:
    tags: [vision, ocr, captura, verificacion, qa]
    related_skills: [document-digitization-ocr, ocr-and-documents, local-vision-toolkit, ingest-pipeline]
---

# Verificar el texto leído de una imagen antes de usarlo

**Cuándo:** una imagen (captura de pantalla, TUI, dashboard, scan, foto) es la única fuente de un dato que vas a **reportar, guardar (wiki/brain/memoria) o usar para decidir**. Aplica igual si la imagen la manda el usuario en el chat o si llega dentro de un enlace de X/TikTok.

**Regla dura:** un **identificador leído de una imagen** —nombre de modelo, ruta, versión, ID, cifra, correo— NO se reporta con una sola pasada de visión. Es exactamente donde el modelo rellena con algo plausible y suena igual de seguro que lo correcto. Una pasada = borrador; dos pasadas concordantes = dato.

## Protocolo (2 pasadas obligatorias)

**Pasada 1 — estructura completa.** Una sola llamada para entender qué hay: `vision_analyze` con la pregunta explícita de transcribir todo el texto respetando indentación y **sin inventar**.

**Pasada 2 — recorte ampliado de la zona crítica.** Se recorta la columna/sección donde vive el dato, se amplía ≥1,5× y se vuelve a preguntar **solo por esa zona**, con salida `[ilegible]` permitida.

```python
import urllib.request
from PIL import Image

urllib.request.urlretrieve(img_url, "/tmp/cap.jpg")   # si ya es un path local, se salta
im = Image.open("/tmp/cap.jpg"); w, h = im.size
im.crop((int(w*0.45), 0, w, h)).resize((int(w*0.55*1.6), int(h*1.6))).save("/tmp/cap-zoom.png")
# vision_analyze("/tmp/cap-zoom.png", "Lee SOLO la columna derecha. Una cadena por línea, tal cual. Si algo no se distingue, escribe [ilegible].")
```

Script listo para correr: `scripts/zoom_crop.py <imagen-o-url> [--left 0.45] [--zoom 1.6] [--out /tmp/zoom.png]`.

## Contrato de salida

- **`[ilegible]` es una respuesta válida y hay que ofrecerla explícitamente.** Sin esa salida el modelo inventa; con ella se declara la duda y sigue.
- Al entregable va **solo lo que ambas pasadas confirman**. Si divergen, se reporta la divergencia, no la versión que suena mejor.
- Distingue en la respuesta lo leído de lo inferido. «El slot Review apunta a X» ≠ «probablemente apunta a X».
- Si el usuario depende del dato para decidir o gastar, dilo antes de que lo use: una transcripción sin verificar no es evidencia.

## Contraste con la fuente viva

Si lo transcrito corresponde a algo que **existe en tu entorno**, verifícalo contra el objeto real antes de afirmarlo: la captura puede ser vieja, de otra máquina o de otro perfil.

- Configuración → `grep`/`read_file` del archivo real (`config.yaml`, `.env`, unit de systemd).
- Comandos/versiones → ejecutar el comando y comparar.
- Capturas de terceros (tuiteros, proveedores) → no hay fuente viva: queda como «según la captura» y la acción propuesta se marca **pendiente**.

Cuando la propuesta derivada toca configuración o gasto, se presenta como propuesta con su OK pendiente (Estado 3/4), nunca como cambio ya hecho.

## QA visual de un artefacto propio (el render de un archivo que TÚ generaste)

Cuando la imagen es el **render de algo que existe en disco** (DOCX, PDF, dashboard exportado), la fuente de verdad es el archivo, no la lectura del modelo: la visión sirve para **layout**, su transcripción es una **hipótesis**.

- Pedir las dos cosas en la misma pasada: (a) defectos de maquetación —membrete, texto cortado, bloques partidos, títulos huérfanos, páginas casi vacías— y (b) la transcripción de lo visible.
- **Nunca corregir el archivo por una errata que reportó la visión.** Confirmarla primero en el original: extraer el texto (`python-docx` desde `terminal()`, `pdftotext`, `read_file`) y buscar la frase exacta. Caso verificado 14/09/2026: el modelo reportó «diez quince segundos» donde el archivo decía «diez a quince segundos», y leyó mal el correo del pie — dos «erratas», ninguna real. Lo que no falla en el archivo no se toca.
- Contrastar las afirmaciones del QA visual con el conteo real antes de entregar: nº de páginas del PDF, cuántos bloques/piezas debería haber, frases críticas (dirección, cifras, pie legal). Si el render muestra 3 páginas y esperabas 5, el problema es el archivo, no la lectura.
- Los hallazgos de diseño que la visión marca como «defecto» pueden ser decisiones del formato (wordmark en dos líneas, línea dorada del título). Comprobar contra la especificación del formato antes de «arreglarlos».
- Cuando el contenedor no tiene LibreOffice, el render se hace fuera y las páginas vuelven al contenedor: cadena exacta y caso completo en `references/caso-qa-render-docx-14sep2026.md`.

## Límites y ruteo vecino

- **Documentos largos o lotes** (PDF, scans, decenas de páginas): no es esta skill — `document-digitization-ocr` (ruteo: pymupdf / visión / Paperless en PROD) y `ocr-and-documents` (bundled).
- **Reconocimiento local sin modelo de visión** (tesseract/OpenCV, gráficas, diagramas): `local-vision-toolkit`.
- **La imagen llega dentro de un enlace social**: la extracción del enlace (media, artículo) vive en `ingest-pipeline` / `twitter-telegram-ingestion` (hoy **user-owned**); aquí solo se resuelve la lectura del texto de la imagen.
- Caso trabajado (captura 1058×525 con 15 filas de texto fino, dos pasadas concordantes, contraste con el `config.yaml` real): `references/caso-captura-config-hermes.md`.

## Pitfalls

- **Reportar identificadores de una sola pasada.** Modelos, rutas y versiones son el punto exacto de alucinación; el nombre inventado es plausible y consistente entre llamadas del mismo modelo.
- **No recortar por parecer legible.** Una captura de ~1000 px con ~15 filas de texto fino no es legible para el modelo aunque lo parezca en la miniatura: el recorte no es opcional.
- **Ampliar sin recortar** (resize de la imagen entera): se pierde resolución efectiva por lado; recorta primero, amplía después.
- **Preguntar abierto en la pasada 2** («¿qué dice la imagen?») en vez de acotar la zona: vuelve a la lectura global y no verifica nada.
- **Guardar la transcripción en wiki/brain como si fuera fuente primaria** sin declarar que es lectura de imagen.
- **Pedir una tercera pasada en bucle.** Dos pasadas concordantes cierran; si no concuerdan, se declara `[ilegible]` y se pide al usuario una captura mejor.
- **Tratar la lectura de la visión como fuente primaria de un archivo que ya tienes.** En el QA de un entregable propio, el `.docx`/`.pdf` manda: la lectura de imagen se confirma contra el archivo o no se usa (ver sección de QA de artefacto propio).
- **Corregir contenido fantasma.** Aplicar un «arreglo» por una errata que solo existe en la lectura del modelo es peor que no revisar: introduce el error y borra el rastro de que el archivo estaba bien.
