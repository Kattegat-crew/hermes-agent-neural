#!/usr/bin/env python3
"""Descarga TODAS las imágenes generadas en un share público de ChatGPT.

Uso: PLAYWRIGHT_BROWSERS_PATH=/opt/data/home/.cache/ms-playwright \
     /opt/data/.venv-pw/bin/python fetch_share_images.py <share_url> <out_dir>

- Scroll progresivo por toda la conversación (JS scrollBy + PageDown) para forzar lazy-load.
- Recolecta {src -> alt} de todos los <img> con /files/<uuid>/raw (ignora sprites del shell).
- Descarga cada src con el contexto del navegador (ctx.request.get) y guarda index.json.
El `alt` de cada imagen es el título real de la generación: 'Generated image: <título>'.
"""
import json
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

share = sys.argv[1]
out = Path(sys.argv[2] if len(sys.argv) > 2 else "images")
out.mkdir(parents=True, exist_ok=True)

seen = {}
JS_COLLECT = """(() => [...document.querySelectorAll('img')].map(i => ({
    src: i.currentSrc || i.src, alt: i.alt || '', w: i.naturalWidth, h: i.naturalHeight
})).filter(o => o.src && o.src.startsWith('http')))()"""
REAL_IMG = re.compile(r"/files/[0-9a-f\-]+/raw")


def collect(page):
    try:
        for o in page.evaluate(JS_COLLECT):
            if not REAL_IMG.search(o["src"]):
                continue
            key = o["src"].split("?")[0]
            if key not in seen or (not seen[key]["alt"] and o["alt"]):
                seen[key] = {"alt": o["alt"], "url": o["src"]}
    except Exception as e:  # noqa: BLE001
        print("collect fail:", e)


with sync_playwright() as p:
    browser = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
    ctx = browser.new_context(viewport={"width": 1100, "height": 1400})
    page = ctx.new_page()
    page.goto(share, wait_until="domcontentloaded", timeout=90000)
    page.wait_for_timeout(6000)
    page.keyboard.press("End")
    page.wait_for_timeout(1500)
    page.keyboard.press("Home")
    page.wait_for_timeout(1000)

    last_y, stuck, guard = -1, 0, 0
    while True:
        guard += 1
        page.evaluate("window.scrollBy(0, 700)")
        page.wait_for_timeout(450)
        collect(page)
        st = page.evaluate("({y: window.scrollY, h: document.body.scrollHeight, inner: window.innerHeight})")
        if st["y"] == last_y:
            stuck += 1
            page.keyboard.press("PageDown")
            page.wait_for_timeout(400)
            if stuck > 4:
                break
        else:
            stuck = 0
        last_y = st["y"]
        if guard > 260:
            break
    page.wait_for_timeout(3000)
    collect(page)
    print(f"imágenes únicas detectadas: {len(seen)}")

    meta = []
    for i, (key, info) in enumerate(seen.items()):
        try:
            data = ctx.request.get(info["url"], timeout=60000).body()
        except Exception as e:  # noqa: BLE001
            print("dl fail", key, e)
            continue
        if len(data) < 5000:
            continue
        ext = ".png" if data[:8] == b"\x89PNG\r\n\x1a\n" else ".jpg"
        f = out / f"img-{i:02d}{ext}"
        f.write_bytes(data)
        meta.append({"file": f.name, "bytes": len(data), "alt": info["alt"], "source_url": key})
        print(f"  [{i:02d}] {len(data):>9,}B  {info['alt'][:90]}")

    (out / "index.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))
    print(f"RESULT: {len(meta)} imágenes guardadas en {out}")
    browser.close()
