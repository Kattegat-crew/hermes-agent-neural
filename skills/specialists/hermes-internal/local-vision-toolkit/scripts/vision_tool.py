#!/usr/bin/env python3
"""
Local Vision Toolkit — Autonomous image analysis without model vision capabilities.

Runs 100% locally via Python (OpenCV, Tesseract, Pillow, scikit-image).
Returns structured text descriptions that ANY model can consume.

Actions:
  ocr       — Extract all text from image (with preprocessing)
  structure — Detect layout blocks, tables, charts, diagrams
  metadata  — Colors, resolution, dominant elements, aspect ratio
  chart     — Analyze charts/graphs/diagrams
  full      — Full analysis: OCR + structure + metadata + description
  diagram   — Detect and describe flowcharts, org charts, architecture diagrams
  infographic — Extract text, sections, and visual hierarchy from infographics
"""

import argparse
import json
import os
import sys
import traceback
from pathlib import Path
from collections import Counter
from datetime import datetime

# ── Libraries ──────────────────────────────────────────────────────────────
try:
    from PIL import Image, ImageDraw, ImageFilter
except ImportError:
    Image = None

try:
    import pytesseract
except ImportError:
    pytesseract = None

try:
    import cv2
except ImportError:
    cv2 = None

try:
    import numpy as np
except ImportError:
    np = None

try:
    from skimage import measure, color, filters
except ImportError:
    measure = None
    color = None
    filters = None

try:
    import matplotlib
    matplotlib.use('Agg')
    from matplotlib.colors import to_rgb, to_hex
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

# ── Helpers ────────────────────────────────────────────────────────────────

def load_image(filepath):
    """Load image from file, return PIL Image."""
    if not Image:
        raise RuntimeError("Pillow not installed. Run: python3 -m pip install Pillow")
    img = Image.open(filepath).convert("RGB")
    return img

def pil_to_cv2(img):
    """Convert PIL Image to OpenCV format."""
    if not cv2:
        raise RuntimeError("OpenCV not installed: pip install opencv-python")
    arr = np.array(img)
    return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)

def preprocess_for_ocr(img):
    """Pre-process image for OCR: grayscale, denoise, threshold, deskew."""
    if not cv2:
        return img
    arr = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2GRAY)
    arr = cv2.fastNlMeansDenoising(arr, h=10)
    arr = cv2.adaptiveThreshold(arr, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                 cv2.THRESH_BINARY, 11, 2)
    return Image.fromarray(arr)

def get_dominant_colors(img, k=5):
    """Extract dominant colors from image using k-means-like pixel clustering."""
    if not np:
        return []
    arr = np.array(img).reshape(-1, 3)
    arr = arr.astype(float)
    arr = arr / 64
    arr = arr.round().astype(int) * 64
    arr = np.clip(arr, 0, 255)
    counter = Counter(map(tuple, arr))
    return [dict(rgb=list(k), count=v) for k, v in counter.most_common(k)]

def detect_edges(img):
    """Detect edges and return edge density (0.0 to 1.0)."""
    if not cv2:
        return 0.0
    gray = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    return float(np.count_nonzero(edges)) / (edges.shape[0] * edges.shape[1])

def detect_text_regions(img):
    """Detect regions likely containing text using edge analysis."""
    if not cv2:
        return []
    gray = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(gray, 30, 100)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    regions = []
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        if w > 20 and h > 10 and w < img.width * 0.9:
            regions.append({"x": x, "y": y, "w": w, "h": h})
    return regions[:50]

# ── OCR Action ─────────────────────────────────────────────────────────────

def action_ocr(img, filepath, lang="spa+eng"):
    """Extract text from image using Tesseract OCR with OpenCV preprocessing."""
    if not Image or not pytesseract:
        return {"error": "Pillow and pytesseract required for OCR"}

    preprocessed = preprocess_for_ocr(img)
    text = pytesseract.image_to_string(preprocessed, lang=lang).strip()
    text_raw = pytesseract.image_to_string(img, lang=lang).strip()

    try:
        data = pytesseract.image_to_data(preprocessed, lang=lang, output_type=pytesseract.Output.DICT)
        words = [w for w in data['text'] if w.strip()]
        avg_conf = sum(data['conf'][i] for i in range(len(words))) / max(len(words), 1)
    except Exception:
        avg_conf = 50
        words = []

    return {
        "action": "ocr",
        "language": lang,
        "text": text,
        "text_raw": text_raw,
        "confidence_estimate": round(avg_conf, 1),
        "word_count": len(words),
        "char_count": len(text),
        "preprocessed": True,
        "preprocessing": "grayscale + denoising + adaptive threshold",
    }

# ── Metadata Action ────────────────────────────────────────────────────────

def action_metadata(img, filepath):
    """Extract image metadata: resolution, aspect ratio, colors, complexity."""
    w, h = img.size
    aspect = w / h if h > 0 else 0
    colors = get_dominant_colors(img, k=5)
    edge_density = detect_edges(img)

    if np:
        arr = np.array(img)
        brightness = float(np.mean(arr))
    else:
        brightness = 128

    has_alpha = False
    try:
        alpha = img.split()[-1]
        has_alpha = alpha.getextrema()[0] < 255
    except Exception:
        pass

    return {
        "action": "metadata",
        "filename": Path(filepath).name,
        "resolution": f"{w}x{h}",
        "width": w,
        "height": h,
        "aspect_ratio": round(aspect, 2),
        "aspect_label": "wide" if aspect > 1.5 else "tall" if aspect < 0.67 else "square",
        "dominant_colors": colors,
        "brightness": round(brightness, 1),
        "edge_density": round(edge_density, 3),
        "complexity": "high" if edge_density > 0.3 else "medium" if edge_density > 0.1 else "low",
        "has_transparency": has_alpha,
    }

# ── Structure Action ───────────────────────────────────────────────────────

def action_structure(img):
    """Detect structural elements: text blocks, tables, charts, diagrams."""
    if not cv2:
        return {"error": "OpenCV required for structure detection"}

    gray = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2GRAY)
    h, w = gray.shape

    kernel_h = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
    horizontal = cv2.morphologyEx(gray, cv2.MORPH_OPEN, kernel_h, iterations=2)
    h_lines = np.count_nonzero(cv2.threshold(horizontal, 0, 255, cv2.THRESH_BINARY)[1])

    kernel_v = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 40))
    vertical = cv2.morphologyEx(gray, cv2.MORPH_OPEN, kernel_v, iterations=2)
    v_lines = np.count_nonzero(cv2.threshold(vertical, 0, 255, cv2.THRESH_BINARY)[1])

    _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    blocks = []
    for cnt in contours:
        x, y, cw, ch = cv2.boundingRect(cnt)
        area = cw * ch
        if area > 1000 and area < h * w * 0.9:
            blocks.append({"x": x, "y": y, "w": cw, "h": ch, "area_ratio": round(area / (w * h), 3)})
    blocks.sort(key=lambda b: b["y"])

    total_pixels = h * w
    has_table = (h_lines / total_pixels > 0.001 and v_lines / total_pixels > 0.001)

    has_chart = False
    if np:
        qh, qw = h // 2, w // 2
        quadrants = [gray[0:qh, 0:qw], gray[0:qh, qw:], gray[qh:, 0:qw], gray[qh:, qw:]]
        variances = [float(np.var(q)) for q in quadrants]
        if max(variances) > 1000 and min(variances) < 100:
            has_chart = True

    return {
        "action": "structure",
        "image_size": f"{w}x{h}",
        "text_blocks_detected": len(blocks),
        "blocks": blocks[:20],
        "potential_table": has_table,
        "horizontal_lines": h_lines,
        "vertical_lines": v_lines,
        "potential_chart": has_chart,
        "edge_density": round(detect_edges(img), 3),
    }

# ── Chart Analysis Action ──────────────────────────────────────────────────

def action_chart(img):
    """Analyze charts, graphs, and data visualizations."""
    if not Image or not np:
        return {"error": "Pillow and numpy required for chart analysis"}

    w, h = img.size
    gray = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2GRAY) if cv2 else np.array(img)
    _, thresh = cv2.threshold(gray, 220, 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    vertical_bars = 0
    horizontal_bars = 0
    circles = 0

    for cnt in contours:
        x, y, cw, ch = cv2.boundingRect(cnt)
        area = cw * ch
        if 500 < area < w * h * 0.5:
            aspect = cw / max(ch, 1)
            if aspect < 0.5 and ch > 30:
                vertical_bars += 1
            elif aspect > 2 and cw > 30:
                horizontal_bars += 1
            perimeter = cv2.arcLength(cnt, True)
            if perimeter > 0:
                circularity = 4 * np.pi * cv2.contourArea(cnt) / (perimeter * perimeter)
                if circularity > 0.7:
                    circles += 1

    chart_type = "unknown"
    if vertical_bars > 2:
        chart_type = "bar_chart"
    elif circles > 2:
        chart_type = "pie_chart"
    elif horizontal_bars > 2:
        chart_type = "horizontal_bar_chart"
    elif vertical_bars > 0 or horizontal_bars > 0:
        chart_type = "mixed_chart"
    else:
        chart_type = "data_visualization"

    colors = get_dominant_colors(img, k=8)
    color_count = len([c for c in colors if c["count"] > w * h * 0.01])

    return {
        "action": "chart_analysis",
        "detected_type": chart_type,
        "vertical_bars": vertical_bars,
        "horizontal_bars": horizontal_bars,
        "circular_elements": circles,
        "color_count": color_count,
        "dominant_colors": colors,
        "is_data_viz": vertical_bars > 0 or circles > 0 or horizontal_bars > 0,
    }

# ── Diagram Analysis Action ────────────────────────────────────────────────

def action_diagram(img):
    """Detect and describe flowcharts, org charts, architecture diagrams."""
    if not cv2:
        return {"error": "OpenCV required for diagram analysis"}

    w, h = img.size
    gray = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2GRAY)

    _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    shapes = {"rectangles": 0, "circles": 0, "diamonds": 0, "lines": 0}

    for cnt in contours:
        x, y, cw, ch = cv2.boundingRect(cnt)
        area = cw * ch
        if 500 < area < w * h * 0.3:
            perimeter = cv2.arcLength(cnt, True)
            if perimeter == 0:
                continue
            circularity = 4 * np.pi * cv2.contourArea(cnt) / (perimeter * perimeter) if cv2.contourArea(cnt) > 0 else 0
            approx = cv2.approxPolyDP(cnt, 0.04 * perimeter, True)
            vertices = len(approx)

            if circularity > 0.7:
                shapes["circles"] += 1
            elif vertices == 4:
                shapes["rectangles"] += 1
            elif vertices == 3 or vertices == 5:
                shapes["diamonds"] += 1
            elif area < 1000:
                shapes["lines"] += 1

    edges = cv2.Canny(gray, 30, 100)
    lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=30, minLineLength=50, maxLineGap=10)
    line_count = len(lines) if lines is not None else 0

    text_regions = detect_text_regions(img)

    diagram_type = "unknown"
    total_shapes = sum(v for k, v in shapes.items() if k != "lines")
    if shapes["rectangles"] > 3 and line_count > 5:
        diagram_type = "flowchart"
    elif shapes["rectangles"] > 2 and shapes["circles"] > 0:
        diagram_type = "org_chart"
    elif line_count > 10:
        diagram_type = "network_diagram"
    elif total_shapes > 2:
        diagram_type = "architecture_diagram"
    else:
        diagram_type = "simple_diagram"

    return {
        "action": "diagram_analysis",
        "diagram_type": diagram_type,
        "shapes": shapes,
        "total_shapes": total_shapes,
        "connections": line_count,
        "text_regions": len(text_regions),
        "complexity": "high" if total_shapes > 10 or line_count > 20 else "medium" if total_shapes > 5 else "low",
    }

# ── Infographic Analysis Action ────────────────────────────────────────────

def action_infographic(img):
    """Extract sections, text hierarchy, and visual structure from infographics."""
    if not Image or not cv2:
        return {"error": "Pillow and OpenCV required for infographic analysis"}

    w, h = img.size
    arr = np.array(img)
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)

    section_breaks = []
    for y in range(0, h, max(1, h // 50)):
        row = gray[y:y+10, :]
        if row.size > 0:
            mean_val = np.mean(row)
            if y > 0:
                prev_row = gray[y-10:y, :]
                if prev_row.size > 0:
                    prev_mean = np.mean(prev_row)
                    if abs(mean_val - prev_mean) > 30:
                        section_breaks.append(y)

    cleaned_breaks = []
    for b in section_breaks:
        if not cleaned_breaks or b - cleaned_breaks[-1] > h // 20:
            cleaned_breaks.append(b)

    hsv = cv2.cvtColor(arr, cv2.COLOR_RGB2HSV)
    saturation = hsv[:, :, 1]
    colored_regions = np.count_nonzero(saturation > 80)
    color_ratio = colored_regions / (w * h)

    _, text_thresh = cv2.threshold(gray, 50, 255, cv2.THRESH_BINARY_INV)
    text_pixels = np.count_nonzero(text_thresh)
    text_ratio = text_pixels / (w * h)

    blocks = detect_text_regions(img)
    blocks.sort(key=lambda b: b["y"])

    title_candidate = None
    if blocks:
        top_blocks = [b for b in blocks if b["y"] < h * 0.2]
        if top_blocks:
            title_candidate = max(top_blocks, key=lambda b: b["w"] * b["h"])

    return {
        "action": "infographic_analysis",
        "sections_detected": len(cleaned_breaks) + 1,
        "section_breaks": cleaned_breaks,
        "text_ratio": round(text_ratio, 3),
        "color_ratio": round(color_ratio, 3),
        "is_visual_heavy": color_ratio > text_ratio * 2,
        "is_text_heavy": text_ratio > color_ratio * 2,
        "title_candidate": {
            "x": title_candidate["x"], "y": title_candidate["y"],
            "w": title_candidate["w"], "h": title_candidate["h"],
        } if title_candidate else None,
        "total_text_blocks": len(blocks),
        "layout": "vertical_sections" if len(cleaned_breaks) > 2 else "single_column" if len(blocks) < 5 else "multi_column",
    }

# ── Full Analysis Action ───────────────────────────────────────────────────

def action_full(img, filepath):
    """Run all analyses and return combined results."""
    results = {
        "action": "full",
        "filename": Path(filepath).name,
        "timestamp": datetime.now().isoformat(),
    }

    for name, fn in [("metadata", action_metadata), ("ocr", action_ocr),
                      ("structure", action_structure), ("chart", action_chart),
                      ("diagram", action_diagram), ("infographic", action_infographic)]:
        try:
            results[name] = fn(img, filepath) if name in ("metadata", "ocr") else fn(img)
        except Exception as e:
            results[f"{name}_error"] = str(e)

    results["description"] = generate_description(results)
    return results

# ── Natural Language Description ────────────────────────────────────────────

def generate_description(results):
    """Generate a natural language description from structured analysis results."""
    parts = []

    meta = results.get("metadata", {})
    if meta:
        parts.append(f"Image ({meta.get('resolution', 'unknown')}), {meta.get('aspect_label', 'unknown')} aspect ratio, {meta.get('complexity', 'unknown')} complexity")
        colors = meta.get("dominant_colors", [])
        if colors:
            color_names = [f"#{c['rgb'][0]:02x}{c['rgb'][1]:02x}{c['rgb'][2]:02x}" for c in colors[:3]]
            parts.append(f"Colors: {', '.join(color_names)}")

    ocr = results.get("ocr", {})
    if ocr and "text" in ocr and ocr["text"]:
        text = ocr["text"][:500]
        parts.append(f"Text detected ({ocr.get('word_count', 0)} words, confidence {ocr.get('confidence_estimate', '?')}%): '{text}'")

    struct = results.get("structure", {})
    if struct:
        if struct.get("potential_table"):
            parts.append("Structure contains a potential table")
        if struct.get("potential_chart"):
            parts.append("Structure contains a potential chart/graph")
        if struct.get("text_blocks_detected", 0) > 0:
            parts.append(f"Layout has {struct['text_blocks_detected']} distinct text blocks")

    chart = results.get("chart", {})
    if chart and chart.get("is_data_viz"):
        parts.append(f"Chart type: {chart.get('detected_type', 'unknown')}")

    diag = results.get("diagram", {})
    if diag and diag.get("diagram_type") != "unknown":
        parts.append(f"Diagram type: {diag['diagram_type']} ({diag.get('total_shapes', 0)} shapes, {diag.get('connections', 0)} connections)")

    info = results.get("infographic", {})
    if info and info.get("sections_detected", 0) > 1:
        parts.append(f"Infographic with {info['sections_detected']} sections, {info.get('layout', 'unknown')} layout")

    if not parts:
        return "No significant content detected in image."

    return " ".join(parts)

# ── Main Dispatcher ────────────────────────────────────────────────────────

def analyze_image(filepath, action="full", output_format="text", lang="spa+eng"):
    """Main dispatcher — runs requested action(s) on image."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    img = load_image(filepath)
    results = {}

    actions = {
        "ocr": lambda: action_ocr(img, filepath, lang),
        "structure": lambda: action_structure(img),
        "metadata": lambda: action_metadata(img, filepath),
        "chart": lambda: action_chart(img),
        "diagram": lambda: action_diagram(img),
        "infographic": lambda: action_infographic(img),
        "full": lambda: action_full(img, filepath),
    }

    if action == "full":
        results = actions["full"]()
    elif action in actions:
        results = actions[action]()
    else:
        raise ValueError(f"Unknown action: {action}. Valid: {list(actions.keys())}")

    results["image_info"] = {
        "filepath": os.path.abspath(filepath),
        "resolution": f"{img.width}x{img.height}",
    }

    return results

# ── Output Formatting ──────────────────────────────────────────────────────

def format_output(data, output_format="text"):
    """Format results for human or machine consumption."""
    if output_format == "json":
        return json.dumps(data, indent=2, ensure_ascii=False, default=str)

    lines = []
    action = data.get("action", "unknown")

    lines.append(f"Vision Analysis: {action}")
    lines.append(f"File: {data.get('image_info', {}).get('filepath', 'unknown')}")
    lines.append(f"Resolution: {data.get('image_info', {}).get('resolution', 'unknown')}")
    lines.append("")

    if "description" in data:
        lines.append(f"Description: {data['description']}")
        lines.append("")

    meta = data.get("metadata", {})
    if meta:
        lines.append("Metadata:")
        lines.append(f"  Resolution: {meta.get('resolution', '?')}")
        lines.append(f"  Aspect: {meta.get('aspect_label', '?')}")
        lines.append(f"  Complexity: {meta.get('complexity', '?')}")
        colors = meta.get("dominant_colors", [])
        if colors:
            clist = [f"#{c['rgb'][0]:02x}{c['rgb'][1]:02x}{c['rgb'][2]:02x}" for c in colors[:3]]
            lines.append(f"  Colors: {', '.join(clist)}")
        lines.append("")

    ocr = data.get("ocr", {})
    if ocr and "text" in ocr and ocr["text"]:
        lines.append("OCR Text:")
        lines.append(f"  Words: {ocr.get('word_count', '?')} | Confidence: {ocr.get('confidence_estimate', '?')}%")
        lines.append(f"  {ocr['text'][:1000]}")
        lines.append("")

    struct = data.get("structure", {})
    if struct:
        lines.append("Structure:")
        lines.append(f"  Text blocks: {struct.get('text_blocks_detected', 0)}")
        if struct.get("potential_table"):
            lines.append(f"  [!] Potential table detected")
        if struct.get("potential_chart"):
            lines.append(f"  [!] Potential chart detected")
        lines.append("")

    chart = data.get("chart", {})
    if chart:
        lines.append("Chart Analysis:")
        lines.append(f"  Type: {chart.get('detected_type', '?')}")
        lines.append(f"  Vertical bars: {chart.get('vertical_bars', 0)}")
        lines.append(f"  Circular elements: {chart.get('circular_elements', 0)}")
        lines.append("")

    diag = data.get("diagram", {})
    if diag:
        lines.append("Diagram Analysis:")
        lines.append(f"  Type: {diag.get('diagram_type', '?')}")
        lines.append(f"  Shapes: {diag.get('total_shapes', 0)} ({diag.get('shapes', {})})")
        lines.append(f"  Connections: {diag.get('connections', 0)}")
        lines.append("")

    info = data.get("infographic", {})
    if info:
        lines.append("Infographic Analysis:")
        lines.append(f"  Sections: {info.get('sections_detected', '?')}")
        lines.append(f"  Layout: {info.get('layout', '?')}")
        lines.append(f"  Text ratio: {info.get('text_ratio', '?')}")
        lines.append(f"  Color ratio: {info.get('color_ratio', '?')}")
        lines.append("")

    return "\n".join(lines)

# ── CLI Entry Point ────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Local Vision Toolkit — Analyze images without model vision capabilities",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Actions:
  ocr       Extract text from image (with OpenCV preprocessing)
  structure Detect layout blocks, tables, charts
  metadata  Colors, resolution, aspect ratio, complexity
  chart     Analyze charts, graphs, data visualizations
  diagram   Detect flowcharts, org charts, architecture diagrams
  infographic Extract sections and visual hierarchy from infographics
  full      Full analysis: all of the above + natural language description

Examples:
  python3 vision_tool.py screenshot.png --action ocr
  python3 vision_tool.py chart.png --action chart
  python3 vision_tool.py diagram.png --action diagram
  python3 vision_tool.py infographic.png --action infographic
  python3 vision_tool.py screenshot.png --action full --format json
        """
    )

    parser.add_argument("filepath", help="Path to the image file")
    parser.add_argument("--action", choices=["ocr", "structure", "metadata", "chart", "diagram", "infographic", "full"],
                       default="full", help="Analysis action (default: full)")
    parser.add_argument("--format", choices=["text", "json"], default="text",
                       help="Output format (default: text)")
    parser.add_argument("--lang", default="spa+eng",
                       help="Tesseract language code (default: spa+eng)")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Show debug info")

    args = parser.parse_args()

    try:
        results = analyze_image(
            args.filepath,
            action=args.action,
            output_format=args.format,
            lang=args.lang,
        )
        output = format_output(results, args.format)
        print(output)

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            traceback.print_exc()
        sys.exit(3)

if __name__ == "__main__":
    main()
