#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
guard_config_model_mutation.py — hook pre_tool_call: protege la configuración de
Hermes (config.yaml, .env, perfiles, modelo) contra mutación directa por tools.

REGLA QUE EJECUTA (Plon, dura en SOUL.md): nunca alterar la configuración de
Hermes (config.yaml, .env, cron, MCP, profiles) sin el ciclo D-I-V-E.

Bloquea: write_file/patch/edit_file contra ficheros protegidos; terminal/
execute_code con patrones de mutación directa sobre ellos.
Permite: todo lo demás (incluida la CLI sancionada `hermes cron ...`).
Escapadera del operador (D-I-V-E): /opt/data/state/config_guard_override.json
  [{"objetivo": "config.yaml", "expira": "2026-11-05T23:59:00-05:00", "nota": "..."}]
Log: /opt/data/state/config_guard.jsonl
Protocolo: stdin JSON {tool_name, tool_input, session_id} · exit 0 permite ·
{"action":"block","message":...} + exit 2 bloquea · fallo interno = bloquear.
"""
import json
import os
import re
import sys
import time
from pathlib import Path

HOME = Path('/opt/hermes-agent-data')
STATE = Path('/opt/data/state')
LOG = STATE / 'config_guard.jsonl'
OVERRIDE = STATE / 'config_guard_override.json'

PROTEGIDOS_RE = [
    r'^/opt/hermes-agent-data/config\.yaml$',
    r'^/opt/hermes-agent-data/profiles/[^/]+/config\.yaml$',
    r'^/opt/hermes-agent-data/\.env(\.\w+)?$',
    r'^/opt/hermes-agent-data/profiles/[^/]+/\.env$',
    r'^/opt/hermes-agent-data/profiles/[^/]+/secrets.*\.env$',
    r'^/opt/hermes-agent-data/profiles/[^/]+/memories/MEMORY\.md$',
    r'^/etc/hermes-vault/.*\.env$',
    r'^/opt/hermes-agent/config\.yaml$',
]
CMD_MUTA_RE = [
    r'\bsed\b.+(config\.yaml|\.env\b)',
    r'\btee\s+.+(config\.yaml|\.env\b)',
    r'echo\s+.+>\s*.+(config\.yaml|\.env\b)',
    r'>\s*/opt/hermes-agent-data/(config\.yaml|profiles/[^/]+/config\.yaml|\.env)',
    r'\bcp\b.+(config\.yaml|\.env)\s+.+(config\.yaml|\.env)',
    r'\bmv\b.+(config\.yaml|\.env\b)',
    r'\brm\b.+(config\.yaml|\.env\b)',
    r'hermes\s+config\s+set\s+(model|provider)',
    r'git\s+checkout\s+.+config\.yaml',
]


def log(reg):
    try:
        STATE.mkdir(parents=True, exist_ok=True)
        with LOG.open('a', encoding='utf-8') as fh:
            fh.write(json.dumps(reg, ensure_ascii=False) + '\n')
    except Exception:
        pass


def bloquear(msg):
    print(json.dumps({'action': 'block', 'message': msg}, ensure_ascii=False))
    sys.exit(2)


def protegido(ruta):
    ruta = str(ruta).strip()
    if not ruta.startswith('/'):
        ruta = str((HOME / ruta).resolve())
    return any(re.match(p, ruta) for p in PROTEGIDOS_RE)


def overrides_vigentes():
    try:
        ahora = time.time()
        vivos = []
        for o in json.loads(OVERRIDE.read_text(encoding='utf-8')):
            exp = str(o.get('expira', ''))
            try:
                if time.mktime(time.strptime(exp[:19], '%Y-%m-%dT%H:%M:%S')) >= ahora:
                    vivos.append(str(o.get('objetivo', '')))
            except Exception:
                continue
        return vivos
    except Exception:
        return []


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    tool = payload.get('tool_name', '')
    ti = payload.get('tool_input') or {}
    ts = time.strftime('%Y-%m-%dT%H:%M:%S%z')

    if tool in ('write_file', 'patch', 'edit_file'):
        objetivo = str(ti.get('path') or ti.get('file_path') or ti.get('target') or '')
        muto = True
    elif tool in ('terminal', 'execute_code'):
        cmd = json.dumps(ti, ensure_ascii=False)
        objetivo = str(ti.get('command') or ti.get('code') or '')[:300]
        muto = any(re.search(p, cmd, re.I) for p in CMD_MUTA_RE)
    else:
        return 0

    if not muto or not objetivo:
        return 0
    if not protegido(objetivo):
        return 0

    for o in overrides_vigentes():
        if o and o.lower() in objetivo.lower():
            log({'ts': ts, 'session_id': payload.get('session_id'), 'tool': tool,
                 'veredicto': 'PERMITIR (override D-I-V-E vigente)', 'objetivo': objetivo[:160]})
            return 0

    log({'ts': ts, 'session_id': payload.get('session_id'), 'tool': tool,
         'veredicto': 'BLOQUEAR', 'objetivo': objetivo[:160]})
    bloquear(
        'GUARD DE CONFIG/MODELO: "%s" tocaría la configuración de Hermes por vía directa.\n\n'
        '  Regla dura: config.yaml/.env/cron/MCP/profiles solo con el ciclo D-I-V-E\n'
        '  (Diagnose -> Backup -> Change -> Verify) y con OK del dueño.\n\n'
        '  Si el operador autorizó esta ventana escribió\n'
        '  /opt/data/state/config_guard_override.json (objetivo + expiración); si no,\n'
        '  usa la CLI sancionada (`hermes cron ...`, `hermes config get`) o pide la\n'
        '  ventana de override al dueño.' % tool)
    return 2


if __name__ == '__main__':
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as exc:
        try:
            print(json.dumps({'action': 'block', 'message':
                              'GUARD DE CONFIG/MODELO con fallo interno (%s). Mutación no '
                              'evaluada; reporta al dueño.' % exc}, ensure_ascii=False))
        except Exception:
            pass
        sys.exit(2)
