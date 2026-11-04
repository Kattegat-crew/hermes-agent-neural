#!/usr/bin/env python3
"""Pinear platforms.api_server.enabled=false en perfiles secundarios Hermes (v0.21).

Uso: python3 fix_api_pin.py [perfil ...]   (default: roshi comms vigia)
Idempotente. Backup .bak-api-pin-<ts> + readback de verificacion.
Requiere restart del gateway default para surtir efecto (ver SKILL.md RC3).
Correr DENTRO del contenedor hermes-agent (rutas /opt/data/...).
"""
import sys, yaml, shutil, time

profiles = sys.argv[1:] or ['roshi', 'comms', 'vigia']
ts = time.strftime('%Y%m%d-%H%M%S')
for p in profiles:
    path = f'/opt/data/profiles/{p}/config.yaml'
    try:
        c = yaml.safe_load(open(path))
    except FileNotFoundError:
        print(p, 'SKIP (no existe config)')
        continue
    if not isinstance(c, dict):
        print(p, 'SKIP (config vacio)')
        continue
    plat = c.setdefault('platforms', {})
    if not isinstance(plat, dict):
        plat = {}
        c['platforms'] = plat
    if plat.get('api_server') == {'enabled': False}:
        print(p, 'ya pineado (no-op)')
        continue
    shutil.copy2(path, f'{path}.bak-api-pin-{ts}')
    prev = plat.get('api_server')
    plat['api_server'] = {'enabled': False}
    yaml.safe_dump(c, open(path, 'w'), sort_keys=False, allow_unicode=True, width=100)
    chk = yaml.safe_load(open(path))
    ok = chk.get('platforms', {}).get('api_server', {}).get('enabled') is False
    print(p, 'pin=False OK' if ok else '!! FALLO', '| prev bloque:', prev)
