#!/usr/bin/env python3
"""
Universal document reader — parses .docx, .xlsx, .pdf, .pptx, .odt, .ods, .odp,
.rtf, .txt, .csv, .md, .epub, .html, .eml, .msg (basic) and outputs structured text.

Usage:
    python3 parse_document.py <filepath> [--format <text|json|summary|tables|metadata|pages>]
    python3 parse_document.py --help

Supported formats:
    Word:  .docx, .doc (via antiword if available), .rtf, .odt
    Excel: .xlsx, .xls (via openpyxl basic), .ods, .csv
    PDF:   .pdf (via pdfplumber + PyPDF2 fallback)
    PowerPoint: .pptx, .odp
    Text:  .txt, .md, .html, .eml
    EBook: .epub

Options:
    --format    Output format (default: text)
                text   — raw readable text
                json   — structured JSON with metadata + content
                summary — AI-style concise summary (requires LLM or manual)
                tables — extract tabular data as CSV
                metadata — file metadata only
                pages  — PDF pages with page numbers
    --max-pages Max pages to extract (PDF only, default: 0 = all)
    --sheet     Sheet name or index to extract (Excel only)
    --verbose   Show progress/debug info
"""

import argparse
import csv
import io
import json
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path

# ── Libraries ──────────────────────────────────────────────────────────────
try:
    from docx import Document as DocxDocument
except ImportError:
    DocxDocument = None

try:
    import openpyxl
except ImportError:
    openpyxl = None

try:
    import pandas as pd
except ImportError:
    pd = None

try:
    import PyPDF2
except ImportError:
    PyPDF2 = None

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

try:
    import mammoth
except ImportError:
    mammoth = None

try:
    from PIL import Image
    import pytesseract
except ImportError:
    Image = None
    pytesseract = None

try:
    import cv2
except ImportError:
    cv2 = None

# ── Helpers ────────────────────────────────────────────────────────────────

def get_file_metadata(filepath):
    """Extract basic file metadata."""
    p = Path(filepath)
    stat = p.stat()
    return {
        "filename": p.name,
        "extension": p.suffix.lower(),
        "size_bytes": stat.st_size,
        "size_human": f"{stat.st_size / 1024:.1f} KB" if stat.st_size > 1024 else f"{stat.st_size} B",
        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        "created": datetime.fromtimestamp(stat.st_ctime).isoformat() if hasattr(stat, 'st_ctime') else None,
        "path": str(p.resolve()),
    }


def format_size(size_bytes):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


# ── PDF Parser ─────────────────────────────────────────────────────────────

def parse_pdf(filepath, max_pages=0, output_format="text", sheet=None, verbose=False):
    """Parse PDF using pdfplumber (primary) or PyPDF2 (fallback)."""
    results = {"type": "pdf", "pages": [], "tables": [], "total_pages": 0}
    
    # Try pdfplumber first (better table extraction)
    if pdfplumber and not verbose:
        try:
            with pdfplumber.open(filepath) as pdf:
                results["total_pages"] = len(pdf.pages)
                
                for i, page in enumerate(pdf.pages):
                    if max_pages > 0 and i >= max_pages:
                        break
                    
                    text = page.extract_text() or ""
                    results["pages"].append({
                        "page": i + 1,
                        "text": text
                    })
                    
                    # Extract tables
                    tables = page.extract_tables()
                    if tables:
                        for t_idx, table in enumerate(tables):
                            results["tables"].append({
                                "page": i + 1,
                                "table_index": t_idx,
                                "rows": table
                            })
            return results
        except Exception as e:
            if verbose:
                print(f"pdfplumber failed: {e}", file=sys.stderr)
    
    # Fallback to PyPDF2
    if PyPDF2:
        try:
            with open(filepath, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                results["total_pages"] = len(reader.pages)
                
                for i, page in enumerate(reader.pages):
                    if max_pages > 0 and i >= max_pages:
                        break
                    
                    text = page.extract_text() or ""
                    results["pages"].append({
                        "page": i + 1,
                        "text": text
                    })
            return results
        except Exception as e:
            if verbose:
                print(f"PyPDF2 failed: {e}", file=sys.stderr)
    
    raise RuntimeError("No PDF library available (need pdfplumber or PyPDF2)")


# ── Word Parser ────────────────────────────────────────────────────────────

def parse_docx(filepath, output_format="text", verbose=False):
    """Parse .docx files."""
    if not DocxDocument:
        raise RuntimeError("python-docx not installed")
    
    doc = DocxDocument(filepath)
    result = {
        "type": "docx",
        "paragraphs": [],
        "tables": [],
        "images": [],
        "metadata": {
            "title": doc.core_properties.title,
            "author": doc.core_properties.author,
            "subject": doc.core_properties.subject,
            "created": str(doc.core_properties.created) if doc.core_properties.created else None,
            "modified": str(doc.core_properties.modified) if doc.core_properties.modified else None,
        }
    }
    
    for para in doc.paragraphs:
        if para.text.strip():
            result["paragraphs"].append({
                "text": para.text,
                "style": para.style.name if para.style else None,
                "bold": para.runs and any(r.bold for r in para.runs) if para.runs else False,
            })
    
    for t_idx, table in enumerate(doc.tables):
        rows = []
        for row in table.rows:
            rows.append([cell.text for cell in row.cells])
        result["tables"].append({"index": t_idx, "rows": rows})
    
    return result


def parse_doc_legacy(filepath, verbose=False):
    """Parse legacy .doc files using antiword."""
    import subprocess
    try:
        result = subprocess.run(
            ["antiword", filepath],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            return {"type": "doc", "text": result.stdout}
        else:
            raise RuntimeError(f"antiword error: {result.stderr}")
    except FileNotFoundError:
        raise RuntimeError("antiword not installed. Install with: apt-get install antiword")


def parse_rtf(filepath, output_format="text", verbose=False):
    """Parse .rtf files by converting to HTML via mammoth, then to text."""
    if mammoth:
        with open(filepath, 'rb') as f:
            result = mammoth.convert_to_html(f)
            # Strip HTML tags for plain text
            import re
            text = re.sub(r'<[^>]+>', ' ', result.value)
            text = re.sub(r'\s+', ' ', text).strip()
            return {"type": "rtf", "text": text}
    raise RuntimeError("mammoth not installed for RTF parsing")


def parse_odt(filepath, verbose=False):
    """Parse .odt files by treating as ZIP and extracting content.xml."""
    import zipfile
    import xml.etree.ElementTree as ET
    
    try:
        with zipfile.ZipFile(filepath) as z:
            if 'content.xml' not in z.namelist():
                raise RuntimeError("content.xml not found in ODT")
            
            with z.open('content.xml') as f:
                tree = ET.parse(f)
                root = tree.getroot()
            
            # ODT uses namespace
            ns = {'text': 'urn:oasis:names:tc:opendocument:xmlns:text:1.0',
                  'draw': 'urn:oasis:names:tc:opendocument:xmlns:drawing:1.0'}
            
            paragraphs = []
            for p in root.findall('.//text:p', ns):
                text = p.text or ''
                for child in p:
                    if child.text:
                        text += child.text
                if text.strip():
                    paragraphs.append(text.strip())
            
            return {"type": "odt", "paragraphs": paragraphs}
    except Exception as e:
        raise RuntimeError(f"Failed to parse ODT: {e}")


# ── Excel Parser ───────────────────────────────────────────────────────────

def parse_xlsx(filepath, sheet=None, output_format="text", verbose=False):
    """Parse .xlsx files."""
    if not openpyxl:
        raise RuntimeError("openpyxl not installed")
    
    wb = openpyxl.load_workbook(filepath, data_only=True)
    result = {
        "type": "xlsx",
        "sheets": {},
        "metadata": {
            "title": wb.properties.title,
            "author": wb.properties.creator,
            "sheet_names": wb.sheetnames,
        }
    }
    
    sheets_to_parse = [sheet] if sheet and sheet in wb.sheetnames else wb.sheetnames
    
    for sheet_name in sheets_to_parse:
        ws = wb[sheet_name]
        rows = []
        for row in ws.iter_rows(values_only=True):
            # Clean row: remove trailing empty cells
            cleaned = list(row)
            while cleaned and cleaned[-1] is None:
                cleaned.pop()
            if any(c is not None for c in cleaned):
                rows.append(cleaned)
        
        result["sheets"][sheet_name] = {
            "rows": rows,
            "dimensions": f"{ws.max_row} rows × {ws.max_column} columns"
        }
    
    return result


def parse_csv(filepath, output_format="text", verbose=False):
    """Parse CSV files."""
    rows = []
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        # Try to detect dialect
        sample = f.read(8192)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample)
        except csv.Error:
            dialect = csv.excel
        
        reader = csv.reader(f, dialect)
        for row in reader:
            rows.append(row)
    
    return {
        "type": "csv",
        "rows": rows,
        "metadata": {
            "total_rows": len(rows),
            "columns": len(rows[0]) if rows else 0,
            "delimiter": dialect.delimiter,
        }
    }


def parse_ods(filepath, verbose=False):
    """Parse .ods files (similar to xlsx, uses openpyxl)."""
    return parse_xlsx(filepath)


# ── PowerPoint Parser ─────────────────────────────────────────────────────

def parse_pptx(filepath, verbose=False):
    """Parse .pptx files."""
    try:
        from pptx import Presentation
    except ImportError:
        raise RuntimeError("python-pptx not installed. Install with: pip install python-pptx")
    
    prs = Presentation(filepath)
    result = {
        "type": "pptx",
        "slides": [],
        "metadata": {
            "total_slides": len(prs.slides),
            "title": prs.core_properties.title,
            "author": prs.core_properties.author,
        }
    }
    
    for i, slide in enumerate(prs.slides):
        slide_text = []
        for shape in slide.shapes:
            if hasattr(shape, "text") and shape.text.strip():
                slide_text.append({
                    "shape_type": shape.shape_type,
                    "text": shape.text.strip(),
                })
        result["slides"].append({"slide": i + 1, "content": slide_text})
    
    return result


# ── EBook Parser ───────────────────────────────────────────────────────────

def parse_epub(filepath, verbose=False):
    """Parse .epub files (ZIP with HTML content)."""
    import zipfile
    import re
    
    try:
        with zipfile.ZipFile(filepath) as z:
            # Find NCX/NAV file for TOC
            toc = []
            html_files = []
            
            for name in z.namelist():
                if name.endswith('.html') or name.endswith('.xhtml'):
                    html_files.append(name)
                if 'toc.ncx' in name.lower():
                    with z.open(name) as f:
                        content = f.read().decode('utf-8', errors='replace')
                        # Simple TOC extraction
                        import re
                        toc_items = re.findall(r'<navPoint[^>]*>(.*?)</navPoint>', content, re.DOTALL)
                        for item in toc_items:
                            title = re.search(r'<text>(.*?)</text>', item)
                            if title:
                                toc.append(title.group(1).strip())
            
            # Extract first few HTML files for content
            content_parts = []
            for hf in html_files[:5]:  # Limit to avoid huge output
                with z.open(hf) as f:
                    html = f.read().decode('utf-8', errors='replace')
                    # Strip HTML tags
                    text = re.sub(r'<[^>]+>', '\n', html)
                    text = re.sub(r'\s+', ' ', text).strip()
                    if text:
                        content_parts.append(text)
            
            return {
                "type": "epub",
                "toc": toc,
                "content": "\n\n".join(content_parts),
                "metadata": {
                    "total_html_files": len(html_files),
                }
            }
    except Exception as e:
        raise RuntimeError(f"Failed to parse EPUB: {e}")


# ── Image OCR ──────────────────────────────────────────────────────────────

def _preprocess_image(img):
    """Pre-process image with OpenCV for better OCR accuracy.
    
    Applies grayscale, thresholding, denoising, and contrast enhancement.
    Falls back gracefully if cv2 is not available.
    """
    if not cv2:
        return img  # Return as-is if OpenCV not available
    
    # Convert PIL to OpenCV
    arr = cv2.cvtColor(numpy_cv2_array(img), cv2.COLOR_RGB2GRAY)
    
    # Denoise
    arr = cv2.fastNlMeansDenoising(arr, h=10)
    
    # Adaptive threshold for better text extraction
    arr = cv2.adaptiveThreshold(
        arr, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
    )
    
    # Convert back to PIL
    img = Image.fromarray(arr)
    
    # Deskew (rotation correction)
    coords = cv2.findNonZero(255 - arr)
    if coords is not None:
        coords = coords.squeeze()
        cx, cy = coords.mean(axis=0)
        img_w, img_h = img.size
        angle = 0
        # Check multiple points for angle estimation
        for x, y in coords[::max(1, len(coords)//20)]:
            angle += (y - cy) / max(1, (x - cx))
        angle = angle.mean() / max(1, len(coords)) * 180
        if abs(angle) > 0.5:
            # Rotate image to correct skew
            center = (img_w / 2, img_h / 2)
            M = cv2.getRotationMatrix2D(center, angle, 1.0)
            img_arr = cv2.warpAffine(numpy_cv2_array(img), M, (img_w, img_h))
            img = Image.fromarray(img_arr)
    
    return img


def numpy_cv2_array(pil_img):
    """Convert PIL Image to numpy array for OpenCV."""
    import numpy as np
    return np.array(pil_img)


def ocr_page_with_preprocessing(page_image, lang="spa+eng"):
    """OCR a single page image with OpenCV preprocessing and language support.
    
    Args:
        page_image: PIL Image of the page
        lang: Tesseract language code (default: spa+eng for Spanish + English)
    
    Returns:
        OCR text string, or empty string on failure
    """
    if not Image or not pytesseract:
        return ""
    
    try:
        # Pre-process with OpenCV for better accuracy
        preprocessed = _preprocess_image(page_image)
        
        # OCR with language support
        text = pytesseract.image_to_string(preprocessed, lang=lang)
        return text.strip()
    except Exception:
        # Fallback without preprocessing
        try:
            return pytesseract.image_to_string(page_image, lang=lang).strip()
        except Exception:
            return ""


def parse_image_ocr(filepath, verbose=False):
    """Try OCR on image-based documents (scanned PDFs, images).
    
    Uses OpenCV preprocessing + Tesseract with Spanish language support.
    """
    if not Image or not pytesseract:
        raise RuntimeError("Pillow and pytesseract are required for OCR.")
    
    try:
        img = Image.open(filepath).convert("RGB")
    except Exception as e:
        raise RuntimeError(f"Cannot open image file: {e}")
    
    # Pre-process with OpenCV
    if verbose:
        print("Pre-processing image with OpenCV...", file=sys.stderr)
    preprocessed = _preprocess_image(img)
    
    # OCR with language support (Spanish + English)
    lang = "spa+eng"
    text = ocr_page_with_preprocessing(preprocessed, lang=lang)
    
    if not text and verbose:
        print("Warning: OCR returned empty text.", file=sys.stderr)
    
    return {
        "type": "image_ocr",
        "text": text,
        "metadata": {
            "ocr_method": "opencv_preprocessed",
            "language": lang,
        }
    }


def is_scanned_pdf(filepath):
    """Check if a PDF is scanned (all pages have no extractable text).
    
    Uses PyMuPDF for page rendering since it handles images better than pdfplumber.
    Returns True if all pages appear to be scanned images.
    """
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(filepath)
        all_scanned = True
        has_content = False
        
        for page in doc:
            text = page.get_text().strip()
            if text:
                # Page has extractable text
                all_scanned = False
                break
            
            # Also check for images on the page - if page has images, it might be scanned
            images = page.get_images(full=True)
            if images:
                has_content = True
        
        doc.close()
        return all_scanned and has_content
        
    except ImportError:
        # PyMuPDF not available, use pdfplumber heuristic
        if pdfplumber:
            with pdfplumber.open(filepath) as pdf:
                all_empty = True
                has_pages = False
                for page in pdf.pages:
                    has_pages = True
                    text = page.extract_text()
                    if text and text.strip():
                        all_empty = False
                        break
                return all_empty and has_pages
        return False
    except Exception:
        return False


def parse_pdf_with_ocr(filepath, max_pages=0, output_format="text", sheet=None, verbose=False):
    """Parse PDF using OCR when text extraction fails (for scanned documents).
    
    Uses PyMuPDF to render pages as images, then applies OCR with OpenCV pre-processing.
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        raise RuntimeError("PyMuPDF required for scanned PDF OCR. Install with: pip install PyMuPDF")
    
    results = {"type": "pdf_scanned", "pages": [], "total_pages": 0}
    
    doc = fitz.open(filepath)
    results["total_pages"] = len(doc)
    
    lang = "spa+eng"  # Spanish + English for OCR
    
    for i, page in enumerate(doc):
        if max_pages > 0 and i >= max_pages:
            break
        
        # Render page to image at high DPI for better OCR
        mat = fitz.Matrix(3, 3)  # 3x zoom for high quality
        pix = page.get_pixmap(matrix=mat)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        
        # Apply OCR with preprocessing
        text = ocr_page_with_preprocessing(img, lang=lang)
        
        results["pages"].append({
            "page": i + 1,
            "text": text,
            "ocr_method": "opencv_preprocessed"
        })
        
        if verbose and text:
            print(f"  Page {i+1} OCR complete ({len(text)} chars)")
    
    doc.close()
    return results


def parse_pdf(filepath, max_pages=0, output_format="text", sheet=None, verbose=False):
    """Parse PDF using pdfplumber (primary) or PyPDF2 (fallback), with OCR for scanned docs.
    
    If all pages have no extractable text, falls back to OCR via PyMuPDF + Tesseract.
    """
    results = {"type": "pdf", "pages": [], "tables": [], "total_pages": 0}
    
    # Try pdfplumber first (better table extraction)
    if pdfplumber and not verbose:
        try:
            with pdfplumber.open(filepath) as pdf:
                results["total_pages"] = len(pdf.pages)
                
                for i, page in enumerate(pdf.pages):
                    if max_pages > 0 and i >= max_pages:
                        break
                    
                    text = page.extract_text() or ""
                    results["pages"].append({
                        "page": i + 1,
                        "text": text
                    })
                    
                    # Extract tables
                    tables = page.extract_tables()
                    if tables:
                        for t_idx, table in enumerate(tables):
                            results["tables"].append({
                                "page": i + 1,
                                "table_index": t_idx,
                                "rows": table
                            })
            
            # Check if all pages are empty (scanned PDF)
            if results["pages"]:
                total_text = sum(len(p.get("text", "")) for p in results["pages"])
                if total_text == 0:
                    if verbose:
                        print("Detected scanned PDF — switching to OCR", file=sys.stderr)
                    return parse_pdf_with_ocr(filepath, max_pages, output_format, sheet, verbose)
            
            return results
        except Exception as e:
            if verbose:
                print(f"pdfplumber failed: {e}", file=sys.stderr)
    
    # Fallback to PyPDF2
    if PyPDF2:
        try:
            with open(filepath, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                results["total_pages"] = len(reader.pages)
                
                for i, page in enumerate(reader.pages):
                    if max_pages > 0 and i >= max_pages:
                        break
                    
                    text = page.extract_text() or ""
                    results["pages"].append({
                        "page": i + 1,
                        "text": text
                    })
            
            # Check if all pages are empty (scanned PDF)
            if results["pages"]:
                total_text = sum(len(p.get("text", "")) for p in results["pages"])
                if total_text == 0:
                    if verbose:
                        print("Detected scanned PDF — switching to OCR", file=sys.stderr)
                    return parse_pdf_with_ocr(filepath, max_pages, output_format, sheet, verbose)
            
            return results
        except Exception as e:
            if verbose:
                print(f"PyPDF2 failed: {e}", file=sys.stderr)
    
    raise RuntimeError("No PDF library available (need pdfplumber or PyPDF2)")


# ── Main Dispatcher ────────────────────────────────────────────────────────

def parse_document(filepath, output_format="text", max_pages=0, sheet=None, verbose=False):
    """Main dispatcher — routes to the right parser based on file extension."""
    
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")
    
    ext = Path(filepath).suffix.lower()
    metadata = get_file_metadata(filepath)
    
    parsers = {
        '.docx': lambda: parse_docx(filepath, output_format, verbose),
        '.doc': lambda: parse_doc_legacy(filepath, verbose),
        '.xlsx': lambda: parse_xlsx(filepath, sheet, output_format, verbose),
        '.xls': lambda: parse_xlsx(filepath, sheet, output_format, verbose),  # limited support
        '.csv': lambda: parse_csv(filepath, output_format, verbose),
        '.pdf': lambda: parse_pdf(filepath, max_pages, output_format, sheet, verbose),
        '.pptx': lambda: parse_pptx(filepath, verbose),
        '.rtf': lambda: parse_rtf(filepath, output_format, verbose),
        '.odt': lambda: parse_odt(filepath, verbose),
        '.ods': lambda: parse_ods(filepath, verbose),
        '.odp': lambda: parse_odt(filepath, verbose),  # basic
        '.epub': lambda: parse_epub(filepath, verbose),
        '.md': lambda: {"type": "markdown", "text": Path(filepath).read_text(encoding='utf-8', errors='replace')},
        '.txt': lambda: {"type": "text", "text": Path(filepath).read_text(encoding='utf-8', errors='replace')},
        '.html': lambda: {"type": "html", "text": Path(filepath).read_text(encoding='utf-8', errors='replace')},
        '.eml': lambda: {"type": "email", "text": Path(filepath).read_text(encoding='utf-8', errors='replace')},
    }
    
    # Image extensions (try OCR)
    image_exts = {'.png', '.jpg', '.jpeg', '.gif', '.tiff', '.tif', '.bmp', '.webp'}
    if ext in image_exts:
        return parse_image_ocr(filepath, verbose)
    
    parser = parsers.get(ext)
    if not parser:
        # Try treating as plain text
        try:
            return {"type": "unknown", "text": Path(filepath).read_text(encoding='utf-8', errors='replace')}
        except UnicodeDecodeError:
            raise RuntimeError(f"Unsupported file type: {ext}. Try a text-based format.")
    
    data = parser()
    data["metadata"] = metadata
    return data


def format_output(data, output_format="text", verbose=False):
    """Format parsed data according to output format."""
    
    if output_format == "json":
        return json.dumps(data, indent=2, ensure_ascii=False, default=str)
    
    elif output_format == "metadata":
        meta = data.get("metadata", {})
        return json.dumps(meta, indent=2, ensure_ascii=False, default=str)
    
    elif output_format == "tables":
        # Extract all tables
        tables = data.get("tables", [])
        if data.get("type") == "xlsx":
            for sheet_name, sheet_data in data.get("sheets", {}).items():
                for row in sheet_data.get("rows", []):
                    tables.append(row)
        
        if not tables:
            return "No tables found in document."
        
        output = io.StringIO()
        writer = csv.writer(output)
        for table in tables:
            if isinstance(table, dict) and "rows" in table:
                for row in table["rows"]:
                    writer.writerow(row)
            elif isinstance(table, (list, tuple)):
                writer.writerow(table)
        return output.getvalue()
    
    elif output_format == "pages":
        # PDF pages format
        pages = data.get("pages", [])
        if not pages:
            return "No pages found."
        result = []
        for page in pages:
            result.append(f"--- Page {page['page']} ---\n{page['text']}")
        return "\n\n".join(result)
    
    elif output_format == "summary":
        # Basic summary (no LLM needed)
        doc_type = data.get("type", "unknown")
        meta = data.get("metadata", {})
        
        summary_parts = [
            f"📄 Document Summary",
            f"Type: {doc_type}",
            f"File: {meta.get('filename', 'unknown')}",
            f"Size: {meta.get('size_human', 'unknown')}",
        ]
        
        if doc_type == "pdf":
            total_pages = data.get("total_pages", 0)
            total_chars = sum(len(p.get("text", "")) for p in data.get("pages", []))
            summary_parts.append(f"Pages: {total_pages}")
            summary_parts.append(f"Characters: {total_chars:,}")
            
            # Word frequency for topic hint
            if total_chars > 0:
                all_text = " ".join(p.get("text", "") for p in data.get("pages", []))
                words = all_text.lower().split()
                freq = {}
                stop_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
                             'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
                             'could', 'should', 'may', 'might', 'can', 'shall', 'to', 'of', 'in',
                             'for', 'on', 'with', 'at', 'by', 'from', 'as', 'into', 'through',
                             'and', 'but', 'or', 'not', 'this', 'that', 'these', 'those', 'i',
                             'you', 'he', 'she', 'it', 'we', 'they', 'what', 'which', 'who',
                             'how', 'when', 'where', 'why', 'all', 'each', 'every', 'both',
                             'few', 'more', 'most', 'other', 'some', 'such', 'no', 'only',
                             'own', 'same', 'so', 'than', 'too', 'very'}
                for w in words:
                    if len(w) > 3 and w not in stop_words:
                        freq[w] = freq.get(w, 0) + 1
                top_words = sorted(freq.items(), key=lambda x: -x[1])[:10]
                if top_words:
                    summary_parts.append(f"Key topics: {', '.join(w for w, c in top_words)}")
        
        elif doc_type == "pdf_scanned":
            total_pages = data.get("total_pages", 0)
            total_chars = sum(len(p.get("text", "")) for p in data.get("pages", []))
            summary_parts.append(f"Pages: {total_pages} (scanned, OCR'd)")
            summary_parts.append(f"Characters: {total_chars:,}")
            if total_chars > 0:
                all_text = " ".join(p.get("text", "") for p in data.get("pages", []))
                words = all_text.lower().split()
                freq = {}
                stop_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
                             'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
                             'could', 'should', 'may', 'might', 'can', 'shall', 'to', 'of', 'in',
                             'for', 'on', 'with', 'at', 'by', 'from', 'as', 'into', 'through',
                             'and', 'but', 'or', 'not', 'this', 'that', 'these', 'those', 'i',
                             'you', 'he', 'she', 'it', 'we', 'they', 'what', 'which', 'who',
                             'how', 'when', 'where', 'why', 'all', 'each', 'every', 'both',
                             'few', 'more', 'most', 'other', 'some', 'such', 'no', 'only',
                             'own', 'same', 'so', 'than', 'too', 'very'}
                for w in words:
                    if len(w) > 3 and w not in stop_words:
                        freq[w] = freq.get(w, 0) + 1
                top_words = sorted(freq.items(), key=lambda x: -x[1])[:10]
                if top_words:
                    summary_parts.append(f"Key topics: {', '.join(w for w, c in top_words)}")
        
        elif doc_type in ("docx", "doc", "odt", "rtf"):
            paragraphs = data.get("paragraphs", [])
            summary_parts.append(f"Paragraphs: {len(paragraphs)}")
            if paragraphs:
                # First paragraph as preview
                preview = paragraphs[0].get("text", "")[:200] if isinstance(paragraphs[0], dict) else str(paragraphs[0])[:200]
                summary_parts.append(f"Preview: {preview}...")
        
        elif doc_type == "xlsx":
            sheets = data.get("sheets", {})
            summary_parts.append(f"Sheets: {', '.join(sheets.keys())}")
            for name, sdata in sheets.items():
                dims = sdata.get("dimensions", "unknown")
                summary_parts.append(f"  {name}: {dims}")
        
        elif doc_type == "csv":
            meta = data.get("metadata", {})
            summary_parts.append(f"Rows: {meta.get('total_rows', 0):,}")
            summary_parts.append(f"Columns: {meta.get('columns', 0)}")
            summary_parts.append(f"Delimiter: {meta.get('delimiter', ',')}")
        
        elif doc_type == "pptx":
            slides = data.get("slides", [])
            summary_parts.append(f"Slides: {len(slides)}")
        
        elif doc_type == "epub":
            toc = data.get("toc", [])
            summary_parts.append(f"Chapters: {len(toc)}")
            if toc:
                summary_parts.append(f"TOC: {', '.join(toc[:10])}")
        
        return "\n".join(summary_parts)
    
    else:  # "text" — default readable format
        doc_type = data.get("type", "unknown")
        meta = data.get("metadata", {})
        
        lines = [
            f"═══════════════════════════════════════",
            f"  📄 {meta.get('filename', 'Document')}",
            f"  Type: {doc_type} | Size: {meta.get('size_human', 'unknown')}",
            f"═══════════════════════════════════════",
            ""
        ]
        
        if doc_type == "pdf":
            for page in data.get("pages", []):
                lines.append(f"── Page {page['page']} ──")
                lines.append(page.get("text", ""))
                lines.append("")
            
            # Show tables if any
            tables = data.get("tables", [])
            if tables:
                lines.append("═══════════════════════════════════════")
                lines.append("  📊 Tables Found")
                lines.append("═══════════════════════════════════════")
                for t in tables:
                    lines.append(f"\nTable (Page {t['page']}, Index {t['table_index']}):")
                    for row in t['rows']:
                        lines.append("  | " + " | ".join(str(c) for c in row) + " |")
                lines.append("")
        
        elif doc_type == "pdf_scanned":
            for page in data.get("pages", []):
                lines.append(f"── Page {page['page']} (OCR) ──")
                lines.append(page.get("text", ""))
                lines.append("")
        
        elif doc_type in ("docx", "doc", "odt", "rtf"):
            paragraphs = data.get("paragraphs", [])
            if isinstance(paragraphs[0], dict) if paragraphs else False:
                for p in paragraphs:
                    style = f" [{p.get('style', '')}]" if p.get('style') else ""
                    lines.append(f"{p.get('text', '')}{style}")
            else:
                for p in paragraphs:
                    lines.append(str(p))
            
            # Show tables
            tables = data.get("tables", [])
            if tables:
                lines.append("")
                lines.append("═══════════════════════════════════════")
                lines.append("  📊 Tables Found")
                lines.append("═══════════════════════════════════════")
                for t in tables:
                    lines.append(f"\nTable (Index {t['index']}):")
                    for row in t['rows']:
                        lines.append("  | " + " | ".join(str(c) for c in row) + " |")
        
        elif doc_type == "xlsx":
            for sheet_name, sdata in data.get("sheets", {}).items():
                lines.append(f"\n📊 Sheet: {sheet_name} ({sdata.get('dimensions', '')})")
                lines.append("─" * 60)
                for row in sdata.get("rows", []):
                    lines.append("  | " + " | ".join(str(c) for c in row) + " |")
        
        elif doc_type == "csv":
            rows = data.get("rows", [])
            for row in rows:
                lines.append("  | " + " | ".join(str(c) for c in row) + " |")
        
        elif doc_type == "pptx":
            for slide in data.get("slides", []):
                lines.append(f"\n── Slide {slide['slide']} ──")
                for item in slide.get("content", []):
                    lines.append(f"  [{item.get('shape_type', '')}] {item.get('text', '')}")
        
        elif doc_type == "epub":
            toc = data.get("toc", [])
            if toc:
                lines.append("📑 Table of Contents:")
                for i, chapter in enumerate(toc, 1):
                    lines.append(f"  {i}. {chapter}")
            lines.append("")
            lines.append(data.get("content", ""))
        
        elif doc_type in ("text", "markdown", "html", "email"):
            lines.append(data.get("text", ""))
        
        elif doc_type == "image_ocr":
            lines.append("🖼️ OCR Result:")
            lines.append(data.get("text", ""))
        
        else:
            lines.append(data.get("text", "No content extracted."))
        
        return "\n".join(lines)


# ── CLI Entry Point ────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Universal document reader — parse Word, Excel, PDF, and more",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 parse_document.py report.docx
  python3 parse_document.py data.xlsx --format tables
  python3 parse_document.py scan.pdf --format pages
  python3 parse_document.py meeting.pptx --format json
  python3 parse_document.py book.epub --format summary
        """
    )
    
    parser.add_argument("filepath", help="Path to the document file")
    parser.add_argument("--format", choices=["text", "json", "summary", "tables", "metadata", "pages"],
                       default="text", help="Output format (default: text)")
    parser.add_argument("--max-pages", type=int, default=0,
                       help="Max pages to extract (PDF only, 0 = all)")
    parser.add_argument("--sheet", default=None,
                       help="Sheet name or index (Excel only)")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Show debug info")
    
    args = parser.parse_args()
    
    try:
        data = parse_document(
            args.filepath,
            output_format=args.format,
            max_pages=args.max_pages,
            sheet=args.sheet,
            verbose=args.verbose,
        )
        
        output = format_output(data, args.format, args.verbose)
        print(output)
        
    except FileNotFoundError as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)
    except RuntimeError as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print(f"❌ Unexpected error: {e}", file=sys.stderr)
        if args.verbose:
            traceback.print_exc()
        sys.exit(3)


if __name__ == "__main__":
    main()
