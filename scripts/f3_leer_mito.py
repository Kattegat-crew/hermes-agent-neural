#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Muestra las líneas exactas del mito del curador en las memorias de la flota."""
from pathlib import Path

objetivos = [
    ('/root/hermes-agent-legacy-docker/data/profiles/bragi/memories/MEMORY.md', [11]),
    ('/root/hermes-agent-legacy-docker/data/memories/MEMORY.md', [132, 154, 199, 213]),
]
for ruta, lineas in objetivos:
    p = Path(ruta)
    if not p.is_file():
        print('NO EXISTE', ruta)
        continue
    txt = p.read_text(encoding='utf-8').splitlines()
    print('=== %s (%d lineas) ===' % (ruta, len(txt)))
    for n in lineas:
        if 1 <= n <= len(txt):
            print('  [%d] %s' % (n, txt[n - 1][:400]))
        else:
            print('  [%d] (fuera de rango)' % n)
    print()
