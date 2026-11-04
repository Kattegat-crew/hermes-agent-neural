---
name: pdf-deliverables
description: "Use when user wants a PDF to deliver as file."
tags: [pdf, fpdf2, documentos, media, entregables]
version: 1.0.0
metadata:
  hermes:
    tags: [pdf, deliverables, fpdf2, file-generation, user-delivery]
---

# PDF Deliverables (fpdf2)

Generar archivos PDF listos para entregar al usuario (prompt cards, infografías de texto, reportes, listados) y adjuntarlos en el chat.

## When to Use

- "Dámelo en archivo pdf", "genera un PDF", "PDF listo para pegar"
- Prompt cards de generación de imágenes (p. ej. flujo baoyu-infographic → usuario pide el prompt en PDF)
- Cualquier contenido que el usuario quiera recibir como archivo, no como texto en el chat

## Delivery preference (validada por el usuario)

- **El archivo PDF se adjunta en la respuesta con `MEDIA:/abs/path/file.pdf`** — nunca responder solo con la ruta interna ("lo guardé en /opt/...") ni con markdown.
- Markdown / rutas internas = repositorio técnico. El PDF es la entrega al humano.
- Espejo de la preferencia DOCX ya documentada (skill `productivity/docx`): DOCX con python-docx, PDF con fpdf2. Preferencias confirmadas 16/08/2026 (DOCX) y 22/08/2026 (PDF: el usuario reclamó "¿por qué lo guardaste ahí? dámelo en archivo pdf").

## Pasos

1. Crear venv con uv (entornos sin pip / PEP 668):
   ```bash
   uv venv --clear /tmp/pdfenv && uv pip install --python /tmp/pdfenv/bin/python fpdf2
   ```
   (fpdf2 instala fonttools + pillow automáticamente; usar `--clear` porque uv falla si el venv ya existe)

2. Escribir script limpio con write_file (ver `templates/pdf_delivery.py` para punto de partida):
   - `FPDF(format="A4")`, `set_auto_page_break(auto=True, margin=15)`, `set_margins(18,18,18)`
   - Registrar fuentes DejaVu (acentos y ñ en español sin problemas):
     ```python
     pdf.add_font("sans", "", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
     pdf.add_font("sans", "B", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
     ```
   - Texto largo: `multi_cell(0, 5.5, text)`; encabezados: `set_fill_color(...)` + `cell(0, 10, text, fill=True, ln=1)`; imagen: `pdf.image(path, x=40, y=34, w=130)` en su propia página (h queda None para mantener aspect ratio)
3. Ejecutar con el python del venv: `/tmp/pdfenv/bin/python script.py`
4. **Verificar**: `ls -la out.pdf` — tamaño > 0 y el archivo existe, antes de decir "listo".
5. Adjuntar en la respuesta final: `MEDIA:/opt/data/.../archivo.pdf` (Discord/Telegram lo envían como adjunto).

## Pitfalls

- **Helpers definidos antes de llamar**: función renombrada (header_band vs header) y constantes (DARK no definido) provocaron NameError. Definir todo ANTES del primer uso.
- **No enmascarar errores**: ejecutar `python s.py; ls -la out.pdf`, nunca `python s.py | tail` ni `cmd || echo` — el pipe enmascara exit codes reales (fpdf2 reportó éxito con salida vacía por el pipe).
- **`uv venv` sin `--clear`** falla con "A virtual environment already exists".
- **DeprecationWarning "uni"** de add_font (fpdf2 ≥2.5.1): inofensivo, ignorar o no pasar uni=True.
- **Helvetica por defecto no soporta bien acentos ni emojis**: usar siempre DejaVuSans ttf.
- Verificar SIEMPRE el output (tamaño + páginas) antes de entregar — la primera versión del script suele llevar bugs.

## Alternativas

- Entregar en DOCX: skill `productivity/docx` (python-docx).
- Convertir HTML ya renderizado a PDF (infográficos complejos): `weasyprint`/`wkhtmltopdf` si están instalados; si no, fpdf2 con imagen incrustada (vista previa PNG en la última página).