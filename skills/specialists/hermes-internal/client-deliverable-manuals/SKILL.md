---
name: client-deliverable-manuals
description: >-
  Use when writing client operational manuals or guides. Use when creating client operational manuals or guides. hermes: tags: [deliverables, manuals, docx, pdf, neuralcrew, client-docs]
tags: [manuales, entregables, docx, pdf, clientes, neuralcrew, casino, operativo]
version: 1.0.0
author: hermes
license: MIT
metadata:---

# Manuales y entregables operativos para clientes (NeuralCrew Labs)

Clase de trabajo: generar manuales operativos / guías de procedimiento para clientes de la agencia
(ej. manual de ejecutivas de venta para campaña de bingo en casinos). Validado 25/08/2026 con el
Bingo Millonario × Amor y Amistad (Golden Game + Lucky Brothers).

## Flujo obligatorio (el Admin lo pidió explícitamente: "preguntame y refinemos antes de hacer los docs finales")

1. **Leer TODOS los documentos fuente** (T&C, PDFs, briefs) antes de producir. No asumir la mecánica.
2. **Preguntar antes de finalizar** — batch de preguntas (usa la herramienta clarify con varias preguntas en un solo llamado): alcance (una o varias empresas), datos pendientes, rol que ejecuta el procedimiento, canal de redes, formato de entrega.
3. **Mostrar borrador de la parte delicada** para revisión del Admin (ej. instructivo de redes sociales) antes de generar los finales.
4. **Solo entonces generar** DOCX + PDF.
5. **Verificar contenido** (ver abajo) y entregar ambos con `MEDIA:` — nunca solo la ruta interna.

## Correcciones del Admin que aplican a TODO manual de cliente (no volver a repetirlas)

- **Tareas internas FUERA del entregable**: los pasos que ejecutamos nosotros (crear hojas, diseñar fichas, gestionar cuentas) NO van en el documento del cliente. El entregable solo describe el *procedimiento de uso*. ("las tareas son para nosotros, no las pongas en el doc que es entregable").
- **Terminología del cliente**: usar el rol aprobado por el Admin (ej. "ejecutivas de venta", NUNCA "cajeras").
- **Un entregable POR EMPRESA**: si la campaña corre en dos razones sociales (Golden + Lucky), generar documentos separados, sin menciones cruzadas ("que no se mencione golden en el de lucky y viceversa"). Parametrizar UN script con lista de configs por empresa (razón social, NIT, contacto, doc nº) e iterar.
- **Secciones que el Admin no pide, no van**: no inflar con datos generales de la promoción ni listados de sedes si no se pidieron.
- **Reglas del negocio**: escribir la regla exacta como la confirmó el Admin (ej. "mínimo 1 bingo por jornada; 2 si el tiempo alcanza"), no la versión genérica del T&C.

## Generación técnica (dual-track DOCX + PDF)

- **DOCX** con python-docx, membrete NeuralCrew: ver skill `neuralcrew-letterhead` (user-owned; leer su script `scripts/gen_manual_asistentes.py` como referencia de estructura: helpers `t()/heading()/body()/bullet()/numbered()`, header con logo + wordmark, líneas doradas con borde de párrafo, no tablas sombreadas).
- **PDF** con fpdf2 (venv uv: `uv venv --clear /tmp/pdfenv && uv pip install --python /tmp/pdfenv/bin/python fpdf2`), fuentes DejaVuSans. NO depende de LibreOffice (puede no estar instalado en el VPS).
- Un solo script por formato que itera sobre `CONFIGS = [{empresa, nit, contacto, doc_n, out_name}]` → N archivos.

## Verificación (obligatoria antes de entregar)

- **No hacer grep sobre .docx/.pdf** (binarios comprimidos — da 0 matches aunque el texto exista). Extraer texto con `read_file` (convierte ambos) y verificar ahí.
- Chequear **referencias cruzadas entre empresas**: buscar el nombre de la otra empresa en el texto extraído → debe dar 0.
- Chequear palabras eliminadas/cambiadas (ej. "Tarea:" → 0, "cajera" → 0).
- PDF: confirmar páginas y contenido por extracción de texto; DOCX: confirmar secciones numeradas y anexos.

## Pitfalls de scripting

- `heading("Título", )` con coma sobrante → SyntaxError.
- `for i, b in enumerate([...]` sin `], start=1):` al cerrar la lista → SyntaxError (paréntesis nunca cerrado).
- fpdf2: `DejaVuSans-Oblique.ttf` puede no existir en el VPS → registrar la variante itálica apuntando a la fuente regular (`pdf.add_font("sans", "I", FONT)`), no fallar por eso.
- Acentos/ñ: siempre DejaVuSans ttf, no Helvetica.
- Verificar tamaño > 0 y que el archivo exista antes de decir "listo".

## Entrega

- DOCX editable (para que el Admin complete campos pendientes) + PDF imprimible, ambos con `MEDIA:/ruta`.
- Avisar qué campos quedaron "por confirmar" (direcciones, contactos) y que se completan en el DOCX editable.
