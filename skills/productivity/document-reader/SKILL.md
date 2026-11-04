---
name: document-reader
description: >-
  Use when parsing any document file to extract its text. Universal document reader that parses .docx, .xlsx, .pdf, .pptx, .odt, .ods, .odp, .rtf, .txt, .csv, .md, .html, .epub, .eml, and image files (via OCR). Use when the user shares a document file, asks to read/extract content from a file, wants to convert between document formats, or needs to summarize or extract tables from any document type. hermes: tags: [Documents, PDF, Word, Excel, OCR, Parsing, Reading] homepage: https://github.com/pymupdf commands: [python3] python_packages: system_packages:
tags: [documentos, documents, pdf, word, excel, ocr, parsing]
version: 2.0.0
author: hermes
license: MIT
metadata:
prerequisites:
    - python-docx
    - openpyxl
    - pandas
    - PyPDF2
    - pdfplumber
    - PyMuPDF
    - mammoth
    - Pillow
    - pytesseract
    - opencv-python
    - tesseract-ocr (with lang=spa for Spanish support)
---

# Document Reader

Universal document parser supporting Word, Excel, PDF, PowerPoint, eBooks, CSV,
image-based documents (with OCR), and **scanned PDFs** (auto-detected).

## Prerequisites

All Python packages are pre-installed:
- `python-docx` — .docx parsing
- `openpyxl` — .xlsx/.ods parsing
- `pandas` — CSV/table processing
- `PyPDF2` — PDF fallback parser
- `pdfplumber` — PDF primary parser (better table extraction)
- `PyMuPDF` — PDF page rendering for OCR (scanned PDFs)
- `mammoth` — .rtf conversion
- `Pillow` — image processing for OCR
- `pytesseract` — OCR engine wrapper
- `opencv-python` — image pre-processing for better OCR accuracy
- `tesseract-ocr` with `spa` language pack — OCR engine (Spanish support)

## Key Features

- **Auto-detects scanned PDFs**: When all pages return no text, automatically falls back to OCR
- **OpenCV pre-processing**: Grayscale, denoising, adaptive thresholding, and deskew before OCR
- **Spanish language support**: OCR uses `spa+eng` language pack for bilingual documents
- **Multiple output formats**: text, json, tables, summary, metadata, pages

## Helper Script

The script lives at `SKILL_DIR/scripts/parse_document.py`.

```bash
# Basic text extraction
python3 SKILL_DIR/scripts/parse_document.py /path/to/file.docx

# JSON output (structured, machine-readable)
python3 SKILL_DIR/scripts/parse_document.py /path/to/file.xlsx --format json

# Extract tables as CSV
python3 SKILL_DIR/scripts/parse_document.py /path/to/file.xlsx --format tables

# PDF pages with page numbers
python3 SKILL_DIR/scripts/parse_document.pdf --format pages

# Summary (key topics, stats)
python3 SKILL_DIR/scripts/parse_document.py /path/to/file.pdf --format summary

# Metadata only
python3 SKILL_DIR/scripts/parse_document.py /path/to/file.pptx --format metadata

# Limit PDF pages
python3 SKILL_DIR/scripts/parse_document.py /path/to/file.pdf --max-pages 10

# Specific Excel sheet
python3 SKILL_DIR/scripts/parse_document.py /path/to/file.xlsx --sheet "Q4 Data"

# Verbose/debug mode
python3 SKILL_DIR/scripts/parse_document.py /path/to/file.odt --verbose

# OCR on scanned images
python3 SKILL_DIR/scripts/parse_document.py /path/to/scan.png

# Scanned PDFs are auto-detected and OCR'd automatically
python3 SKILL_DIR/scripts/parse_document.py /path/to/scan.pdf
```

## Supported Formats

| Format | Extensions | Parser | Notes |
|--------|-----------|--------|-------|
| Word | `.docx` | python-docx | Full: paragraphs, tables, metadata |
| Word (legacy) | `.doc` | antiword | Requires `apt-get install antiword` |
| Word | `.rtf` | mammoth | Converts to HTML then strips tags |
| Word | `.odt` | ZIP+XML | OpenDocument text format |
| Excel | `.xlsx` | openpyxl | Full: all sheets, cells, formulas |
| Excel | `.xls` | openpyxl | Limited (read-only) |
| Excel | `.ods` | openpyxl | OpenDocument spreadsheet |
| CSV | `.csv` | Python csv | Auto-detects delimiter |
| PDF | `.pdf` | pdfplumber | Best table extraction |
| PDF | `.pdf` | PyPDF2 | Fallback if pdfplumber fails |
| PDF (scanned) | `.pdf` | PyMuPDF+OCR | Auto-detected, uses OpenCV pre-processing |
| PowerPoint | `.pptx` | python-pptx | Slides with text content |
| PowerPoint | `.odp` | ZIP+XML | Basic OpenDocument presentation |
| eBook | `.epub` | ZIP+HTML | TOC + first 5 chapters |
| Text | `.txt`, `.md` | Built-in | Direct file read |
| Web | `.html` | Built-in | Direct file read |
| Email | `.eml` | Built-in | Raw email text |
| Images | `.png`, `.jpg`, `.gif`, `.tiff`, `.bmp`, `.webp` | Pillow+pytesseract | OCR with OpenCV pre-processing + Spanish support |

## Output Formats

| Format | Description |
|--------|-------------|
| `text` | Human-readable with separators and formatting |
| `json` | Structured JSON with metadata, paragraphs, tables |
| `summary` | Document stats, key topics, preview |
| `tables` | CSV output of all tabular data |
| `metadata` | File metadata only (JSON) |
| `pages` | PDF pages numbered and separated |

## Workflow

1. **Identify** the file type from the extension.
2. **Run** the parser script with the appropriate `--format` flag.
3. **Validate** the output is non-empty and readable.
4. **Process** further: summarize, extract specific sections, convert to another format.

### Typical Use Cases

**User shares a file path:**
```bash
python3 SKILL_DIR/scripts/parse_document.py ~/Documents/report.pdf
```

**User asks to extract tables:**
```bash
python3 SKILL_DIR/scripts/parse_document.py ~/Documents/data.xlsx --format tables
```

**User wants a summary:**
```bash
python3 SKILL_DIR/scripts/parse_document.py ~/Documents/article.pdf --format summary
```

**User wants structured data:**
```bash
python3 SKILL_DIR/scripts/parse_document.py ~/Documents/report.docx --format json
```

**Scanned PDF (auto-detected):**
```bash
python3 SKILL_DIR/scripts/parse_document.py ~/Documents/scan.pdf
# Script auto-detects no text and runs OCR with spa+eng
```

## Error Handling

- **File not found**: Check the path and try again.
- **Unsupported format**: Try converting to a supported format first (e.g., `.doc` → `.docx` via LibreOffice).
- **PDF with no text**: The file is likely image-based (scanned). OCR is now automatic.
- **Encrypted/password-protected**: Tell the user the file requires a password.
- **Library missing**: Install the required package (`pip install <package>`).
- **Large files**: Use `--max-pages` for PDFs or `--sheet` for Excel to limit extraction.

## Tips

- For **large PDFs**, use `--max-pages` to avoid timeout.
- For **Excel files with many sheets**, use `--sheet "SheetName"` to target a specific one.
- For **CSV files**, the script auto-detects the delimiter (comma, semicolon, tab, etc.).
- For **.docx files**, both paragraphs and tables are extracted separately.
- For **PowerPoint**, each slide's text content is extracted with shape type info.
- For **eBooks**, the table of contents is extracted first, then the first 5 chapters.
- Use `--format json` when you need to programmatically process the output.
- Use `--format summary` for a quick overview without reading the full content.
- For **scanned documents** (images or PDFs), OCR uses OpenCV pre-processing + Tesseract with Spanish (`spa`) and English (`eng`) language support.
- Scanned PDFs are **auto-detected**: if all pages return empty text, the script automatically switches to OCR mode.
- For OCR to work, ensure `tesseract-ocr` is installed with Spanish language pack: `apt-get install tesseract-ocr-spa`

## Integration with local-vision-toolkit

For image files (PNG, JPG, etc.), use `document-reader` for basic OCR or `local-vision-toolkit` for deep visual analysis (chart type, diagram structure, infographic layout, color analysis).

**When to use which:**
- `document-reader` → Quick OCR on any image file (simple, fast)
- `local-vision-toolkit` → Deep analysis: chart types, flowcharts, infographics, structural layout, dominant colors

**Workflow — deep image analysis via document-reader:**
```bash
# Convert image to PDF (for document-reader PDF pipeline)
python3 -c "from PIL import Image; Image.open('scan.png').save('scan.pdf', 'PDF')"
# Then use document-reader
python3 SKILL_DIR/scripts/parse_document.py scan.pdf
```

**Workflow — complement with local-vision-toolkit:**
```bash
# Quick OCR via document-reader
python3 SKILL_DIR/scripts/parse_document.py screenshot.png

# Deep analysis via local-vision-toolkit
python3 SKILL_DIR/../local-vision-toolkit/scripts/vision_tool.py screenshot.png --action chart
```

## Support Files

| File | Purpose |
|------|---------|
| `scripts/verify_ocr.sh` | Quick verification: checks all deps, tesseract binary, spa lang, runs test OCR |
| `references/scanned-pdf-ocr.md` | Deep reference: scanned PDF detection architecture, preprocessing pipeline, language support |

## Pitfalls

- **PDFs returning "No content extracted"**: This almost always means a scanned PDF (no text layer). The script auto-detects this, but if it doesn't, verify that pdfplumber/PyPDF2 are installed and that `tesseract-ocr-spa` is present.
- **Patching OCR functions requires full old_string**: The `parse_image_ocr` function was accidentally deleted during a patch because the `old_string` didn't match the current code. Always `skill_view` the exact section before patching multi-line functions.
- **OpenCV is optional but recommended**: `_preprocess_image()` returns the image unchanged if `cv2` is not installed. The OCR still works but with lower accuracy.
- **PyMuPDF is required for scanned PDFs**: Without `PyMuPDF` (fitz), the scanned PDF detection path cannot render pages as images. Install with `pip install PyMuPDF`.
- **Tesseract language packs are system-level**: `pip install pytesseract` only installs the Python wrapper. Tesseract itself and language data (`tesseract-ocr-spa`) must be installed via system package manager.
