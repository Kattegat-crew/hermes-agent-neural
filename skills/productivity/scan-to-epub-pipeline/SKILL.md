---
name: scan-to-epub-pipeline
description: "Use when converting a scanned PDF to EPUB or OCR PDF"
tags: [ocr, pdf, epub, escaneo, scan, ocrmypdf, docker, pymupdf]
---

# Scanned PDF → Searchable PDF + EPUB

Converts 100%-image scanned PDFs into (a) a searchable PDF/A with a real text layer and (b) an EPUB 3 with reflowable text and a navigable TOC. Verified end-to-end on an 83-page Spanish book inside the Hermes Docker container (no apt, no sudo, no tesseract, no calibre, marker-pdf skipped to avoid ~5GB).

Triggers: "libro escaneado a epub", "pdf escaneado a seleccionable", "scanned PDF to EPUB", "OCR de un PDF sin capa de texto", conversiones estilo Stirling/Paperless.

## Step 0 — Diagnose the PDF first (30 seconds, decides everything)

```python
import pymupdf
d = pymupdf.open(path)
chars = sum(len(p.get_text().strip()) for p in d)
imgs  = sum(len(p.get_images()) for p in d)
# chars==0 and imgs>0 → image-only scan → needs --force-ocr OCR
```

pymupdf lives in `/opt/data/.venv/bin/python` (check other venvs with a one-liner import before assuming it's missing). If the PDF already has a text layer, skip OCR and go straight to extraction/EPUB.

## Step 1 — OCR via sibling container (the bind-mount trap)

If the container has `/run/docker.sock` mounted (group `hostdocker`), run OCRmyPDF as a sibling container. Image with `spa`+`eng` built in: `jbarlow83/ocrmypdf:latest` (confirm languages: `docker run --rm --entrypoint tesseract jbarlow83/ocrmypdf:latest --list-langs`).

**CRITICAL PITFALL: never use `-v` bind mounts from inside the Hermes container.** Paths like `/opt/data/workspace/...` are the *container's* overlay path — the docker daemon resolves them on the HOST filesystem, so the mount comes up empty or wrong (`InputFileError: File not found /data/scan.pdf` even though the file clearly exists; `ls -la /data` inside shows an empty dir). The pattern that works is `docker cp` in, `docker cp` out:

```bash
docker create --name ocr -u 0:0 --entrypoint sleep jbarlow83/ocrmypdf:latest infinity
docker start ocr
docker cp scan.pdf ocr:/opt/scan.pdf
docker exec ocr bash -c "cd /opt && ocrmypdf scan.pdf out.pdf -l spa --force-ocr --jobs 3"
docker cp ocr:/opt/out.pdf ./searchable.pdf
docker rm -f ocr
```

Gotchas observed:
- `--force-ocr` is REQUIRED for image-only scans; without it OCRmyPDF thinks there's nothing to do.
- The image entrypoint IS ocrmypdf — `docker create ... jbarlow83/ocrmypdf sleep` fails with argparse errors. Override with `--entrypoint sleep`.
- `--clean` is boolean, takes no value (`--clean 0` → "unrecognized arguments", exit 2).
- `-u 0:0` avoids `OutputFileAccessError` from the image's default user; `-u 10000` may still hit output permission errors on cp'd files.
- Re-run inside the SAME long-lived container if a run dies on a bad flag — the input stays at `/opt/scan.pdf`.
- Speed: ~2-4 min CPU for 83 pages @ `--jobs 3` (2000×1600px scans). Run long jobs with `terminal(background=true)` and poll; don't block.
- Clean text for downstream parsing: rerun with `--sidecar texto.txt`, or just `get_text()` on the searchable PDF with pymupdf (instant, preferred).

**Verify the OCR before claiming success**: reopen output with pymupdf, count chars (83 Spanish pages ≈ 285k), print a sample mid-book page. OCR errata run ~1/500 words (ligature confusions, "capital"→"canar") — tell the user it's reader-quality, not citation-quality.

## Step 2 — Build the EPUB without calibre

`ebook-convert`/calibre are typically absent; do not try to install them. Build EPUB 3 directly with stdlib `zipfile` from pymupdf block text. Full working script: `scripts/build_epub.py` (copy, adjust SRC/chapter heuristic). Key mechanics:

- `page.get_text('blocks', sort=True)` for reading-order blocks; drop standalone `\d{1,3}` blocks (running headers/page numbers).
- Typography cleanup before paragraph joins: `re.sub(r'-\n(?=[a-záéíóúñü])','',s)` (de-hyphenate) then single newlines → spaces.
- Chapter detection heuristic for books: ALL-CAPS short lines followed by a real body paragraph (uppercase regex, len<140, next block >60 chars with lowercase). Expect false positives from OCR'd headers — print the detected TOC and eyeball it before shipping. Title-case the headings for display.
- EPUB 3 minimum: `mimetype` entry FIRST and ZIP_STORED (`compress_type=zipfile.ZIP_STORED`), `META-INF/container.xml`, `OEBPS/content.opf` (with `<meta property="dcterms:modified">`), `OEBPS/nav.xhtml` with `epub:type="toc"`, one xhtml per chapter, `xml:lang="es"`.
- Validate: `zipfile.testzip()` is None, decode one chapter and strip tags to confirm prose reads correctly.

## Step 3 — Deliver

Both artifacts go to the user as attachments (MEDIA:), never paths: searchable PDF + EPUB, with an honest note about OCR errata rate and (if applicable) that Stirling/Paperless were not involved — same engines underneath.

## Pitfalls recap

| Symptom | Cause | Fix |
|---|---|---|
| `InputFileError`/empty `/data` despite bind mount | daemon resolves path on host | `docker cp` pattern |
| argparse usage dump from `docker create ... sleep` | entrypoint is ocrmypdf | `--entrypoint sleep` |
| `OutputFileAccessError` writing to mounted dir | container user lacks perms | `-u 0:0` + `docker cp` out |
| "unrecognized arguments: 0" | `--clean` is boolean | drop the value |
| output PDF has 0 text chars | ran without `--force-ocr` on image-only scan | add flag |

Related: `ocr-and-documents` (bundled) covers pymupdf/marker-pdf general extraction; this skill owns the scanned-book → searchable-PDF → EPUB class with the docker-sibling workaround for locked-down containers.
