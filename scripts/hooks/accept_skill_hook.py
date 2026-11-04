#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
accept_skill_hook.py — aprueba el hook del gate en cada hogar de perfil
======================================================================

El registro del hook en `hooks:` queda INERTE hasta que el par (evento, comando)
esta en la allowlist del hogar:  <HERMES_HOME>/shell-hooks-allowlist.json

Este script usa las funciones del PROPIO motor (agent.shell_hooks._record_approval)
para escribir esa entrada, en vez de fabricar el JSON a mano. Se ejecuta una vez
por hogar y es idempotente.

USO:  python3 scripts/hooks/accept_skill_hook.py [--dry-run]
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

REPO = Path('/root/hermes-agent-legacy-docker')
COMANDO = '/host/root/hermes-agent-legacy-docker/scripts/hooks/guard_autoskill_create.py'
PY = '/opt/hermes/.venv/bin/python3'

# Rutas VISTAS DESDE EL CONTENEDOR (el mismo directorio del host, otro montaje):
# el hogar del default es /opt/data y el de cada perfil /opt/data/profiles/<p>.
HOGARES = ['/opt/data'] + [
    '/opt/data/profiles/' + p.name
    for p in sorted((REPO / 'data/profiles').glob('*')) if p.is_dir()
]

CODIGO = '''
import sys
sys.path.insert(0, "/opt/hermes")
from agent.shell_hooks import _record_approval, allowlist_path, load_allowlist, _is_allowlisted
_record_approval("pre_tool_call", "%s")
p = allowlist_path()
print("   allowlist:", p)
print("   aprobado :", _is_allowlisted("pre_tool_call", "%s"))
''' % (COMANDO, COMANDO)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()

    print('hook    : %s' % COMANDO)
    print('hogares : %d' % len(HOGARES))
    if a.dry_run:
        for h in HOGARES:
            print('   (dry) %s -> %s/shell-hooks-allowlist.json' % (h, h))
        return 0

    ok = 0
    for h in HOGARES:
        # La allowlist la escribe el runtime: se ejecuta DENTRO del contenedor
        # (el venv de Hermes vive ahi) con el mismo HERMES_HOME, que es el mismo
        # directorio del host (el compose monta ./data en /opt/data).
        out = subprocess.run(
            ['docker', 'exec', '-u', '10000', '-e', 'HERMES_HOME=' + h,
             'hermes-agent', PY, '-c', CODIGO],
            capture_output=True, text=True)
        bien = 'True' in out.stdout
        ok += 1 if bien else 0
        print('%-34s %s' % (os.path.basename(h) or h, 'OK' if bien else 'FALLO'))
        if not bien and (out.stdout or out.stderr):
            print('     %s' % (out.stdout + out.stderr).strip().splitlines()[-1][:150])
    print('')
    print('hogares aprobados: %d/%d' % (ok, len(HOGARES)))
    return 0 if ok == len(HOGARES) else 1


if __name__ == '__main__':
    sys.exit(main())
