#!/usr/bin/env python3
"""Resumen de dashboard-auth.log (JSON por linea) por IP de cliente.

Uso:
  python3 auth-log-summary.py                       # todas las IPs: conteo, primer/ultimo evento, motivos
  python3 auth-log-summary.py --ip 100.116.169.91   # una sola IP + ultimos eventos crudos
  python3 auth-log-summary.py --event native_       # eventos cuyo nombre empieza con el prefijo

Sin dependencias. La log vive en el host: /host/root/hermes-agent-legacy-docker/data/logs/dashboard-auth.log
"""
import argparse
import collections
import json

DEFAULT_LOG = "/host/root/hermes-agent-legacy-docker/data/logs/dashboard-auth.log"


def load(path):
    rows = []
    with open(path, errors="ignore") as fh:
        for line in fh:
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue
    rows.sort(key=lambda d: d.get("ts", ""))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", default=DEFAULT_LOG)
    ap.add_argument("--ip", help="filtrar por IP de cliente (ej. la del tailnet)")
    ap.add_argument("--event", help="prefijo del nombre de evento (ej. native_, refresh_failure)")
    ap.add_argument("--tail", type=int, default=15, help="cuantos eventos crudos mostrar (0 = ninguno)")
    a = ap.parse_args()

    try:
        rows = load(a.log)
    except OSError as exc:
        print("No se pudo leer %s: %s" % (a.log, exc))
        return
    print("total eventos: %d  (%s)" % (len(rows), a.log))

    if a.ip:
        sel = [d for d in rows if d.get("ip") == a.ip]
        first = sel[0]["ts"][:19] if sel else "-"
        last = sel[-1]["ts"][:19] if sel else "-"
        print("\n%s: %d eventos  primero=%s  ultimo=%s" % (a.ip, len(sel), first, last))
        c = collections.Counter((d.get("event"), d.get("reason", "")) for d in sel)
        for (ev, rs), n in c.most_common():
            print("  %7d  %s%s" % (n, ev, (" / " + rs) if rs else ""))
        if a.tail:
            print("  --- ultimos ---")
            for d in sel[-a.tail:]:
                print("   ", d.get("ts", "")[:19], d.get("event"), d.get("reason", ""), d.get("provider", ""))
        return

    if a.event:
        sel = [d for d in rows if str(d.get("event", "")).startswith(a.event)]
        print("\neventos '%s*': %d" % (a.event, len(sel)))
        for d in sel:
            print("   ", d.get("ts", "")[:19], d.get("event"), d.get("ip"), d.get("provider", ""))
        return

    per = collections.defaultdict(lambda: {"n": 0, "first": "", "last": "", "ev": collections.Counter(), "rs": collections.Counter()})
    for d in rows:
        e = per[d.get("ip", "?")]
        e["n"] += 1
        ts = d.get("ts", "")
        e["first"] = e["first"] or ts
        e["last"] = ts
        e["ev"][d.get("event")] += 1
        if d.get("reason"):
            e["rs"][d["reason"]] += 1

    print("\n== por IP (ordenado por ultimo evento) ==")
    for ip, e in sorted(per.items(), key=lambda kv: kv[1]["last"]):
        print("%s\n    n=%d first=%s last=%s" % (ip, e["n"], e["first"][:19], e["last"][:19]))
        print("    events=%s" % dict(e["ev"]))
        if e["rs"]:
            print("    reasons=%s" % dict(e["rs"]))


if __name__ == "__main__":
    main()
