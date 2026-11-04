---
name: neuralcrew-letterhead
description: "Use when generating NeuralCrew letterhead DOCX files."
tags: [docx, membrete, neuralcrew, marca, branding, plantillas]
version: 1.0.0
author: Ragnar
platforms: [linux]
---

# NeuralCrew Labs Letterhead

Genera plantillas DOCX profesionales con la identidad de marca oficial de NeuralCrew Labs. Reutilizar para TODOS los documentos de clientes (propuestas, informes, reportes, contratos, entregables).

## Identidad de marca (contexto)

- **Paleta**: Negro `#1A1A1A`, Dorado `#D4AF37`, Gris oscuro `#3A3A3A`, Gris medio `#707070`
- **Tipografía**: Calibri (cuerpo), bold para títulos
- **Logo**: icono circular rompecabezas (negro + dorado, red neuronal) — tiene fondo transparente. El wordmark se hace con tipografía editable: **NEURALCREW** en negro + **LABS** en dorado
- **Eslogan**: *"Inteligencia artificial aplicada a tu negocio"*
- **Contacto**: 3166910728 · captain@neuralcrewlabs.com · Bogotá

## Activos requeridos

- `/root/hermes-agent-legacy-docker/data/workspace/logo_icon.png` — icono circular recortado, fondo transparente (extraído de `logo neural.png`)

## Script principal

`/root/hermes-agent-legacy-docker/data/scripts/gen_letterhead_v5.py`

Genera `/root/hermes-agent-legacy-docker/data/workspace/NeuralCrew_Labs_Membrete_Oficial.docx` con:
- Línea dorada fina superior (border de párrafo, NO tabla sombreada)
- Header 2 columnas: icono izquierda + wordmark derecha
- Línea dorada fina bajo wordmark
- Metadata: CLIENTE / FECHA / ASUNTO / DOC. Nº
- Título centrado con línea dorada fina debajo
- Secciones con marcador dorado "— "
- Footer con contacto

## Lecciones CRÍTICAS de diseño DOCX (evitar errores del v1-v3 "horribles")

1. **NO usar tablas de 1 celda sombreada como líneas** — se renderizan como barras doradas GORDAS y feas. Usar el **border inferior del párrafo** (`w:pBdr/w:bottom`) para líneas finas. `w:sz="8"` (~1pt) o `w:sz="16"` (~2pt).
2. **NUNCA** usar líneas decorativas con caracteres repetidos (`───`, `•••`) — se renderizan mal.
3. **Cabecera**: icono izquierda (celda 2.8cm) + wordmark derecha (13.4cm) en tabla invisible (borders none). El logo debe tener alpha transparente (evita efecto "pegatina"). **FORZAR layout fijo** (`w:tblLayout type="fixed"` + `autofit=False` + `w:tcW`) o Word/Drive re-distribuye las columnas por contenido y NEURALCREW se parte ("W" baja sola). El header tabla ancho total ≈16.2cm < ancho útil ~17.2cm.
4. **Wordmark**: NEURALCREW en un SOLO renglón (tamaño 22pt max en la celda de 13.4cm) con LABS debajo (16pt dorado). NO usar el logo vertical completo. El contacto (tel/email/Ubicación) NO va en la cabecera — solo en el footer (decisión del Admin 24/08).
5. Labels metadata (CLIENTE:, FECHA:) en gris medio `#707070`, valores en negro — evitar gris claro casi invisible.
6. **NO usar guion «— » dorado antes de los títulos de sección** (decisión del Admin 24/08: "no pega"). Los headings van en negro bold, sin símbolos. El dorado queda solo en la marca (icono, LABS, líneas finas, subtítulos de portada).
7. **Verificar SIEMPRE** con `libreoffice --convert-to pdf` + `pdftoppm -png` + `vision_analyze` antes de entregar.

## Workflow de entrega

1. Ejecutar el script
2. Convertir a PDF y revisar visualmente
3. Entregar DOCX en el chat con `MEDIA:.../NeuralCrew_Labs_Membrete_Oficial.docx`
4. Subir a Drive carpeta "Neural Crew Labs" (`1yjLxB4lEZe3n79QKK8vlnladPv4FtM7w`) si se pide

## Verificación visual

```bash
cd /root/hermes-agent-legacy-docker/data/workspace
libreoffice --headless --convert-to pdf NeuralCrew_Labs_Membrete_Oficial.docx --outdir preview
pdftoppm -png -r 90 preview/NeuralCrew_Labs_Membrete_Oficial.pdf preview/page
# abrir preview/page-1.png con vision_analyze para QA
```