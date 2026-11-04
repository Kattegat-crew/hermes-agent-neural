#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validación de los 13 configs + del valor efectivo de las claves de F3."""
import glob
import sys

import yaml

rutas = ['/opt/data/config.yaml'] + sorted(glob.glob('/opt/data/profiles/*/config.yaml'))
ok = roto = 0
for f in rutas:
    try:
        d = yaml.safe_load(open(f, encoding='utf-8'))
    except Exception as e:
        print('ROTO  %-45s %s' % (f, str(e).replace('\n', ' | ')[:90]))
        roto += 1
        continue
    s = (d or {}).get('skills') or {}
    print('OK    %-45s external_dirs=%s guard_agent_created=%s on_demand=%s'
          % (f, s.get('external_dirs', '—'), s.get('guard_agent_created', '—'),
             s.get('on_demand', '—')))
    ok += 1
print()
print('validos=%d roto=%d' % (ok, roto))
sys.exit(1 if roto else 0)
