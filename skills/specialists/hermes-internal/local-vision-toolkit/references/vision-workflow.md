# Integration Patterns: Local Vision Toolkit

## How the toolkit fits into the Hermes ecosystem

```
                    +------------------+
                    |  User sends image|
                    +--------+---------+
                             |
                    +--------v---------+
                    |  vision_tool.py  |  <--- NEW: local vision
                    |  (100% local)    |      runs without model vision
                    +--------+---------+
                             |
                    +--------v---------+
                    |  Structured text |  <--- model consumes text, not image
                    +--------+---------+
                             |
              +--------------+--------------+
              |                             |
      +-------v--------+          +----------v-------+
      | document-reader|          | knowledge-absorp |
      | (PDFs, docs)   |          | (Brain Wiki/Notion)|
      +----------------+          +------------------+
```

## Pattern 1: User sends a screenshot -> answer question

```
# User: "de que trata esta captura de pantalla?"
# Ragnar loads local-vision-toolkit skill

python3 SKILL_DIR/scripts/vision_tool.py /tmp/screenshot.png --action full
# Returns structured description + OCR text

# Ragnar uses the description as context to answer the user
# NO need for a model with vision capabilities
```

## Pattern 2: User shares an image -> absorb into Brain Wiki

```
# User: "guarda esto en el brain wiki"
# (sends an infographic image)

# 1. Run full analysis
python3 SKILL_DIR/scripts/vision_tool.py infographic.png --action full --format json

# 2. Extract results
description = result["description"]
ocr_text = result["ocr"]["text"]
info = result["infographic"]

# 3. Create Brain Wiki entry
# Use brain-knowledge-base skill conventions
cat > /opt/data/brain/entities/image_infographic_001.md <<EOF
---
title: {info.get('layout', 'infographic')} analysis
type: image_analysis
tags: [image, infographic, {detected_sections}]
created: $(date +%Y-%m-%d)
source: local
---

# {description}

## Extracted Text
{ocr_text}

## Layout
{json.dumps(info, indent=2, ensure_ascii=False)}
EOF

# 4. Link from index
# Use brain-knowledge-base skill to update index
```

## Pattern 3: User sends chart/graph -> extract data

```
# User: "cuales son los datos de este grafico?"

python3 SKILL_DIR/scripts/vision_tool.py chart.png --action chart --format json
# Returns chart type, bar counts, elements

python3 SKILL_DIR/scripts/vision_tool.py chart.png --action ocr --format json
# Returns the axis labels, titles, data labels

# Combine both results to provide context-aware answer
# Note: cannot extract precise data values from charts
# but can identify chart type and read axis labels via OCR
```

## Pattern 4: User sends diagram -> understand architecture

```
# User: "explicame este diagrama de arquitectura"

python3 SKILL_DIR/scripts/vision_tool.py architecture.png --action diagram --format json
# Returns: diagram_type, shapes count, connections, complexity

python3 SKILL_DIR/scripts/vision_tool.py architecture.png --action ocr --format json
# Returns: text labels inside shapes

# Combine: "This is a {diagram_type} with {shapes} shapes and {connections} connections.
# The labels are: {ocr_text}"
```

## Pattern 5: User sends scanned document -> OCR text

```
# User: "extrae el texto de esta foto"

python3 SKILL_DIR/scripts/vision_tool.py foto.jpg --action ocr --lang spa
# Returns extracted Spanish text with confidence

# Or for higher accuracy on multi-page scanned docs,
# prefer document-reader skill with --format pages
```

## Decision Flow: Which tool to use?

| User sends... | Use this tool | Reason |
|---------------|--------------|--------|
| Screenshot (PNG/JPG) | local-vision-toolkit | Direct image analysis |
| Photo with text | local-vision-toolkit | OCR on image files |
| Diagram/architecture | local-vision-toolkit | Shape/connection detection |
| Chart/graph | local-vision-toolkit | Chart type detection |
| Infographic | local-vision-toolkit | Section/layout extraction |
| PDF (scanned) | document-reader | Better PDF handling |
| PDF (text-based) | document-reader | Built-in PDF text extraction |
| Word/Excel/PowerPoint | document-reader | Native format support |
| Image + want Brain Wiki | local-vision-toolkit + knowledge-absorption | Extract + absorb |
| Image + want answer | local-vision-toolkit only | Just need description |

## Important Limitations

### Cannot extract precise data from charts
The chart analysis detects types and elements (bars, circles) but cannot read exact data values from chart elements. It CAN read axis labels and titles via OCR.

### Diagram detection is structural, not semantic
It identifies that something is a flowchart with 12 shapes and 18 connections, but cannot interpret what the flowchart means. OCR text inside shapes provides context.

### Infographic analysis extracts structure, not content
It identifies sections and layout patterns, but actual text content comes from the OCR action.

### Image quality matters
Low resolution, blur, or poor contrast will reduce OCR accuracy. The toolkit applies OpenCV preprocessing automatically (grayscale, denoising, adaptive threshold), but very poor images may still fail.

### Tesseract accuracy varies
Accuracy depends on:
- Image quality (resolution, contrast)
- Font style (serif vs sans-serif, bold vs regular)
- Language (spa+eng default works well for Spanish/English mixed)
- Text size (very small text < 8pt is hard to read)

## Tips for Best Results

1. **Always use `--action full`** unless you specifically need one analysis -- it runs everything and gives a natural language description.

2. **Use `--format json`** when processing images programmatically (e.g., saving to Brain Wiki, extracting data for reports).

3. **Use `--lang spa`** for Spanish-only text, `--lang eng` for English-only, `--lang spa+eng` for mixed.

4. **For very large images** (>4000px wide), consider resizing first:
   ```bash
   python3 -c "from PIL import Image; Image.open('big.png').resize((1920, 1080)).save('small.png')"
   ```

5. **Combine chart + OCR analysis** for chart interpretation:
   ```bash
   python3 SKILL_DIR/scripts/vision_tool.py chart.png --action chart --format json
   python3 SKILL_DIR/scripts/vision_tool.py chart.png --action ocr --format json
   ```

6. **Use document-reader for PDFs**, local-vision-toolkit for image files. They share the same OCR engine (Tesseract) but document-reader handles PDF-specific concerns better (multi-page, embedded fonts, etc.).
