#!/usr/bin/env python3
"""Ejecuta plan PAUSED (campana + adsets) via COMPOSIO_MULTI_EXECUTE_TOOL.
Uso: COMPOSIO_MCP_KEY=<key> ads_execute_composio.py <dryrun.json> <account_name> [--verbose-first]
Saltos creatives/ads (gap video). Refs ${campaign:...}/${adset:...} resueltas
con IDs reales capturados de respuestas previas.

NOTA 16-oct-2026: con 2 conexiones metaads activas el campo 'account' es
RECHAZADO en todas las shapes probadas (ticket 1560875784246399059).
Verificar estado de la cuenta antes de reintentar CREATE con id nulo."""
import json, os, re, sys, time, urllib.request

KEY = os.environ["COMPOSIO_MCP_KEY"]
ACCOUNT = sys.argv[2]
VERBOSE = '--verbose-first' in sys.argv

def rpc(params):
    body = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": params}
    req = urllib.request.Request(
        "https://connect.composio.dev/mcp", data=json.dumps(body).encode(),
        headers={"x-consumer-api-key": KEY, "Content-Type": "application/json",
                 "Accept": "application/json, text/event-stream"})
    raw = urllib.request.urlopen(req, timeout=120).read().decode()
    lines = [l[6:] for l in raw.splitlines() if l.startswith('data: ')]
    d = json.loads(lines[-1]) if lines else json.loads(raw)
    return json.loads(d['result']['content'][0]['text'])

def execute(tool_slug, args):
    payload = {'tools': [{'tool_slug': tool_slug,
                          'arguments': dict(args, account=ACCOUNT)}]}
    r = rpc({'name': 'COMPOSIO_MULTI_EXECUTE_TOOL', 'arguments': payload})
    results = r.get('data', {}).get('results', [])
    res = results[0] if results else {}
    if not r.get('successful') or res.get('error'):
        raise RuntimeError(f"{tool_slug}: {json.dumps(res)[:400]}")
    return res

def find_ids(obj):
    return re.findall(r'"id"\s*:\s*"?(23\d{13,17})"?', json.dumps(obj))

dryrun = json.load(open(sys.argv[1]))
refs, out = {}, []
for op in dryrun['operations']:
    if op['operation_type'] in ('create_ad_creative', 'create_ad'):
        out.append({'step': op['step_order'], 'skipped': op['operation_type']})
        continue
    payload = json.loads(json.dumps(op['normalized_payload']))
    for k, v in payload.items():
        if isinstance(v, str) and v.startswith('${'):
            payload[k] = refs[v[2:-1]]
    res = execute(op['tool_slug'], payload)
    ids = find_ids(res)
    refs[op['local_ref_id']] = ids[0] if ids else None
    out.append({'step': op['step_order'], 'op': op['operation_type'],
                'name': payload.get('name'), 'id': ids[0] if ids else None})
    if VERBOSE and op['step_order'] == 1:
        print('RESPUESTA 1a OP:', json.dumps(res, ensure_ascii=False)[:700], file=sys.stderr)
    time.sleep(1.5)

print(json.dumps(out, ensure_ascii=False, indent=1))
ok = all(r.get('id') or r.get('skipped') for r in out)
print('RESUMEN:', 'OK' if ok else 'FALLO', file=sys.stderr)
