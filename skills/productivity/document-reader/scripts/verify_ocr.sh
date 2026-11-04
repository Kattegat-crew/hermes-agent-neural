#!/usr/bin/env bash
# Quick verification script for document-reader OCR — run after skill install/update.
# Checks: pytesseract, opencv-python, tesseract binaries, lang=spa, sample image OCR.
# Exit 0 = all good. Exit 1 = something broken.

set -euo pipefail
SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT="$SKILL_DIR/scripts/parse_document.py"
FAIL=0

echo "=== document-reader OCR verification ==="

# 1. Python deps
echo -n "  pytesseract ... "
python3 -c "import pytesseract; print('OK')" 2>/dev/null && echo "✓" || { echo "✗ MISSING"; FAIL=1; }

echo -n "  opencv-python ... "
python3 -c "import cv2; print('OK')" 2>/dev/null && echo "✓" || { echo "✗ MISSING"; FAIL=1; }

echo -n "  PyMuPDF ... "
python3 -c "import fitz; print('OK')" 2>/dev/null && echo "✓" || { echo "✗ MISSING"; FAIL=1; }

echo -n "  Pillow ... "
python3 -c "from PIL import Image; print('OK')" 2>/dev/null && echo "✓" || { echo "✗ MISSING"; FAIL=1; }

# 2. System: tesseract binary + spa language
echo -n "  tesseract binary ... "
which tesseract >/dev/null 2>&1 && echo "✓" || { echo "✗ MISSING"; FAIL=1; }

echo -n "  tesseract spa lang ... "
if tesseract --list-langs 2>/dev/null | grep -q "^spa$"; then
    echo "✓"
else
    echo "✗ MISSING (run: apt-get install tesseract-ocr-spa)"
    FAIL=1
fi

# 3. Generate a test image and run OCR
python3 -c "
from PIL import Image, ImageDraw
img = Image.new('RGB', (400, 100), color='white')
d = ImageDraw.Draw(img)
d.text((10, 30), 'Verificacion OCR funciona', fill='black')
img.save('/tmp/_dr_verify.png')
" 2>/dev/null

echo -n "  OCR image test ... "
RESULT=$(python3 "$SCRIPT" /tmp/_dr_verify.png --format text 2>/dev/null)
if echo "$RESULT" | grep -qi "verif"; then
    echo "✓"
else
    echo "✗ OCR returned unexpected result:"
    echo "  $RESULT"
    FAIL=1
fi

# 4. Generate a test scanned PDF and run OCR
python3 -c "
from PIL import Image, ImageDraw
img = Image.new('RGB', (400, 200), color='white')
d = ImageDraw.Draw(img)
d.text((10, 30), 'PDF escaneado de prueba', fill='black')
d.text((10, 80), 'Con texto en español', fill='black')
img.save('/tmp/_dr_verify.pdf', 'PDF')
" 2>/dev/null

echo -n "  OCR scanned PDF test ... "
RESULT=$(python3 "$SCRIPT" /tmp/_dr_verify.pdf --format text 2>/dev/null)
if echo "$RESULT" | grep -qi "escaneado"; then
    echo "✓"
else
    echo "✗ OCR returned unexpected result for scanned PDF:"
    echo "  $RESULT"
    FAIL=1
fi

# Cleanup
rm -f /tmp/_dr_verify.png /tmp/_dr_verify.pdf

echo ""
if [ "$FAIL" -eq 0 ]; then
    echo "All checks passed ✓"
else
    echo "Some checks failed ✗ — run the fix steps in SKILL.md"
fi
exit $FAIL
