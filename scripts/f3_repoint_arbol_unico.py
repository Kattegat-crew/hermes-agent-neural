#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
F3 · Repunte de la raíz de escritura de skills al árbol único (23-sep-2026)
===========================================================================

POR QUÉ EXISTE ESTE PASO
  F2 montó el canon del repositorio en `/opt/hermes/skills`, pero eso es una
  raíz que el runtime trata como EXTERNA (`skills.external_dirs`): sirve para
  LEER, no para ESCRIBIR. La raíz donde un agente crea una skill sigue siendo
  `get_skills_dir()` = `<HERMES_HOME>/skills`:

      default  -> /opt/data/skills
      <perfil> -> /opt/data/profiles/<perfil>/skills      (hermes -p <perfil>)

  Consecuencia medida hoy: 12 raíces de escritura fuera del control de versión
  (0 SKILL.md en 11 de ellas; 3 instalaciones de hub en la del default) y el
  curador EXCLUYE el canon de su universo por la regla dura de `external_dirs`
  (agent/curator.py:447) — o sea, F4 no puede arrancar mientras esto siga así.

QUÉ HACE
  1. Respalda configs + compose (tar + sha256) ANTES de tocar nada.
  2. Mueve —nunca borra— el estado runtime de cada raíz local al archivo
     (`data/archive/F3_raices_locales_<ts>/`): .hub, .usage.json,
     .curator_*, .bundled_manifest.
  3. Quita `skills.external_dirs` de los 12 configs (root + 11 perfiles).
  4. Monta el canon del repositorio en las 12 rutas de ESCRITURA
     (`./skills:/opt/data/skills` y `./skills:/opt/data/profiles/<p>/skills`).
     Un solo inodo para todo el catálogo ⇒ un solo árbol (invariante I1).
  5. Ignora en git el estado runtime que el canon va a recibir.
  6. Valida (`docker compose config`) y deja reporte JSON en data/state/.

GATE DE FIRMA (bloqueo duro en código, no en la disciplina del agente)
  `--apply` exige `--firma TOKEN`, validado por sha256 contra
  /root/.sync-firma.sha256 (chmod 600, creado por el dueño). Un agente NUNCA
  debe crear ni leer ese archivo. Sin token → exit 1, cero escrituras.

USO
  python3 scripts/f3_repoint_arbol_unico.py                          # dry-run
  python3 scripts/f3_repoint_arbol_unico.py --apply --firma TOKEN
  python3 scripts/f3_repoint_arbol_unico.py --apply --firma TOKEN --hub promover
  (la recreación del contenedor la hace scripts/f3_ventana_repoint.sh, que
   reutiliza el patrón probado de la ventana F2 con rollback automático)
"""
import argparse
import copy
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import yaml

REPO = Path('/root/hermes-agent-legacy-docker')
DATA = REPO / 'data'
CANON = REPO / 'skills'
FIRMA_SHA = Path('/root/.sync-firma.sha256')

PERFILES = ['bragi', 'brokkr', 'comms', 'freyja', 'heimdall', 'hermodr',
            'roshi', 'sindri', 'ullr', 'vigia', 'vili']
CONFIGS = [DATA / 'config.yaml'] + [DATA / 'profiles' / p / 'config.yaml' for p in PERFILES]
COMPOSE = REPO / 'docker-compose.yml'
LINEA_CANON = '      - ./skills:/opt/hermes/skills\n'

# Estado runtime que vive en la raíz local y que, tras el montaje, pasa a
# escribirse dentro del canon. Son ficheros de operación, no catálogo.
ESTADO_RUNTIME = ['.hub', '.usage.json', '.usage.json.lock', '.curator_ledger.jsonl',
                  '.curator_state', '.curator_backups', '.bundled_manifest']

GITIGNORE_ENTRADAS = [
    '',
    '# --- canon montado: estado runtime del catálogo (no es catálogo) ---',
    'skills/.usage.json',
    'skills/.usage.json.lock',
    'skills/.curator_ledger.jsonl',
    'skills/.curator_state',
    'skills/.curator_backups/',
    'skills/.bundled_manifest',
    'skills/.skills_prompt_snapshot.json',
]


def log(msg=''):
    print(msg, flush=True)


def run(cmd, cwd=None, check=True, shell=True):
    out = subprocess.run(cmd, shell=shell, cwd=cwd, capture_output=True, text=True)
    if check and out.returncode != 0:
        log('❌ falló: %s\n%s\n%s' % (cmd, out.stdout[-600:], out.stderr[-600:]))
        raise SystemExit(1)
    return out


def check_firma(firma):
    if not FIRMA_SHA.exists():
        log('🔒 GATE CERRADO — no existe %s (lo crea el dueño).' % FIRMA_SHA)
        return False
    if not firma:
        log('🔒 GATE CERRADO — falta --firma TOKEN (el token lo aporta el dueño).')
        return False
    if hashlib.sha256(firma.encode()).hexdigest() != FIRMA_SHA.read_text().strip():
        log('❌ FIRMA INVÁLIDA — el token no coincide con el autorizado por el dueño.')
        return False
    log('✅ Firma válida.')
    return True


def rutas_raices():
    """(etiqueta, ruta_HOST, ruta_CONTENEDOR) de cada raíz de escritura.

    OJO — el host y el contenedor NO coinciden: dentro del contenedor esas
    rutas son /opt/data/..., pero en el host el mismo árbol vive bajo
    /root/hermes-agent-legacy-docker/data/... (el compose monta `./data:/opt/data`).
    Operar sobre `/opt/data` en el host tocaría un árbol LEGADO distinto.
    """
    out = [('default', DATA / 'skills', '/opt/data/skills')]
    for p in PERFILES:
        out.append((p, DATA / 'profiles' / p / 'skills',
                    '/opt/data/profiles/%s/skills' % p))
    return out


def bloque_external_dirs(txt):
    """Devuelve (inicio, fin) del bloque `external_dirs:` bajo skills:, o None.

    El ítem de lista puede venir indentado con 2 espacios (al mismo nivel que la
    clave) o con 4: el layout ha variado entre perfiles. Se consumen todos los
    ítems consecutivos con indentación >= la de la clave, y se corta en la
    primera línea que no sea ítem.
    """
    lineas = txt.splitlines(keepends=True)
    for i, l in enumerate(lineas):
        if re.match(r'^\s*external_dirs:\s*(\[\s*\]\s*)?$', l):
            indent = len(l) - len(l.lstrip())
            j = i + 1
            while j < len(lineas):
                s = lineas[j]
                if s.strip() == '':
                    break
                lind = len(s) - len(s.lstrip())
                if s.lstrip().startswith('- ') and lind >= indent:
                    j += 1
                    continue
                break
            return i, j
    return None


def quitar_external_dirs(texto):
    """Quita `skills.external_dirs` con validación estructural obligatoria.

    Devuelve (texto_nuevo, quitado, error). El texto nuevo solo se acepta si
    parsea y si el documento resultante es idéntico al original salvo por esa
    clave. Sin esta comprobación, una eliminación mal recortada deja el YAML
    inválido y el runtime cae al config por defecto ignorando todos los
    overrides del perfil (incidente del 23-sep-2026).
    """
    r = bloque_external_dirs(texto)
    if not r:
        return texto, False, None
    i, j = r
    lineas = texto.splitlines(keepends=True)
    nuevo = ''.join(lineas[:i] + lineas[j:])
    try:
        antes = yaml.safe_load(texto) or {}
        despues = yaml.safe_load(nuevo) or {}
    except Exception as e:
        return texto, False, 'YAML inválido tras la edición: %s' % e
    if not isinstance(despues, dict) or (despues.get('skills') or {}).get('external_dirs'):
        return texto, False, 'external_dirs sigue presente en el resultado'
    esperado = copy.deepcopy(antes)
    if isinstance(esperado, dict) and isinstance(esperado.get('skills'), dict):
        esperado['skills'].pop('external_dirs', None)
    if esperado != despues:
        return texto, False, 'la edición cambió el documento más allá de external_dirs'
    return nuevo, True, None


def montajes_faltantes(compose_txt):
    faltan = []
    for etiqueta, _host, cont in rutas_raices():
        spec = '      - ./skills:%s\n' % cont
        if spec not in compose_txt:
            faltan.append((etiqueta, cont, spec))
    return faltan


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument('--apply', action='store_true', help='ejecuta de verdad (exige --firma)')
    ap.add_argument('--firma', default=None, help='token del dueño')
    ap.add_argument('--hub', choices=['archivar', 'promover'], default='archivar',
                    help='destino de las instalaciones de hub que viven en la raíz local')
    a = ap.parse_args()

    if a.apply and not check_firma(a.firma):
        return 1
    if not a.apply:
        log('─ DRY-RUN (nada se escribe) ─')

    ts = time.strftime('%Y%m%d-%H%M%S')
    arch = DATA / 'archive' / ('F3_raices_locales_%s' % ts)
    bck = DATA / 'backups' / 'config' / ('F3_%s' % ts)
    informe = {'ts': ts, 'aplicado': bool(a.apply), 'hub': a.hub, 'pasos': []}

    # ── 1. respaldo ──────────────────────────────────────────────────────────
    existentes = [p for p in CONFIGS + [COMPOSE, Path('/root/hermes-agent-legacy-docker/.gitignore')] if p.is_file()]
    log('\n1) respaldo de %d ficheros → %s' % (len(existentes), bck))
    for p in existentes:
        log('   · %s' % p)
    if a.apply:
        bck.mkdir(parents=True, exist_ok=True)
        for p in existentes:
            rel = str(p).replace('/', '_')
            shutil.copy2(p, bck / rel)
        sha = hashlib.sha256()
        for p in sorted(existentes):
            sha.update(p.read_bytes())
        (bck / 'MANIFIESTO.txt').write_text(
            'Respaldo previo al repunte F3 (%s)\nsha256 conjunto: %s\nficheros: %d\n'
            % (ts, sha.hexdigest(), len(existentes)), encoding='utf-8')
        informe['respaldo'] = {'dir': str(bck), 'sha256_conjunto': sha.hexdigest()}
        log('   sha256 conjunto: %s' % sha.hexdigest()[:16])

    # ── 2. estado runtime de las raíces locales → archivo ────────────────────
    log('\n2) estado runtime de las raíces locales → %s (se MUEVE, no se borra)' % arch)
    movidos, hub_instalados = [], []
    ino_canon = CANON.stat().st_ino
    for etiqueta, ruta, _cont in rutas_raices():
        if not ruta.is_dir():
            continue
        if ruta.stat().st_ino == ino_canon:
            log('   · %-8s (ya ES el canon; no se mueve nada)' % etiqueta)
            continue
        entradas = sorted(p.name for p in ruta.iterdir())
        estado = [n for n in entradas if n in ESTADO_RUNTIME]
        for n in estado:
            log('   · %-8s %s' % (etiqueta, n))
        # instalaciones de hub: directorios con SKILL.md en la raíz local
        hubs = []
        for n in entradas:
            d = ruta / n
            if d.is_dir() and (d / 'SKILL.md').is_file() and n not in ESTADO_RUNTIME:
                hubs.append(n)
        for n in hubs:
            hub_instalados.append({'perfil': etiqueta, 'nombre': n,
                                   'origen': str(ruta / n)})
            log('   · %-8s [hub] %s' % (etiqueta, n))
        if a.apply:
            destino = arch / etiqueta
            for n in estado + hubs:
                destino.mkdir(parents=True, exist_ok=True)
                shutil.move(str(ruta / n), str(destino / n))
                movidos.append('%s/%s' % (etiqueta, n))
    informe['movidos_al_archivo'] = movidos
    informe['instalaciones_hub'] = hub_instalados

    # ── 3. promover las instalaciones de hub al árbol (si se pide) ───────────
    if hub_instalados:
        log('\n3) instalaciones de hub detectadas: %d (modo --hub %s)'
            % (len(hub_instalados), a.hub))
        for h in hub_instalados:
            if a.hub == 'promover':
                # destino: skills/<nombre> en la raíz del canon, versionado
                dst = CANON / h['nombre']
                log('   · promover %s → %s' % (h['nombre'], dst))
                if a.apply:
                    if dst.exists():
                        log('     (ya existe en el canon; se conserva el archivo)')
                    else:
                        shutil.copytree(arch / h['perfil'] / h['nombre'], dst)
            else:
                log('   · archivar %s (queda en %s; reinstalable con `hermes skills install`)'
                    % (h['nombre'], arch / h['perfil'] / h['nombre']))
    else:
        log('\n3) sin instalaciones de hub que resolver.')

    # ── 4. quitar skills.external_dirs de los 12 configs ─────────────────────
    log('\n4) quitar `skills.external_dirs` de los configs')
    tocados, errores = [], []
    for p in CONFIGS:
        if not p.is_file():
            log('   · (no existe) %s' % p)
            continue
        txt = p.read_text(encoding='utf-8')
        nuevo, hizo, err = quitar_external_dirs(txt)
        etiqueta = p.parent.name if p.parent != DATA else 'root'
        if err:
            log('   ❌ %s: %s' % (etiqueta, err))
            errores.append('%s: %s' % (etiqueta, err))
            continue
        if not hizo:
            log('   · %-8s ya sin external_dirs' % etiqueta)
            continue
        log('   · %-8s → quitado (validado estructuralmente)' % etiqueta)
        tocados.append(str(p))
        if a.apply:
            p.write_text(nuevo, encoding='utf-8')
    informe['configs_editados'] = tocados
    informe['configs_con_error'] = errores
    if errores:
        log('\n🛑 ABORTADO: hay configs que no se pudieron editar sin riesgo (%d).' % len(errores))
        return 1

    # ── 5. montar el canon en las 12 rutas de escritura ──────────────────────
    log('\n5) montajes del canon en las rutas de ESCRITURA')
    comp = COMPOSE.read_text(encoding='utf-8')
    faltan = montajes_faltantes(comp)
    for etiqueta, ruta, spec in faltan:
        log('   · + ./skills → %s' % ruta)
    if not faltan:
        log('   · ya presentes (idempotente)')
    elif a.apply:
        if LINEA_CANON not in comp:
            log('❌ no encuentro la línea base del montaje ya aplicado en F2 (%s)' % LINEA_CANON.strip())
            return 1
        comp = comp.replace(LINEA_CANON, LINEA_CANON + ''.join(s for _, _, s in faltan), 1)
        COMPOSE.write_text(comp, encoding='utf-8')

    # ── 6. higiene de .gitignore ─────────────────────────────────────────────
    gi = REPO / '.gitignore'
    gitxt = gi.read_text(encoding='utf-8')
    nuevas = [l for l in GITIGNORE_ENTRADAS if l and l not in gitxt]
    log('\n6) .gitignore: %s' % ('%d entradas nuevas' % len(nuevas) if nuevas else 'ya al día'))
    for l in nuevas:
        log('   · %s' % l)
    if a.apply and nuevas:
        gi.write_text(gitxt.rstrip('\n') + '\n' + '\n'.join(GITIGNORE_ENTRADAS) + '\n', encoding='utf-8')

    # ── 7. validación ────────────────────────────────────────────────────────
    log('\n7) validación')
    if a.apply:
        out = run('docker compose config --quiet', cwd=REPO, check=False)
        if out.returncode != 0:
            log('❌ compose inválido:\n%s\n%s' % (out.stdout[-500:], out.stderr[-500:]))
            return 1
        log('   compose OK')
        # YAML válido en los configs editados
        for ps in tocados:
            t = Path(ps).read_text(encoding='utf-8')
            if 'external_dirs' in t and 'skills:' in t:
                log('   ⚠ %s aún menciona external_dirs' % ps)
        log('   configs editados re-escritos y con sintaxis preservada')
    else:
        log('   (dry-run: no se valida compose)')

    est = DATA / 'state' / ('f3_repoint_%s.json' % ts)
    if a.apply:
        est.parent.mkdir(parents=True, exist_ok=True)
        est.write_text(json.dumps(informe, indent=2, ensure_ascii=False), encoding='utf-8')
        log('\n📄 informe: %s' % est)

    log('\n%s' % ('─ APLICADO ─' if a.apply else '─ DRY-RUN: nada se escribió ─'))
    log('Siguiente: scripts/f3_ventana_repoint.sh --firma TOKEN   (recrea y verifica inodo único)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
