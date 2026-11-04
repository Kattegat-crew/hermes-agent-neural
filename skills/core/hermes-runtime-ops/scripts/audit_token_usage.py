#!/usr/bin/env python3
"""audit_token_usage.py — ¿dónde se van los tokens de la flota? (multi-perfil)

Lee `session_model_usage` + `sessions` de TODOS los state.db del HERMES_HOME y de
sus perfiles, en SOLO LECTURA, y responde las tres preguntas que deciden un cambio
de ruteo de modelos:

  1. ¿cuánto se va en tareas auxiliares vs conversación principal?
  2. ¿qué tarea auxiliar domina? (casi nunca es la que uno supone)
  3. ¿en qué sesiones se concentra? (suelen ser pocas sesiones eternas)

Además reporta la proporción de `cache_read_tokens` (los caps de proveedor suelen
contarlos) y el prefijo medio por llamada (`cache_read / api_calls`).

Uso:
  python3 audit_token_usage.py                    # últimos 30 días
  python3 audit_token_usage.py --days 10
  python3 audit_token_usage.py --since 2026-09-01
  python3 audit_token_usage.py --top 15 --json
  python3 audit_token_usage.py --roots /root/hermes-agent-legacy-docker/data

Solo stdlib.
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import glob
import json
import os
import sqlite3
import sys


def discover_dbs(roots: list[str]) -> list[str]:
    """state.db del HERMES_HOME + uno por perfil (viven en profiles/<perfil>/)."""
    found: list[str] = []
    for root in roots:
        candidates = [os.path.join(root, 'state.db')]
        candidates += sorted(glob.glob(os.path.join(root, 'profiles', '*', 'state.db')))
        candidates += sorted(glob.glob(os.path.join(root, 'profiles', 'state.db')))
        for path in candidates:
            if os.path.exists(path) and path not in found:
                found.append(path)
    return found


def table_exists(con: sqlite3.Connection, name: str) -> bool:
    row = con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return bool(row)


def collect(dbs: list[str], cutoff: float):
    by_task = collections.defaultdict(lambda: [0, 0, 0, 0])          # in, out, cache, calls
    by_model_task = collections.defaultdict(lambda: [0, 0, 0, 0])
    by_session = collections.defaultdict(lambda: [0, 0, 0, ''])      # total, calls, -, etiqueta
    skipped: list[str] = []

    for db in dbs:
        try:
            con = sqlite3.connect(f'file:{db}?mode=ro', uri=True)
        except sqlite3.Error as exc:            # DB ilegible: seguir, no abortar la auditoría
            skipped.append(f'{db}: {exc}')
            continue
        try:
            if not table_exists(con, 'session_model_usage'):
                skipped.append(f'{db}: sin session_model_usage (DB vieja)')
                continue
            for model, task, i, o, cr, calls in con.execute(
                """SELECT model, COALESCE(NULLIF(task,''),'(principal)'),
                          SUM(input_tokens), SUM(output_tokens), SUM(cache_read_tokens),
                          SUM(COALESCE(api_call_count,0))
                   FROM session_model_usage WHERE last_seen > ?
                   GROUP BY model, COALESCE(NULLIF(task,''),'(principal)') """,
                (cutoff,),
            ):
                row = [i or 0, o or 0, cr or 0, calls or 0]
                t = by_task[task]
                m = by_model_task[(model, task)]
                for k in range(4):
                    t[k] += row[k]
                    m[k] += row[k]
            if not table_exists(con, 'sessions'):
                continue
            for sid, source, title, tot, calls in con.execute(
                """SELECT s.id, COALESCE(s.source,'?'), COALESCE(s.title,''),
                          COALESCE(SUM(u.input_tokens),0)+COALESCE(SUM(u.output_tokens),0)
                            +COALESCE(SUM(u.cache_read_tokens),0),
                          COALESCE(SUM(u.api_call_count),0)
                   FROM sessions s LEFT JOIN session_model_usage u ON u.session_id = s.id
                        AND (u.task IS NULL OR u.task = '')
                   WHERE s.started_at > ? GROUP BY s.id""",
                (cutoff,),
            ):
                agg = by_session[sid]
                agg[0] += tot
                agg[1] += calls
                agg[3] = f'{source}: {(title or sid)[:60]}'
        except sqlite3.Error as exc:
            skipped.append(f'{db}: {type(exc).__name__} {exc}')
        finally:
            con.close()
    return by_task, by_model_task, by_session, skipped


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--days', type=int, default=30)
    ap.add_argument('--since', help='AAAA-MM-DD (gana sobre --days)')
    ap.add_argument('--top', type=int, default=12, help='cuántas sesiones listar')
    ap.add_argument('--roots', nargs='*',
                    default=[os.environ.get('HERMES_HOME') or os.path.expanduser('~/.hermes')])
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args(argv)

    if args.since:
        cutoff = dt.datetime.strptime(args.since, '%Y-%m-%d').timestamp()
    else:
        cutoff = (dt.datetime.now() - dt.timedelta(days=args.days)).timestamp()

    dbs = discover_dbs(args.roots)
    if not dbs:
        print('No encontré state.db en: ' + ', '.join(args.roots), file=sys.stderr)
        return 1
    by_task, by_model_task, by_session, skipped = collect(dbs, cutoff)

    tot = sum(v[0] + v[1] + v[2] for v in by_task.values())
    cache = sum(v[2] for v in by_task.values())
    calls = sum(v[3] for v in by_task.values())

    if args.json:
        print(json.dumps({
            'dbs': dbs, 'cutoff': cutoff, 'total_tokens': tot,
            'cache_read_tokens': cache, 'api_calls': calls,
            'by_task': {k: dict(zip(('in', 'out', 'cache', 'calls'), v)) for k, v in by_task.items()},
            'by_model_task': {f'{m}|{t}': dict(zip(('in', 'out', 'cache', 'calls'), v))
                              for (m, t), v in by_model_task.items()},
            'top_sessions': sorted(([v[3], v[0], v[1]] for v in by_session.values()),
                                   key=lambda x: -x[1])[:args.top],
            'skipped': skipped,
        }, indent=1, ensure_ascii=False))
        return 0

    print(f'DBs leídas: {len(dbs)} · desde {dt.datetime.fromtimestamp(cutoff):%Y-%m-%d}')
    print(f'TOTAL: {tot/1e6:.1f}M tokens ({calls} llamadas) · cache_read = {cache/1e6:.1f}M '
          f'({cache/(tot or 1)*100:.1f}%) · prefijo medio {cache/(calls or 1)/1e3:.1f}k/llamada')

    print('\n== Por TAREA ==')
    for task, v in sorted(by_task.items(), key=lambda x: -(x[1][0] + x[1][1] + x[1][2])):
        s = v[0] + v[1] + v[2]
        print(f'  {task:20} {s/1e6:9.1f}M ({s/(tot or 1)*100:5.1f}%)  {v[3]:6} llamadas')

    print('\n== Por MODELO y TAREA (top 12) ==')
    for (model, task), v in sorted(by_model_task.items(),
                                   key=lambda x: -(x[1][0] + x[1][1] + x[1][2]))[:12]:
        s = v[0] + v[1] + v[2]
        print(f'  {model:22} {task:18} {s/1e6:8.1f}M  in {v[0]/1e6:6.1f}M out {v[1]/1e6:5.2f}M '
              f'cache {v[2]/1e6:8.1f}M  {v[3]:5} calls')

    print(f'\n== Top {args.top} SESIONES (concentración) ==')
    for label, s, c in sorted(([v[3], v[0], v[1]] for v in by_session.values()),
                              key=lambda x: -x[1])[:args.top]:
        print(f'  {s/1e6:8.1f}M  {c:5} calls  {label}')

    if skipped:
        print('\n(saltadas: ' + '; '.join(skipped[:5]) + ')')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
