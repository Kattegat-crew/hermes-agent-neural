#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
f3_absorber_autoskills.py — absorbe la re-acumulacion de autoskills en los paraguas
==================================================================================

Lee el manifiesto firmado (docs/skills/absorcion-manifiesto.json) y, para cada caso:

  1. escribe `skills/core/<paraguas>/references/<caso>.md` con el contenido integro
     de la autoskill absorbida + una seccion de procedencia;
  2. añade el caso a las dos listas del `SKILL.md` del paraguas (Proposito/Alcance y
     Casos de Uso Disponibles), conservando el estilo existente;
  3. archiva el origen en data/archive/F3_absorcion_<ts>/ y lo retira de data/skills;
  4. registra la operacion en data/state/f3_absorcion.jsonl.

Nada se borra: el origen queda archivado y restaurable. La copia divergente del caso
`merge` integra SOLO el delta que no estaba ya en el paraguas.

GATE: `--apply` exige `--firma TOKEN` (sha256 contra /root/.sync-firma.sha256).
USO :  python3 scripts/f3_absorber_autoskills.py            # dry-run
       python3 scripts/f3_absorber_autoskills.py --apply --firma TOKEN [--push]
"""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path('/root/hermes-agent-legacy-docker')
SKILLS = REPO / 'skills'
CORE = SKILLS / 'core'
MANIFIESTO = REPO / 'docs' / 'skills' / 'absorcion-manifiesto.json'
SHA_FILE = Path('/root/.sync-firma.sha256')
LEDGER = REPO / 'data' / 'state' / 'f3_absorcion.jsonl'


def log(m=''):
    print(m, flush=True)


def check_firma(firma):
    if not SHA_FILE.is_file():
        log('🔒 GATE CERRADO — no existe %s' % SHA_FILE)
        return False
    if not firma:
        log('🔒 GATE CERRADO — falta --firma TOKEN.')
        return False
    if hashlib.sha256(firma.encode()).hexdigest() != SHA_FILE.read_text().strip():
        log('❌ FIRMA INVÁLIDA.')
        return False
    log('✅ Firma válida.')
    return True


def leer(p, limite=None):
    t = p.read_text(encoding='utf-8', errors='replace')
    return t[:limite] if limite else t


def parrafos(txt):
    return [p.strip() for p in re.split(r'\n\s*\n', txt) if p.strip()]


def delta_para_reference(fuente: Path, reference: Path):
    """Parrafos de la fuente que NO estan ya en el reference (modo merge).

    Comparacion por LINEA, no por parrafo completo: un parrafo cuenta como nuevo
    solo si NINGUNA de sus lineas aparece ya en el reference. Asi el merge es
    idempotente aunque el parrafo se haya re-flowado al escribirlo (bug detectado
    el 23-sep: el delta se duplico por comparar parrafos exactos).
    """
    lineas_ref = set(l.strip() for l in leer(reference).split('\n') if l.strip())
    fuera = []
    for par in parrafos(leer(fuente)):
        pl = [l.strip() for l in par.split('\n') if l.strip()]
        if pl and not any(l in lineas_ref for l in pl):
            fuera.append(par)
    return fuera


def plan(entrada):
    origen = REPO / entrada['origen']
    paraguas = entrada['paraguas']
    sm = CORE / paraguas / 'SKILL.md'
    ref = CORE / paraguas / 'references' / ('%s.md' % entrada['caso'])
    return origen, sm, ref


def aplicar(entrada, archive, ts):
    origen, sm, ref = plan(entrada)
    nombre = entrada['caso']
    modo = entrada['modo']
    reg = {'ts': ts, 'caso': nombre, 'paraguas': entrada['paraguas'], 'modo': modo,
           'origen': entrada['origen'], 'destino': str(ref.relative_to(REPO))}

    # Reanudable: si el origen ya fue archivado y el reference existe, este caso
    # ya se aplicó en una corrida anterior (el script puede morir a mitad de lote).
    if not origen.exists() and ref.exists():
        reg['estado'] = 'ya_aplicado'
        log('   ⏭️  ya aplicado en una corrida previa; se omite')
        with LEDGER.open('a', encoding='utf-8') as fh:
            fh.write(json.dumps(reg, ensure_ascii=False) + '\n')
        return reg

    # 1) respaldos
    (archive / 'origenes').mkdir(parents=True, exist_ok=True)
    if origen.is_dir():
        shutil.copytree(origen, archive / 'origenes' / origen.name, dirs_exist_ok=True)
    if ref.exists():
        (archive / 'references_previas').mkdir(parents=True, exist_ok=True)
        shutil.copy2(ref, archive / 'references_previas' / ref.name)
        shutil.copy2(sm, archive / ('%s.SKILL.md.bak' % entrada['paraguas']))

    # 2) contenido del reference
    if not origen.exists():
        log('   ⚠️ origen inexistente y reference inexistente: nada que hacer')
        return reg
    fuente_txt = leer(origen / 'SKILL.md')
    if modo == 'merge':
        delta = delta_para_reference(origen / 'SKILL.md', ref)
        reg['delta_parrafos'] = len(delta)
        if delta:
            extra = ['', '', '---', '',
                     '## Delta incorporado por F3 (%s)' % ts,
                     '',
                     'Aportes de la copia sin versión `%s` que no estaban ya en esta referencia:'
                     % entrada['origen'], '']
            extra += delta
            ref.write_text(leer(ref).rstrip() + '\n' + '\n'.join(extra) + '\n', encoding='utf-8')
        log('   ♻️  merge: %s (%d parrafos de delta)' % (nombre, len(delta)))
    else:
        ref.parent.mkdir(parents=True, exist_ok=True)
        prov = ['', '', '---', '',
                '## Procedencia',
                '',
                'Absorbido por F3 el %s desde la autoskill `%s` (sin versión en git hasta hoy).'
                % (ts, entrada['origen']),
                'El procedimiento se conserva íntegro; el paraguas `%s` es su punto de entrada.'
                % entrada['paraguas'], '']
        ref.write_text(fuente_txt.rstrip() + '\n' + '\n'.join(prov) + '\n', encoding='utf-8')
        log('   📄 reference escrito: %s' % ref.relative_to(REPO))

    # 3) listas del SKILL.md del paraguas (idempotente)
    sm_txt = leer(sm)
    if '`%s`' % nombre not in sm_txt:
        sm_txt = sm_txt.replace(
            '## Arquitectura y Protocolos',
            '- `%s`\n\n## Arquitectura y Protocolos' % nombre, 1) if '## Arquitectura y Protocolos' in sm_txt \
            else sm_txt
    disparador = entrada.get('disparador') or entrada.get('nota') or '(sin descripcion)'
    linea_caso = ('- **%s**: %s — ver '
                  '[references/%s.md](file:///root/hermes-agent-legacy-docker/skills/core/%s/references/%s.md)'
                  % (nombre, disparador, nombre, entrada['paraguas'], nombre))
    if 'references/%s.md' % nombre not in sm_txt:
        if '## Casos de Uso Disponibles' in sm_txt:
            sm_txt = sm_txt.rstrip() + '\n' + linea_caso + '\n'
        else:
            sm_txt = sm_txt.rstrip() + '\n\n## Casos de Uso Disponibles\n' + linea_caso + '\n'
    sm.write_text(sm_txt, encoding='utf-8')
    log('   📝 paraguas actualizado: %s' % sm.relative_to(REPO))

    # 4) archivar el origen y retirarlo del sedimento
    destino_arch = archive / 'sedimento' / entrada['origen'].replace('/', '__')
    if origen.exists():
        shutil.move(str(origen), str(destino_arch))
        padre = origen.parent
        try:
            while padre != (REPO / 'data' / 'skills') and padre.is_dir() and not any(padre.iterdir()):
                nxt = padre.parent
                padre.rmdir()
                padre = nxt
        except Exception:
            pass
        log('   🗄️  origen archivado: %s' % entrada['origen'])

    with LEDGER.open('a', encoding='utf-8') as fh:
        fh.write(json.dumps(reg, ensure_ascii=False) + '\n')
    return reg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--firma', default='')
    ap.add_argument('--push', action='store_true')
    a = ap.parse_args()

    man = json.loads(MANIFIESTO.read_text(encoding='utf-8'))
    entradas = man['absorciones']
    log('=' * 84)
    log('F3 · ABSORCION DE LA RE-ACUMULACION (%d casos)' % len(entradas))
    log('=' * 84)

    faltan = []
    for e in entradas:
        origen, sm, ref = plan(e)
        ok = origen.is_dir() and sm.is_file()
        bytes_ = (origen / 'SKILL.md').stat().st_size if (origen / 'SKILL.md').is_file() else 0
        ya = ref.exists()
        log('   %-40s -> core/%-24s %s%s' % (
            e['origen'], e['paraguas'], '(%d B) ' % bytes_,
            '[ya existe el reference: modo %s]' % e['modo'] if ya else ''))
        if not ok:
            faltan.append(e['origen'])
    if faltan:
        log('')
        log('   ⚠️ no encontrados: %s' % ', '.join(faltan))

    if not a.apply:
        log('')
        log('🧪 DRY-RUN — nada escrito. Para ejecutar: --apply --firma TOKEN [--push]')
        return 0

    if not check_firma(a.firma):
        return 1

    ts = time.strftime('%Y%m%d-%H%M%S')
    archive = REPO / 'data' / 'archive' / ('F3_absorcion_' + ts)
    archive.mkdir(parents=True, exist_ok=True)
    log('🗄️  Respaldo de esta corrida: %s' % archive)
    log('')
    regs = []
    for e in entradas:
        log('▶ %s -> %s' % (e['origen'], e['paraguas']))
        regs.append(aplicar(e, archive, ts))

    run = lambda c: subprocess.run(c, shell=True, cwd=REPO, capture_output=True, text=True)
    run('find skills -type d -exec chmod 2775 {} +')
    run('find skills -type f -exec chmod 664 {} +')
    msg = 'feat(skills): F3 absorbe %d autoskills en los 19 paraguas de core/ (%s)' % (len(regs), ts)
    run('git add -A skills && git commit -m "%s"' % msg)
    head = run('git rev-parse HEAD').stdout.strip()
    log('')
    log('   ✅ commit: %s (%s)' % (head[:12], msg))
    if a.push:
        run('git push origin HEAD:main')
        remoto = run('git ls-remote origin refs/heads/main').stdout.split()[0]
        log('   %s push: HEAD=%s origin/main=%s' % ('✅' if remoto == head else '❌',
                                                    head[:12], remoto[:12]))
    log('')
    log('🧪 Verificacion:')
    ver = run('python3 scripts/verify_skills.py')
    log('   aduana: %s' % ('VERDE' if 'ADUANA SUPERADA' in ver.stdout else 'REVISAR'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
