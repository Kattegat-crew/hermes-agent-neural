#!/usr/bin/env python3.12
"""Inventario legible de una instalación Hermes (JSON + Markdown).

Uso:
    python3.12 make_inventory.py [BASE_DATA_DIR] [OUT_PREFIX]

    BASE_DATA_DIR  default /opt/data              (DEV local)
    OUT_PREFIX     default <BASE>/deliverables/inventory-<fecha>

Para PROD: copiar el script al host (`ssh prod 'cat > /tmp/make_inventory.py'`)
y correrlo allá con BASE=/opt/hermes/data, o traer los archivos por SSH y
apuntar BASE a la copia local. Nunca parsear configs desde memoria.

Produce: <OUT_PREFIX>.json (completo) y <OUT_PREFIX>.md (resumen para ticket).
Fuente de crons: <BASE>/cron/jobs.json (jobs.db/cron.db suelen estar vacíos).
"""
import datetime, glob, json, os, subprocess, sys

import yaml

BASE = sys.argv[1] if len(sys.argv) > 1 else '/opt/data'
PREFIX = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
    BASE, 'deliverables', 'inventory-' + datetime.date.today().isoformat())
os.makedirs(os.path.dirname(PREFIX), exist_ok=True)


def sh(cmd, timeout=25):
    try:
        return subprocess.run(cmd, shell=True, capture_output=True, text=True,
                              timeout=timeout).stdout.strip()
    except Exception as exc:
        return f'ERR {exc}'


root = yaml.safe_load(open(f'{BASE}/config.yaml')) or {}
inv = {'generado': datetime.datetime.now().isoformat(timespec='seconds')}

inv['version'] = sh('hermes --version 2>/dev/null | head -1')
inv['health'] = sh(f"curl -s -m 5 http://127.0.0.1:8642/health")

# claves de comportamiento (CLI sancionada; timeout alto: la CLI puede tardar)
KEYS = ['webapp.enabled', 'plugins.isolation', 'plugins.auto_apply',
        'kanban.dispatch_in_gateway', 'kanban.dispatch_interval_seconds',
        'delegation.backend', 'skills.on_demand', 'sessions.retention_days',
        'security.redact_secrets', 'gateway.multiplex_profiles',
        'memory.on_demand']
inv['flags'] = {k: sh(f'hermes config get {k} 2>/dev/null | tail -1', timeout=60)
                for k in KEYS}

# perfiles: cada config es candidato a override completo — leerlo, no asumir herencia
profiles = []
for name in sorted(os.listdir(f'{BASE}/profiles')):
    cf = f'{BASE}/profiles/{name}/config.yaml'
    if not os.path.isfile(cf):
        profiles.append({'perfil': name, 'nota': 'sin config (huérfano?)'})
        continue
    try:
        c = yaml.safe_load(open(cf)) or {}
    except Exception as exc:
        profiles.append({'perfil': name, 'error': str(exc)})
        continue
    m = c.get('model') or {}
    profiles.append({
        'perfil': name,
        'modelo': m.get('default'),
        'proveedor': m.get('provider'),
        'kanban_dispatch': (c.get('kanban') or {}).get('dispatch_in_gateway', '(hereda raíz)'),
        'plugins_enabled': (c.get('plugins') or {}).get('enabled'),
        'mcp_count': len(c.get('mcp_servers') or {}),
    })
inv['perfiles'] = profiles

# gateways vivos
inv['gateways'] = sh("ps -eo cmd | grep -o -- '-p [a-z-]* gateway run' | sort | uniq -c")

# crons: fuente real jobs.json
try:
    d = json.load(open(f'{BASE}/cron/jobs.json'))
    jobs = d.get('jobs', d) if isinstance(d, dict) else d
    if isinstance(jobs, dict):
        jobs = list(jobs.values())
    cron_jobs = []
    for j in jobs:
        sch = j.get('schedule') or {}
        cron_jobs.append({'id': j.get('id'), 'nombre': j.get('name'),
                          'schedule': sch.get('display') if isinstance(sch, dict) else sch,
                          'enabled': j.get('enabled'),
                          'perfil': j.get('profile') or j.get('agent') or 'default'})
    inv['crons'] = {'total': len(cron_jobs), 'jobs': cron_jobs}
except Exception as exc:
    inv['crons'] = {'error': str(exc)}

# skills por categoría
cat = {}
skills_root = '/opt/hermes-agent/skills'
for f in glob.glob(f'{skills_root}/**/SKILL.md', recursive=True):
    rel = os.path.relpath(f, skills_root)
    cat.setdefault(rel.split('/')[0] if '/' in rel else '(raiz)', []).append(rel.split('/')[-2])
inv['skills'] = {'total': sum(len(v) for v in cat.values()),
                 'por_categoria': {k: len(v) for k, v in sorted(cat.items())},
                 'nombres': {k: sorted(v) for k, v in sorted(cat.items())}}

# MCP: nombre, tipo y tools.include (lo que recorta superficie por perfil)
inv['mcp'] = {k: {'enabled': bool((v or {}).get('enabled', True)),
                  'type': (v or {}).get('type') or ('http' if (v or {}).get('url') else 'stdio'),
                  'tools_include': ((v or {}).get('tools') or {}).get('include')}
              for k, v in sorted((root.get('mcp_servers') or {}).items())}

inv['plugins'] = {'enabled': (root.get('plugins') or {}).get('enabled'),
                  'disabled': (root.get('plugins') or {}).get('disabled')}

json.dump(inv, open(PREFIX + '.json', 'w'), ensure_ascii=False, indent=1)

L = [f'# Inventario Hermes — {BASE}', f"Generado: {inv['generado']}",
     f"- Versión: `{inv['version']}`",
     f"- Gateway /health → `{inv['health']}`  (dashboard aparte: revisar :9112/api/health)",
     '', '## Flags', '| clave | valor |', '|---|---|']
L += [f'| `{k}` | `{v}` |' for k, v in inv['flags'].items()]
L += ['', '## Perfiles',
      '| perfil | modelo | proveedor | kanban_dispatch | plugins | mcp |', '|---|---|---|---|---|---|']
L += [f"| {p.get('perfil')} | {p.get('modelo')} | {p.get('proveedor')} | "
      f"{p.get('kanban_dispatch')} | {len(p.get('plugins_enabled') or [])} | {p.get('mcp_count')} |"
      for p in profiles]
L += [f"\n## Gateways vivos\n```\n{inv['gateways']}\n```",
      f"\n## Crons: {inv['crons'].get('total')}\n"]
L += [f"- {j.get('id')} · {j.get('nombre')} · {j.get('schedule')} · enabled={j.get('enabled')} · perfil={j.get('perfil')}"
      for j in inv['crons'].get('jobs', [])[:80]]
L += [f"\n## Skills: **{inv['skills']['total']}**\n"]
L += [f'- {k}: {v}' for k, v in inv['skills']['por_categoria'].items()]
L += ['\n## MCP', '| servidor | tipo | activo | tools.include |', '|---|---|---|---|']
L += [f"| {k} | {v['type']} | {v['enabled']} | {v['tools_include']} |" for k, v in inv['mcp'].items()]
L += [f"\n## Plugins raíz\n- activos ({len(inv['plugins']['enabled'] or [])}): {', '.join(inv['plugins']['enabled'] or [])}",
      f"- desactivados: {', '.join(inv['plugins']['disabled'] or [])}"]
open(PREFIX + '.md', 'w').write('\n'.join(L))

print('OK', PREFIX + '.json', PREFIX + '.md')
print('perfiles:', len(profiles), '| skills:', inv['skills']['total'],
      '| crons:', inv['crons'].get('total'), '| mcp:', len(inv['mcp']))
print('flags:', inv['flags'])
