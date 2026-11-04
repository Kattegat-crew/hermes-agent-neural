#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
autoskill_override.py — excepcion firmada, de un solo uso, para el gate de autoskills
====================================================================================

Cuando el gate resuelve EDITAR/OMITIR pero el agente tiene razon en que se trata de
una CLASE NUEVA ajena a los 19 paraguas, el dueño puede autorizar la creacion una vez.

    autoskill_override.py --firma TOKEN --name <skill> --justify "<razon>"

El permiso caduca en 10 minutos, se consume con la primera creacion y queda en el
ledger (data/state/autoskill_gate.jsonl). Sin firma valida no se escribe nada.
"""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

SHA_FILE = Path('/root/.sync-firma.sha256')
DESTINOS = [Path('/opt/data/state'), Path('/tmp')]


def dir_datos():
    for d in DESTINOS:
        try:
            d.mkdir(parents=True, exist_ok=True)
            p = d / '.probe'
            p.write_text('x')
            p.unlink()
            return d
        except Exception:
            continue
    return Path('/tmp')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--firma', default='')
    ap.add_argument('--name', required=True)
    ap.add_argument('--justify', required=True)
    ap.add_argument('--ttl', type=int, default=600, help='segundos de validez (max 3600)')
    a = ap.parse_args()

    if not SHA_FILE.is_file():
        print('🔒 GATE CERRADO — no existe %s (lo crea el dueño).' % SHA_FILE)
        return 1
    if not a.firma:
        print('🔒 GATE CERRADO — falta --firma TOKEN.')
        return 1
    if hashlib.sha256(a.firma.encode()).hexdigest() != SHA_FILE.read_text().strip():
        print('❌ FIRMA INVÁLIDA — el token no coincide con el autorizado por el dueño.')
        return 1
    if len(a.justify.strip()) < 15:
        print('❌ La justificación es obligatoria y debe ser explicativa (>= 15 caracteres).')
        return 1

    ttl = min(max(a.ttl, 60), 3600)
    d = dir_datos()
    reg = {'name': a.name.strip(), 'justify': a.justify.strip(),
           'emitido': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
           'expira': time.time() + ttl, 'autorizado_por': 'dueno (firma verificada)'}
    (d / 'autoskill_override.json').write_text(json.dumps(reg, indent=1, ensure_ascii=False),
                                               encoding='utf-8')
    with (d / 'autoskill_gate.jsonl').open('a', encoding='utf-8') as fh:
        fh.write(json.dumps({'ts': reg['emitido'], 'skill': reg['name'],
                             'veredicto': 'OVERRIDE EMITIDO', 'justify': reg['justify'],
                             'ttl_s': ttl}, ensure_ascii=False) + '\n')
    print('✅ Override vigente por %d s para "%s". Se consume con la primera creación y queda en el ledger.'
          % (ttl, reg['name']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
