---
name: local-vision-toolkit
description: >-
  Use when a model without vision must read an image or chart Autonomous local computer vision toolkit — OCR, image analysis, chart detection, infographic extraction, screenshot interpretation, and diagram understanding. Runs 100% locally with Python (OpenCV, Tesseract, Pillow, scikit-image). Does NOT depend on the connected model having vision capabilities. Use when the user shares an image, screenshot, diagram, chart, infographic, or any visual content that needs analysis — even if the model can't see. hermes: tags: [Vision, OCR, Images, Charts, Infographics, Diagrams, Local, AI] category: vision related_skills: [document-reader, brain-knowledge-base, knowledge-absorption, skill-integration] commands: [python3] python_packages: system_packages:
version: 1.0.0
author: hermes
license: MIT
metadata:
prerequisites:
    - Pillow
    - pytesseract
    - opencv-python
    - scikit-image
    - numpy
    - matplotlib (optional)
    - tesseract-ocr (with lang=spa for Spanish support)
---

# Local Vision Toolkit

A self-contained computer vision toolkit that lets ANY Hermes agent "see" and interpret images, screenshots, diagrams, charts, and infographics — **without needing a model with vision capabilities**.

All processing happens locally via Python scripts. The agent receives structured text descriptions, not raw images.

## Why This Exists

Most LLMs (including qwen3.6) cannot see images. When users share screenshots, diagrams, or charts, you need a way to extract their content programmatically. This toolkit bridges that gap — it's the agent's "eyes" that always work, regardless of model.

## Architecture

```
User sends image/screenshot
        |
        v
+---------------------+
|  vision_tool.py     |  <- Runs locally, no model needed
|  (Python + OpenCV)  |
+---------+-----------+
          |
          +-- OCR -> Extract text from image
          +-- Structure -> Detect layout blocks, tables, charts
          +-- Metadata -> Colors, resolution, dominant elements
          +-- Description -> Natural language summary
          |
          v
    Structured JSON/Text
    (sent to model as context)
```

## Quick Start

```bash
# Basic OCR (extract all text from image)
python3 SKILL_DIR/scripts/vision_tool.py screenshot.png --action ocr

# Full analysis (text + structure + metadata + description)
python3 SKILL_DIR/scripts/vision_tool.py screenshot.png --action full

# Chart analysis (detect chart type, bars, circles)
python3 SKILL_DIR/scripts/vision_tool.py chart.png --action chart

# Diagram detection (flowcharts, org charts, architecture)
python3 SKILL_DIR/scripts/vision_tool.py diagram.png --action diagram

# Infographic extraction (sections, layout, hierarchy)
python3 SKILL_DIR/scripts/vision_tool.py infographic.png --action infographic

# JSON output for programmatic consumption
python3 SKILL_DIR/scripts/vision_tool.py screenshot.png --action full --format json

# Spanish language OCR
python3 SKILL_DIR/scripts/vision_tool.py screenshot.png --action ocr --lang spa
```

## Actions

| Action | What it does | When to use |
|--------|-------------|-------------|
| `ocr` | Extract all text from image with OpenCV preprocessing | Screenshots, scanned images, photos with text |
| `structure` | Detect layout blocks, tables, charts, diagrams | Complex layouts, dashboards, reports |
| `metadata` | Colors, resolution, aspect ratio, complexity | Quick image assessment |
| `chart` | Analyze charts/graphs — detect type, bars, circles | Bar charts, pie charts, line graphs |
| `diagram` | Detect flowcharts, org charts, architecture diagrams | Technical diagrams, process flows |
| `infographic` | Extract sections, visual hierarchy, text/color ratio | Marketing infographics, educational visuals |
| `full` | Run ALL analyses + generate natural language description | When you need everything at once |

## Integration with document-reader

The `document-reader` skill handles PDFs, Word, Excel, and scanned documents. The `local-vision-toolkit` complements it by handling **image files directly** and providing **deeper visual analysis** (chart type, diagram structure, infographic layout).

**Workflow:**
1. User sends an image file (PNG, JPG, etc.)
2. Run `vision_tool.py --action full` on the image
3. Read the structured output (text or JSON)
4. Use the extracted text/description as context for further processing
5. Save to Brain Wiki or Notion using `knowledge-absorption` patterns

**Example integration:**
```bash
# When user sends a screenshot:
python3 SKILL_DIR/scripts/vision_tool.py /tmp/screenshot.png --action full
# Returns: OCR text + chart detection + structure + description
# Use the description as context for answering the user
```

## Integration with knowledge-absorption

When absorbing visual content into the Brain Wiki:

1. Run `vision_tool.py` on the image
2. Extract the description and OCR text
3. Create a Brain Wiki entry with frontmatter:

```markdown
---
title: {description_summary}
type: image_analysis
tags: [vision, ocr, imagenes, capturas, graficos, tesseract, opencv, local]
created: YYYY-MM-DD
source: file://{filepath}
---

# {Title}

## Description
{natural language description from toolkit}

## OCR Text
{extracted text if any}

## Analysis
{structured analysis results}
```

## Typical Use Cases

**User shares a screenshot of a dashboard:**
```bash
python3 SKILL_DIR/scripts/vision_tool.py dashboard.png --action full
# Returns: chart types, text, layout structure, description
# "Image (1920x1080), wide aspect ratio, high complexity. Chart type: bar_chart. Text: 'Q4 Revenue: $1.2M'"
```

**User shares a diagram/architecture image:**
```bash
python3 SKILL_DIR/scripts/vision_tool.py architecture.png --action diagram
# Returns: diagram type, shapes, connections, complexity
# "flowchart (12 shapes, 18 connections)"
```

**User shares a chart/graph:**
```bash
python3 SKILL_DIR/scripts/vision_tool.py chart.png --action chart
# Returns: chart type, bar counts, circular elements
# "bar_chart (8 vertical bars, 0 circular elements)"
```

**User shares an infographic:**
```bash
python3 SKILL_DIR/scripts/vision_tool.py infographic.png --action infographic
# Returns: sections, layout, text/color ratio
# "Infographic with 5 sections, vertical_sections layout"
```

**User shares a photo with text (Spanish):**
```bash
python3 SKILL_DIR/scripts/vision_tool.py foto.jpg --action ocr --lang spa
# Returns: extracted Spanish text with confidence score
```

## Output Formats

| Format | Description |
|--------|-------------|
| `text` | Human-readable with sections and labels |
| `json` | Structured JSON with all fields — machine parseable |

## Error Handling

- **File not found**: Check the path and try again.
- **Image not supported**: Try converting to PNG or JPG first.
- **Library missing**: Install the required package (`pip install <package>`).
- **OCR returns empty**: Image may not contain text. Try `--action structure` or `--action metadata` instead.
- **Low confidence OCR**: Image quality may be poor. Try increasing resolution or improving contrast.

## Tips

- Use `--action full` when you need everything — it's the most versatile.
- Use `--format json` when you need to programmatically process the output.
- Use `--action ocr` when you just need text extraction (fastest).
- Use `--action chart` for data visualizations — it detects bar charts, pie charts, etc.
- Use `--action diagram` for technical diagrams — it detects flowcharts, org charts, architecture diagrams.
- Use `--action infographic` for marketing/educational visuals — it extracts sections and layout.
- For **scanned documents**, prefer `document-reader` skill (it handles PDFs better).
- For **images sent directly** (screenshots, photos, diagrams), use `local-vision-toolkit`.
- The toolkit works with ANY model — even models without vision capabilities.
- All processing is local — no API calls, no external services, no model dependency.

## Support Files

| File | Purpose |
|------|---------|
| `scripts/vision_tool.py` | Main analysis script with all actions |
| `scripts/verify_vision.sh` | Quick verification: checks all deps, runs test analysis |
| `references/vision-workflow.md` | Integration patterns with document-reader and knowledge-absorption |

## Pitfalls

- **Tesseract language packs are system-level**: `pip install pytesseract` only installs the Python wrapper. Tesseract itself and language data (`tesseract-ocr-spa`) must be installed via system package manager.
- **Image quality matters**: Low resolution, blur, or poor contrast will reduce OCR accuracy. The toolkit applies OpenCV preprocessing automatically, but very poor images may still fail.
- **OpenCV is optional but recommended**: `_preprocess_image()` returns the image unchanged if `cv2` is not installed. OCR and chart detection still work but with lower accuracy.
- **Large images slow down analysis**: For very large images (>4000px), consider resizing before analysis.
- **Chart analysis is heuristic-based**: It detects likely chart types but cannot extract exact data values from charts. For precise data extraction, use `document-reader` on the source document.
- **Diagram detection identifies structure, not meaning**: It can detect that something is a flowchart with 12 shapes, but cannot interpret what the flowchart represents. Combine with OCR text for full understanding.
- **Infographic analysis extracts structure, not content**: It identifies sections and layout but the actual text content comes from the OCR action.
