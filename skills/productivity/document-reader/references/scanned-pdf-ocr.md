# Scanned PDF Detection & OCR — Reference

## The Problem

`pdfplumber` and `PyPDF2` extract text from PDFs by reading the text layer embedded in the file. When a PDF is **scanned** (i.e., pages are images without a text layer), these libraries return empty strings.

### Symptoms
- `parse_document.py` returns "No content extracted" for scanned PDFs
- `page.extract_text()` returns `""`
- User shares a PDF that visually contains text but parser returns nothing

### Root Cause
The original `parse_document.py` only attempted OCR on image files (`.png`, `.jpg`, etc.), NOT on scanned PDFs. There was no fallback path.

## The Fix (v2.0.0)

### Architecture
```
PDF → pdfplumber → extract_text()
         │
         ├─→ text found → return as normal
         │
         └─→ text empty → auto-detect scanned → PyMuPDF page render → PIL Image → OpenCV preprocess → Tesseract OCR (spa+eng)
```

### Key Functions
1. **`parse_pdf()`** — Tries pdfplumber first, checks if ALL pages have zero text, if so calls `parse_pdf_with_ocr()`
2. **`parse_pdf_with_ocr()`** — Uses PyMuPDF to render each page as a PIL Image, then calls `ocr_page_with_preprocessing()`
3. **`ocr_page_with_preprocessing()`** — Applies `_preprocess_image()` then calls `pytesseract.image_to_string()` with `lang="spa+eng"`
4. **`_preprocess_image()`** — OpenCV pipeline: grayscale → denoise → adaptive threshold → deskew
5. **`parse_image_ocr()`** — Standalone OCR for image files (.png, .jpg, etc.) with same pipeline

### Data Flow
```
pdfplumber.extract_text() == ""
    → parse_pdf_with_ocr()
        → fitz.open(filepath) → page.get_text() == "" → render_as_pil()
            → _preprocess_image() (OpenCV)
                → pytesseract.image_to_string(img, lang="spa+eng")
                    → {"type": "pdf_scanned", "pages": [{"page": 1, "text": "..."}]}
```

## Preprocessing Pipeline

The OpenCV preprocessing significantly improves OCR accuracy:

1. **Grayscale** — `cv2.cvtColor(..., cv2.COLOR_RGB2GRAY)`
2. **Denoise** — `cv2.fastNlMeansDenoising(arr, h=10)`
3. **Adaptive Threshold** — `cv2.adaptiveThreshold(..., cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)`
4. **Deskew** — Estimate rotation angle from content centroid, rotate if > 0.5°

## Language Support

Uses `spa+eng` (Spanish + English) for bilingual documents. Requires:
```bash
apt-get install tesseract-ocr-spa
```

Verify with: `tesseract --list-langs | grep spa`

## Verification

Run: `bash SKILL_DIR/scripts/verify_ocr.sh`

Checks:
- Python packages: pytesseract, opencv-python, PyMuPDF, Pillow
- System: tesseract binary, spa language pack
- OCR on test image
- OCR on test scanned PDF
