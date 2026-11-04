#!/usr/bin/env python3
"""Audita TODOS los cron jobs de Hermes en uno o varios jobs.json (READ-ONLY).

Uso local (dev):
    python3 cron_fleet_audit.py /opt/data/cron/jobs.json /opt/data/profiles/*/cron/jobs.json

Uso en prod (copia el archivo, NO lo pipees por stdin de ssh):
    ssh prod 'cat > /tmp/cron_fleet_audit.py' < cron_fleet_audit.py
    ssh prod "cd /opt/hermes/data && python3 /tmp/cron_fleet_audit.py cron/jobs.json profiles/*/cron/jobs.json"

No ejecuta jobs ni escribe nada: solo lee jobs.json y reporta.

Banderas:
    STATUS=<x>          last_status != ok (error, blocked_config, failure...)
    streak=N            failure_streak > 0
    ATRASADO(Nm)        next_run_at vencido >15 min con el job enabled
    NUNCA-CORRIO        sin last_run_at
    off:<state>         deshabilitado (paused / completed)
    SCRIPT-FALTA        el script declarado no resuelve en <home>/scripts/
    SCRIPT-EN-OTRO-HOME el nombre suelto existe en /opt/data/scripts pero no en el home del perfil
    DELIVERY-ERR        last_delivery_error registrado

Recuerda: last_status=ok NO prueba que haya servido. Revisa el ultimo
cron/output/<jobid>/*.md (0 bytes = sano en un watchdog silencioso;
'monitor' + no_change = sano). Los .md root-owned se leen con
`docker exec hermes-agent cat <archivo>`.
"""
import json
import os
import sys
from datetime import datetime, timezone

LATE_MIN = -15  # minutos de gracia antes de marcar ATRASADO


def parse_ts(s):
    if not s:
        return None
    try:
        d = datetime.fromisoformat(s)
    except Exception:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    now = datetime.now(timezone.utc)
    for path in argv:
        if not os.path.exists(path):
            print("!! no existe: %s" % path)
            continue
        try:
            doc = json.load(open(path, encoding="utf-8"))
        except Exception as e:
            print("!! ilegible: %s (%s)" % (path, e))
            continue
        jobs = doc.get("jobs", []) if isinstance(doc, dict) else doc
        home = os.path.dirname(os.path.dirname(os.path.abspath(path)))
        prof = os.path.basename(home) if "/profiles/" in home else "default"
        print("=== %s  [perfil=%s]  jobs=%d" % (path, prof, len(jobs)))
        for j in jobs:
            flags = []
            status = j.get("last_status") or "-"
            if status not in ("ok", "-"):
                flags.append("STATUS=%s" % status.upper())
            if (j.get("failure_streak") or 0) > 0:
                flags.append("streak=%s" % j["failure_streak"])
            nxt, last = parse_ts(j.get("next_run_at")), parse_ts(j.get("last_run_at"))
            if nxt and j.get("enabled") and j.get("state") not in ("completed",):
                mins = (nxt - now).total_seconds() / 60.0
                if mins < LATE_MIN:
                    flags.append("ATRASADO(%.0fm)" % mins)
            if not last:
                flags.append("NUNCA-CORRIO")
            if not j.get("enabled"):
                flags.append("off:%s" % j.get("state"))
            script = j.get("script")
            if script:
                if script.startswith("/"):
                    if not os.path.exists(script):
                        flags.append("SCRIPT-FALTA")
                else:
                    here = os.path.join(home, "scripts", script)
                    if not os.path.exists(here):
                        alt = os.path.exists(os.path.join("/opt/data/scripts", script))
                        flags.append("SCRIPT-EN-OTRO-HOME" if alt else "SCRIPT-FALTA")
            if j.get("last_delivery_error"):
                flags.append("DELIVERY-ERR")
            print("  %-14s %-34s %-16s en=%s st=%-9s last=%-6s run=%s next=%s deliv=%-28s script=%s%s" % (
                j.get("id"), (j.get("name") or "")[:34], (j.get("schedule_display") or "")[:16],
                "T" if j.get("enabled") else "F", j.get("state") or "-", status,
                j.get("last_run_at") or "-", j.get("next_run_at") or "-",
                str(j.get("deliver"))[:28], str(script),
                ("   <<< " + " ".join(flags)) if flags else ""))
            for key in ("last_error", "last_delivery_error"):
                if j.get(key):
                    print("      %s: %s" % (key, str(j[key]).replace("\n", " | ")[:240]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
