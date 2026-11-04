#!/usr/bin/env bash
# Quick verification script for local-vision-toolkit
# Checks: python deps, tesseract binary, sample image OCR, chart detection, diagram detection.
# Exit 0 = all good. Exit 1 = something broken.

set -euo pipefail
SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT="$SKILL_DIR/scripts/vision_tool.py"
FAIL=0

echo "=== local-vision-toolkit verification ==="

# 1. Python deps
echo -n "  Pillow ... "
python3 -c "from PIL import Image; print('OK')" 2>/dev/null && echo "OK" || { echo "MISSING"; FAIL=1; }

echo -n "  pytesseract ... "
python3 -c "import pytesseract; print('OK')" 2>/dev/null && echo "OK" || { echo "MISSING"; FAIL=1; }

echo -n "  opencv-python ... "
python3 -c "import cv2; print('OK')" 2>/dev/null && echo "OK" || { echo "MISSING"; FAIL=1; }

echo -n "  numpy ... "
python3 -c "import numpy; print('OK')" 2>/dev/null && echo "OK" || { echo "MISSING"; FAIL=1; }

echo -n "  scikit-image ... "
python3 -c "import skimage; print('OK')" 2>/dev/null && echo "OK" || { echo "MISSING"; FAIL=1; }

# 2. System: tesseract binary + spa language
echo -n "  tesseract binary ... "
which tesseract >/dev/null 2>&1 && echo "OK" || { echo "MISSING"; FAIL=1; }

echo -n "  tesseract spa lang ... "
if tesseract --list-langs 2>/dev/null | grep -q "^spa$"; then
    echo "OK"
else
    echo "MISSING (run: apt-get install tesseract-ocr-spa)"
    FAIL=1
fi

# 3. Generate test image and run OCR
python3 -c "
from PIL import Image, ImageDraw
img = Image.new('RGB', (400, 100), color='white')
d = ImageDraw.Draw(img)
d.text((10, 30), 'Vision Toolkit funciona', fill='black')
img.save('/tmp/_lvt_verify.png')
" 2>/dev/null

echo -n "  OCR image test ... "
RESULT=$(python3 "$SCRIPT" /tmp/_lvt_verify.png --action ocr 2>/dev/null)
if echo "$RESULT" | grep -qi "vision"; then
    echo "OK"
else
    echo "OCR returned unexpected result:"
    echo "  $RESULT"
    FAIL=1
fi

# 4. Generate test chart image and run chart analysis
python3 -c "
from PIL import Image, ImageDraw
img = Image.new('RGB', (400, 300), color='white')
d = ImageDraw.Draw(img)
# Draw some bars to simulate a bar chart
for i in range(5):
    height = 50 + i * 40
    d.rectangle([50+i*60, 250-height, 90+i*60, 250], fill='blue')
# Draw a circle to simulate a pie chart element
d.ellipse([250, 50, 350, 150], fill='red')
img.save('/tmp/_lvt_verify_chart.png')
" 2>/dev/null

echo -n "  Chart detection test ... "
RESULT=$(python3 "$SCRIPT" /tmp/_lvt_verify_chart.png --action chart 2>/dev/null)
if echo "$RESULT" | grep -qi "bar_chart\|pie_chart\|data_visualization"; then
    echo "OK"
else
    echo "Chart analysis returned unexpected result:"
    echo "  $RESULT"
    FAIL=1
fi

# 5. Generate test diagram image and run diagram analysis
python3 -c "
from PIL import Image, ImageDraw
img = Image.new('RGB', (400, 300), color='white')
d = ImageDraw.Draw(img)
# Draw rectangles (shapes in a flowchart)
d.rectangle([50, 50, 150, 100], outline='black', width=2)
d.rectangle([250, 50, 350, 100], outline='black', width=2)
d.rectangle([50, 200, 150, 250], outline='black', width=2)
# Draw a line connecting them
d.line([(150, 75), (250, 75)], fill='black', width=2)
d.line([(100, 100), (100, 200)], fill='black', width=2)
img.save('/tmp/_lvt_verify_diagram.png')
" 2>/dev/null

echo -n "  Diagram detection test ... "
RESULT=$(python3 "$SCRIPT" /tmp/_lvt_verify_diagram.png --action diagram 2>/dev/null)
if echo "$RESULT" | grep -qi "flowchart\|diagram"; then
    echo "OK"
else
    echo "Diagram analysis returned unexpected result:"
    echo "  $RESULT"
    FAIL=1
fi

# 6. Full analysis test
echo -n "  Full analysis test ... "
RESULT=$(python3 "$SCRIPT" /tmp/_lvt_verify.png --action full 2>/dev/null)
if echo "$RESULT" | grep -qi "description\|ocr\|metadata"; then
    echo "OK"
else
    echo "Full analysis returned unexpected result:"
    echo "  $RESULT"
    FAIL=1
fi

# 7. JSON format test
echo -n "  JSON format test ... "
RESULT=$(python3 "$SCRIPT" /tmp/_lvt_verify.png --action metadata --format json 2>/dev/null)
if echo "$RESULT" | python3 -c "import sys,json; json.loads(sys.stdin.read())" 2>/dev/null; then
    echo "OK"
else
    echo "JSON output is not valid JSON"
    FAIL=1
fi

# Cleanup
rm -f /tmp/_lvt_verify.png /tmp/_lvt_verify_chart.png /tmp/_lvt_verify_diagram.png

echo ""
if [ "$FAIL" -eq 0 ]; then
    echo "All checks passed"
else
    echo "Some checks failed — run the fix steps in SKILL.md"
fi
exit $FAIL
