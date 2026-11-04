#!/usr/bin/env python3
"""Build a reflowable EPUB 3 from a searchable (OCR'd) PDF — no calibre needed.

Usage:  /opt/data/.venv/bin/python build_epub.py <searchable.pdf> <out.epub> --lang es --author "Karl Marx" --title "El arma de la crítica"

Verified on an 83-page Spanish book (OCRmyPDF output). Adjust HEAD_RE /
is_head() heuristics per book layout. Requires pymupdf (in /opt/data/.venv).
"""
import pymupdf, re, zipfile, html, os, sys, argparse

def clean_para(s):
    s = re.sub(r'-\n(?=[a-záéíóúñü])', '', s)   # de-hyphenate line-end breaks
    s = re.sub(r'\n', ' ', s)                    # soft line breaks -> spaces
    s = re.sub(r' {2,}', ' ', s)
    s = re.sub(r'\s+([,;:.¿!?)\]])', r'\1', s)   # fix OCR spacing before punctuation
    return s.strip()

def collect_blocks(doc):
    paras = []
    for page in doc:
        for b in page.get_text('blocks', sort=True):
            txt = b[4].strip()
            if not txt or re.fullmatch(r'\d{1,3}', txt):
                continue                          # drop running page numbers
            paras.append(txt)
    return paras

UPPER = re.compile(r'^[A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ0-9 ,.;:\-¿()&\[\]¡!]{5,}$')

def is_head(c, nxt):
    """ALL-CAPS short line followed by real prose = section title."""
    flat = c.replace('\n', ' ').strip()
    if not UPPER.match(flat) or len(flat) > 140 or flat.startswith('['):
        return False
    return len(nxt) > 60 and any(ch.islower() for ch in nxt)

def split_chapters(clean):
    chapters, cur = [], {'title': 'Inicio', 'paras': []}
    for i, c in enumerate(clean):
        nxt = clean[i + 1] if i + 1 < len(clean) else ''
        if is_head(c, nxt):
            if cur['paras']:
                chapters.append(cur)
            cur = {'title': re.sub(r'\s+', ' ', c).title(), 'paras': []}
            continue
        cur['paras'].append(c)
    if cur['paras']:
        chapters.append(cur)
    return chapters

def xhtml(title, body_paras, cid):
    out = []
    for p in body_paras:
        esc = html.escape(p)
        out.append(f'<h2>{esc}</h2>' if (UPPER.match(p) and len(p) < 140) else f'<p>{esc}</p>')
    return ('<?xml version="1.0" encoding="utf-8"?>\n'
            '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="es">\n'
            '<head><meta charset="utf-8"/><title>' + html.escape(title) + '</title>'
            '<link rel="stylesheet" type="text/css" href="style.css"/></head>\n'
            '<body><section epub:type="chapter" id="' + cid + '"><h1>' + html.escape(title) + '</h1>\n'
            + '\n'.join(out) + '\n</section></body></html>')

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('pdf'); ap.add_argument('epub')
    ap.add_argument('--title', default=os.path.splitext(os.path.basename(os.path.abspath(ap.parse_args().epub)))[0])
    a = ap.parse_args()
    doc = pymupdf.open(a.pdf)
    clean = [c for c in (clean_para(p) for p in collect_blocks(doc)) if c]
    chapters = split_chapters(clean)
    print('secciones detectadas:', len(chapters))
    for ch in chapters:
        print('  -', ch['title'][:70], f"({len(ch['paras'])} párr.)")  # EYEBALL THIS TOC before shipping

    with zipfile.ZipFile(a.epub, 'w', zipfile.ZIP_DEFLATED) as z:
        # mimetype MUST be first entry and STORED
        z.writestr(zipfile.ZipInfo('mimetype'), 'application/epub+zip', compress_type=zipfile.ZIP_STORED)
        z.writestr('META-INF/container.xml', '''<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
<rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles>
</container>''')
        z.writestr('OEBPS/style.css',
                   'body{font-family:serif;line-height:1.5;margin:2em}'
                   'p{text-align:justify;text-indent:1.2em;margin:0.4em 0}'
                   'h1{font-size:1.4em;margin:1.5em 0}h2{font-size:1.15em;margin:1.2em 0 0.5em}')
        manifest, spine = [], []
        for idx, ch in enumerate(chapters):
            cid = f'ch{idx:02d}'
            z.writestr(f'OEBPS/{cid}.xhtml', xhtml(ch['title'], ch['paras'], cid))
            manifest.append(f'<item id="{cid}" href="{cid}.xhtml" media-type="application/xhtml+xml"/>')
            spine.append(f'<itemref idref="{cid}"/>')
        z.writestr('OEBPS/content.opf', f'''<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bid" xml:lang="es">
<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
<dc:identifier id="bid">scan-epub-{os.path.getmtime(a.pdf):.0f}</dc:identifier>
<dc:title>{html.escape(a.title)}</dc:title>
<dc:language>es</dc:language>
<meta property="dcterms:modified">2020-01-01T00:00:00Z</meta>
</metadata>
<manifest><item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
<item id="css" href="style.css" media-type="text/css"/>
{''.join(manifest)}</manifest>
<spine>{''.join(spine)}</spine>
</package>''')
        toc = ''.join(f'<li><a href="ch{i:02d}.xhtml">{html.escape(c["title"])}</a></li>'
                      for i, c in enumerate(chapters))
        z.writestr('OEBPS/nav.xhtml', f'''<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="es">
<head><title>Índice</title></head><body><nav epub:type="toc"><ol>{toc}</ol></nav></body></html>''')

    # validate
    z = zipfile.ZipFile(a.epub)
    assert z.testzip() is None
    sample = re.sub(r'<[^>]+>', '', z.read('OEBPS/ch01.xhtml').decode('utf-8'))
    print('OK', a.epub, os.path.getsize(a.epub), 'bytes — muestra:', sample[:120].strip())

if __name__ == '__main__':
    main()
