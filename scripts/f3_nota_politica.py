#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Anexa a la política la nota del borde D1/D2 del gate y la integración del lint."""
from pathlib import Path

P = Path('/root/hermes-agent-legacy-docker/docs/skills/POLITICA-ARBOL-CANONICO.md')
NOTA = '''
## Notas de borde verificadas (23-sep-2026)

### Gate de autoskills · D1 vs D2 en el caso homónimo

Cuando una skill absorbida tiene EXACTAMENTE el mismo nombre que su paraguas
—hoy ocurre en `core/video-reel-pipeline`, que conserva
`references/video-reel-pipeline.md`—, el nombre intentado resuelve primero por
D1 (caso de `references/`) y no por D2 (clase de `core/`). El veredicto sigue
siendo **bloquear**, con la ruta exacta en el mensaje, y la instrucción de
enriquecer el fichero existente en lugar de crear; lo único que cambia es el
texto (dice OMITIR donde el caso de clase diría EDITAR). Se deja documentado en
vez de corregir el hook en caliente: tocar el script invalida la aprobación del
allowlist en los 12 perfiles y exige un ciclo de re-aprobación con reinicio.

### Lint de catálogo dentro de la aduana (R5 / R7)

`verify_skills.py` ejecuta ahora `lint_skills_catalog.py` (fuente única del
criterio) y publica:

- **R5** como MÉTRICA: cuántas descripciones cierran su primera frase fuera de
  la ventana de 57 caracteres (línea base medida el 23-sep-2026: 321). No
  bloquea; el objetivo es que la cifra baje.
- **R7** como REGLA BLOQUEANTE para grupos NUEVOS: los grupos de nombres
  equivalentes conocidos al integrar la regla quedan en
  `data/state/nombres_equivalentes_baseline.json` y se reportan; cualquier par
  nuevo que aparezca bloquea la aduana. Así el semáforo es útil (verde hoy) y
  no se normaliza el defecto que R7 existe para evitar.
'''
t = P.read_text(encoding='utf-8')
if 'Notas de borde verificadas' in t:
    print('ya estaba')
else:
    P.write_text(t.rstrip('\n') + '\n' + NOTA, encoding='utf-8')
    print('nota anexada a la política (%d chars)' % len(NOTA))
