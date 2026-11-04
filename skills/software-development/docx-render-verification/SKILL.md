---
name: docx-render-verification
description: "Use when QA-ing or editing an existing .docx deliverable."
version: 1.0.1
author: Ragnar
license: MIT
platforms: [linux]
tags: [docx, docker, libreoffice, qa, render, vision]
metadata:
  hermes:
    tags: [docx, docker, libreoffice, qa, render]
    category: devops
---

# Verificación visual de DOCX sin LibreOffice local

## When to Use

- Un entregable DOCX (membrete, informe, contrato) requiere el QA visual del workflow y `libreoffice`/`soffice`/`pdftoppm` no están en el contenedor ni se pueden instalar (agente sin root).
- Aplica a DOCX de clientes generados por otros skills (p. ej. neuralcrew-letterhead), cuyo paso de verificación asume LibreOffice local.
- NO aplica si el entorno ya tiene LibreOffice: usar el flujo directo del skill de membrete.
- **Edición quirúrgica de un DOCX ya aprobado** (tesis, planteamiento, informe): cuando hay que reescribir párrafos concretos sin perder estilos, numeración ni sangrías, y verificar cada cita antes de entregar. Ver `references/edicion-quirurgica-academica.md`.

Patrón para el paso "verificar SIEMPRE con libreoffice→pdftoppm→vision_analyze" cuando el contenedor Hermes **no trae** `libreoffice`/`soffice`/`pdftoppm` y el agente corre como uid no-root (no puede instalar paquetes). Probado 28/08/2026 generando el DOCX de estado de guiones Bingo.

## Receta (una sola llamada terminal)

Ejecutar LibreOffice en un contenedor efímero sobre la ruta canónica del host (host `/root/hermes-agent-legacy-docker/data/workspace` == contenedor `/opt/data/workspace`):

```bash
docker run --rm -v /root/hermes-agent-legacy-docker/data/workspace:/dst alpine:latest sh -c \
"apk add -q libreoffice poppler-utils >/dev/null 2>&1; \
 cd /dst && \
 soffice --headless --convert-to pdf MI-DOC.docx --outdir /tmp/out >/dev/null 2>&1 && \
 pdftoppm -png -r 150 /tmp/out/MI-DOC.pdf /tmp/out/pg && \
 cp /tmp/out/MI-DOC.pdf /dst/ && \
 cp /tmp/out/pg-1.png /dst/_preview_pg1.png && \
 echo COPIED"
```

Luego: `vision_analyze` sobre `_preview_pg1.png` y limpiar los previews antes de entregar.

## Lecciones

- **150 DPI mínimo** para el QA: a 80 DPI vision_analyze reporta texto "ilegible/pixelado" y falla el QA aunque el documento esté bien.
- **Glitch generalizado ≠ defecto del DOCX**: alpine sin fuentes Calibri hace fallback; si la estructura (membrete, líneas, tablas, saltos) está íntegra y el texto "pixelado" es uniforme, es el contenedor, no el archivo. Verificar layout, no tipografía exacta.
- `apk add libreoffice` tarda 1-3 min; pedir SIEMPRE `poppler-utils` en el mismo run.
- Montar la ruta del **host** (`/root/hermes-agent-legacy-docker/data/...`): los outputs del contenedor efímero quedan root-owned pero legibles para el agente.
- **chown de outputs del Docker efímero (03/09):** los archivos que el contenedor `docker run --rm` genera (default root) quedan **root-owned**. Si el flujo siguiente necesita moverse/leerse desde una sesión hermes (uid 10000), hacer `docker exec hermes-agent chown -R hermes:hermes <ruta>` (o `chmod`) ANTES de usarlos — lección directa con el `MEMORY.md` que quedó root:root tras correr comandos curator y bloqueó el write de memoria. No intentar chown como agente no-root.
- No intentar `apt-get install` desde el agente (no es root) ni `docker exec hermes-agent` (tampoco lo tiene).
- **QA de contenido, no solo de layout:** cuando `soffice` sí está disponible, `soffice --headless --convert-to pdf` + `pdftotext -layout` permite revisar texto (placeholders, citas colgantes, concordancia) además de la estructura; `scripts/docx_surgical.py check` lo corre en un paso.
- **Nunca inventar una referencia ni citar los COMENTARIOS de un insumo como si fueran el artículo:** en un RAE el bloque RESUMEN es textual con página, pero los COMENTARIOS son lectura del grupo. Si una cita del texto no tiene entrada en la lista de referencias, atribuir la afirmación a quien la sostiene en el insumo y dejarlo como pendiente en la planilla.

## Alternativa pandoc/core: MD→DOCX + QA en un solo contenedor

Cuando el entregable nace en Markdown, la imagen `pandoc/core` hace los DOS pasos (conversión y QA) sin tocar alpine:

```bash
# 1) MD → DOCX
docker run --rm -v /root/hermes-agent-legacy-docker/data/workspace:/data pandoc/core:latest \
  /data/DOC.md -o /data/DOC.docx --standalone --metadata title="Título"
# 2) QA: mismo contenedor con LibreOffice instalado en el fly
docker run --rm -v /root/hermes-agent-legacy-docker/data/workspace:/data --entrypoint sh pandoc/core:latest -c \
"apk add -q libreoffice poppler-utils >/dev/null 2>&1; cd /data && \
 soffice --headless --convert-to pdf DOC.docx >/dev/null 2>&1 && \
 pdftoppm -png -r 90 -f 1 -l 1 DOC.pdf _p && echo RENDER_OK"
```

- El DOCX resultante de pandoc sale root-owned pero legible; `--standalone` es necesario o el DOCX queda sin estilos.
- **QA sin vision disponible:** si `vision_analyze` falla (p. ej. el modelo activo no soporta imágenes: "This model does not support image"), verificar la integridad del texto con `pdftotext DOC.pdf -` (grep de typos/secciones) y `pdfinfo | grep Pages` para el conteo. El QA de LAYOUT (membrete, tablas, líneas finas) sigue necesitando PNG + vision; el de TEXTO no.
