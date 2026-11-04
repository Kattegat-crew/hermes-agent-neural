#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
guard_autoskill_create.py — gate de decision de autoskills (hook pre_tool_call)
===============================================================================

Intercepta `skill_manage(action="create")` ANTES de que escriba nada. Decide con
DOS capas separadas a proposito:

  CAPA DURA (bloquea, determinista, 100% reproducible)
    D1  el nombre coincide con un `references/<caso>.md` existente  -> OMITIR
    D2  el nombre coincide con una clase de `core/`                 -> EDITAR
    D3  el nombre es un caso casi identico (plural/guion/guion_bajo) de una clase
        o de un reference ya existentes, en `core/` o en todo el catalogo -> EDITAR

  CAPA DE CONSULTA (no bloquea: orienta)
    El gate adjunta el indice del corpus de clase (los 28 registros de `core/` con
    su disparador y sus references) para que la decision semantica la tome el agente
    con el material delante, y deja en el ledger los 3 candidatos mas cercanos.

POR QUE LA CAPA LEXICA NO DECIDE
  Medido el 23-sep-2026 sobre este mismo corpus, con coseno TF-IDF y con cobertura
  IDF, en dos granularidades (cuerpos completos y registros cortos densos):
  un borrador AJENO (calibracion de un telescopio) puntua 0,252 y un borrador que
  SI pertenece a meta-ads-ops puntua 0,243. La similitud lexica NO separa las
  clases: no puede ser el arbitro. Los umbrales se reservan para la metrica oficial
  de solapamiento del catalogo (F6), donde se comparan documentos comparables.

Destino exacto de lo absorbido: skills/core/<paraguas>/references/<caso>.md
"""
import json
import os
import re
import sys
import time
from pathlib import Path

# F6 nativo (02-oct-2026): canon de skills en /opt/hermes-agent/skills (era /opt/hermes/skills, docker)
SKILLS = Path(os.environ.get('HERMES_SKILLS_ROOT', '/opt/hermes-agent/skills'))
CORE = SKILLS / 'core'
HOOK_DIR = Path(__file__).resolve().parent
DIRS_ESCRITURA = [Path('/opt/data/state'), Path('/tmp')]


def dir_datos():
    for d in DIRS_ESCRITURA:
        try:
            d.mkdir(parents=True, exist_ok=True)
            p = d / '.gate-probe'
            p.write_text('x')
            p.unlink()
            return d
        except Exception:
            continue
    return Path('/tmp')


def log(reg):
    try:
        with (dir_datos() / 'autoskill_gate.jsonl').open('a', encoding='utf-8') as fh:
            fh.write(json.dumps(reg, ensure_ascii=False) + '\n')
    except Exception:
        pass


def bloquear(msg):
    print(json.dumps({'action': 'block', 'message': msg}, ensure_ascii=False))
    sys.exit(2)


def leer(p, limite=800):
    try:
        return p.read_text(encoding='utf-8', errors='replace')[:limite]
    except Exception:
        return ''


def descripcion(txt):
    m = re.search(r'^description:\s*(.+)$', txt, re.M)
    if not m:
        return ''
    d = m.group(1).strip().strip('"\'')
    if not d or d in ('|', '>'):
        m2 = re.search(r'^description:\s*[|>]-?\s*\n((?:\s+.*\n)+)', txt, re.M)
        d = ' '.join(l.strip() for l in m2.group(1).splitlines()) if m2 else ''
    return d


def normaliza(n):
    n = re.sub(r'[-_\s]', '', n.lower())
    return n[:-1] if n.endswith('s') and not n.endswith('ss') else n


# ── corpus de clase ─────────────────────────────────────────────────────────
def corpus():
    """Devuelve (clases, nombre->destino) de core/."""
    clases, destinos = [], {}
    if not CORE.is_dir():
        return clases, destinos
    for d in sorted(CORE.iterdir()):
        if not (d.is_dir() and (d / 'SKILL.md').is_file()):
            continue
        sm = leer(d / 'SKILL.md', 1200)
        refs = []
        rd = d / 'references'
        if rd.is_dir():
            refs = sorted(r.name for r in rd.iterdir() if r.is_file() and r.suffix == '.md')
        clases.append({'clase': d.name, 'destino': 'skills/core/%s/SKILL.md' % d.name,
                       'disparador': descripcion(sm)[:120], 'references': refs})
        destinos[d.name] = 'skills/core/%s/SKILL.md' % d.name
        for r in refs:
            destinos[Path(r).stem] = 'skills/core/%s/references/%s' % (d.name, r)
    return clases, destinos


def indice_cacheado():
    cp = dir_datos() / 'autoskill_corpus.json'
    huella = 0.0
    try:
        for p in CORE.rglob('SKILL.md'):
            huella = max(huella, p.stat().st_mtime)
    except Exception:
        pass
    if cp.is_file():
        try:
            d = json.loads(cp.read_text(encoding='utf-8'))
            if d.get('huella') == round(huella, 3):
                return d['clases'], {k: v for k, v in d['destinos'].items()}, True
        except Exception:
            pass
    clases, destinos = corpus()
    try:
        cp.write_text(json.dumps({'huella': round(huella, 3), 'clases': clases,
                                  'destinos': destinos}, ensure_ascii=False), encoding='utf-8')
    except Exception:
        pass
    return clases, destinos, False


def nombres_catalogo():
    """Todo el catalogo por nombre normalizado (para D3).

    Incluye dos clases de objeto, porque las dos son duplicables:
      - directorios de skill (nombre de la skill)
      - ficheros de `references/` (nombre de cada caso absorbido)
    """
    idx = {}
    try:
        for sm in SKILLS.rglob('SKILL.md'):
            partes = sm.relative_to(SKILLS).parts
            if any(x.startswith('_') or x.startswith('.') for x in partes):
                continue
            if sm.parent.name in ('references', 'scripts', 'templates'):
                continue
            base = sm.parent
            idx.setdefault(normaliza(base.name), []).append(str(base.relative_to(SKILLS)))
            rd = base / 'references'
            if rd.is_dir():
                for r in rd.iterdir():
                    if r.is_file() and r.suffix in ('.md', '.txt'):
                        idx.setdefault(normaliza(r.stem), []).append(
                            str(r.relative_to(SKILLS)))
    except Exception:
        pass
    return idx


def override_vigente(nombre):
    f = dir_datos() / 'autoskill_override.json'
    if not f.is_file():
        return None
    try:
        d = json.loads(f.read_text(encoding='utf-8'))
    except Exception:
        return None
    if d.get('name') != nombre or time.time() > float(d.get('expira', 0)):
        return None
    try:
        f.unlink()
    except Exception:
        pass
    return d


def candidatos(nombre, contenido, clases, n=3):
    """Senal SOLO informativa: solape de tokens del nombre + descripcion con cada clase."""
    texto = '%s %s' % (nombre, descripcion(contenido))
    q = set(re.findall(r'[a-z]{4,}', texto.lower()))
    if not q:
        return []
    out = []
    for c in clases:
        texto_c = '%s %s %s' % (c['clase'], c['disparador'], ' '.join(c['references']))
        d = set(re.findall(r'[a-z]{4,}', texto_c.lower()))
        out.append((len(q & d) / max(len(q), 1), c['clase']))
    out.sort(reverse=True)
    return [(round(s, 3), c) for s, c in out[:n] if s > 0]


def digest(clases, limite=28):
    lineas = ['INDICE DE CLASE (core/) — consultar ANTES de crear una skill:',
              '  Si tu caso encaja en una clase, va ahi (references/<caso>.md). Si no encaja en',
              '  ninguna, es clase nueva y nace versionada.', '']
    for c in clases[:limite]:
        lineas.append('  - %s :: %s' % (c['clase'], c['disparador'] or '(sin descripcion)'))
        lineas.append('      destino: %s' % c['destino'])
    return '\n'.join(lineas)


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    if payload.get('tool_name') != 'skill_manage':
        return 0

    ti = payload.get('tool_input') or {}
    ops = ti.get('operations')
    if not isinstance(ops, list):
        ops = [ti] if ti.get('action') else []
    crea = [o for o in ops if isinstance(o, dict) and o.get('action') == 'create' and o.get('name')]
    if not crea:
        return 0

    clases, destinos, cacheado = indice_cacheado()
    cat = nombres_catalogo()

    for op in crea:
        nombre = str(op['name']).strip()
        contenido = str(op.get('content') or '')
        ts = time.strftime('%Y-%m-%dT%H:%M:%S%z')
        cand = candidatos(nombre, contenido, clases)

        if override_vigente(nombre):
            log({'ts': ts, 'session_id': payload.get('session_id'), 'skill': nombre,
                 'veredicto': 'CREAR', 'motivo': 'override firmado por el dueño', 'candidatos': cand})
            continue

        # D1 — nombre de un references existente
        if nombre in destinos and '/references/' in destinos[nombre]:
            dest = destinos[nombre]
            log({'ts': ts, 'session_id': payload.get('session_id'), 'skill': nombre,
                 'veredicto': 'OMITIR', 'destino': dest, 'candidatos': cand})
            bloquear('GATE DE AUTOSKILLS · OMITIR: "%s" ya existe en el catalogo.\n\n'
                     '  existente: %s\n\nNo crees nada: consulta skill_view y, si te falta un '
                     'detalle, enriquece ese fichero.' % (nombre, dest))

        # D2 — nombre de una clase de core/
        if nombre in destinos:
            dest = destinos[nombre]
            log({'ts': ts, 'session_id': payload.get('session_id'), 'skill': nombre,
                 'veredicto': 'EDITAR', 'destino': dest, 'candidatos': cand})
            bloquear('GATE DE AUTOSKILLS · EDITAR, no crear: "%s" es una CLASE existente.\n\n'
                     '  destino: %s\n\nEnriquece la clase con skill_manage(patch) o baja el detalle '
                     'a un references/ nuevo.' % (nombre, dest))

        # D3 — casi identico a algo que ya existe (plural/guion/guion_bajo)
        norm = normaliza(nombre)
        norm_dest = {normaliza(k): v for k, v in destinos.items()}
        existente = None
        if norm in cat:
            existente = 'skills/%s' % cat[norm][0]
        elif norm in norm_dest:
            existente = norm_dest[norm]
        if existente:
            log({'ts': ts, 'session_id': payload.get('session_id'), 'skill': nombre,
                 'veredicto': 'EDITAR', 'destino': existente, 'candidatos': cand, 'regla': 'D3'})
            bloquear('GATE DE AUTOSKILLS · EDITAR: "%s" es un sinonimo de algo que ya existe '
                     '(mismo objeto, dos grafias).\n\n  existente: %s\n\n'
                     'No dupliques el objeto: enriquece el existente o usa otro nombre.'
                     % (nombre, existente))

        # permitido: se registra con candidatos para revision posterior
        log({'ts': ts, 'session_id': payload.get('session_id'), 'skill': nombre,
             'veredicto': 'CREAR', 'candidatos': cand, 'corpus': len(clases), 'cache': cacheado})
        print(digest(clases))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as exc:
        print(json.dumps({'action': 'block', 'message':
                          'GATE DE AUTOSKILLS con fallo interno (%s). No se crea nada hasta '
                          'revisarlo; reporta al dueño.' % exc}, ensure_ascii=False))
        sys.exit(2)
