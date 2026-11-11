#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""peguelo_ledger.py — ledger de lecciones con regla de promocion 1-2-3.

  add  --rule TEXTO --destination skill|memoria|brain|guard|nada --target NOMBRE
       [--session ID] [--evidence "msg#12 ..."] [--ledger PATH]
  count --rule TEXTO
  list [--tail N]

Regla: 1 aparicion = solo ledger; 2 = candidata a parche de skill; 3+ = escalar a guard/hook.
Escribe JSONL (append-only). No toca state.db.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone

DEFAULT_LEDGER = os.environ.get("PEGUELO_LEDGER") or "/opt/data/brain/ops/session-retros/ledger.jsonl"
VALID = ("skill", "memoria", "brain", "guard", "nada")


def norm(rule):
    r = rule.lower().strip()
    r = re.sub(r"\s+", " ", r)
    r = re.sub(r"[^\wáéíóúñü ]", "", r)
    return r


def lesson_id(rule):
    return hashlib.sha1(norm(rule).encode("utf-8")).hexdigest()[:10]


def load(path):
    out = []
    if not os.path.isfile(path):
        return out
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


def append(path, entry):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def promote(n, destination):
    if n >= 3:
        return "ESCALAR: 3+ repeticiones -> propon guard/hook que lo bloquee en codigo" if destination != "guard" else "guard ya propuesto: verificar que exista"
    if n == 2:
        return "PARCHE: 2 repeticiones -> proponer parche de la skill/regla concreta"
    return "LEDGER: primera vez, no tocar nada todavia"


def cmd_add(args):
    entries = load(args.ledger)
    n = sum(1 for e in entries if e.get("lesson_id") == lesson_id(args.rule)) + 1
    entry = {
        "ts": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "lesson_id": lesson_id(args.rule),
        "rule": args.rule.strip(),
        "destination": args.destination,
        "target": args.target or "",
        "session": args.session or "",
        "evidence": args.evidence or "",
        "recurrence": n,
        "promotion": promote(n, args.destination),
    }
    append(args.ledger, entry)
    print(json.dumps(entry, ensure_ascii=False, indent=1))
    return 0


def cmd_count(args):
    entries = load(args.ledger)
    n = sum(1 for e in entries if e.get("lesson_id") == lesson_id(args.rule))
    print(json.dumps({"lesson_id": lesson_id(args.rule), "count": n, "promotion": promote(n, "skill"),
                      "ledger": args.ledger}, ensure_ascii=False))
    return 0


def cmd_list(args):
    entries = load(args.ledger)
    for e in entries[-args.tail:]:
        print("%s x%s [%s->%s] %s" % (e.get("ts", "?")[:10], e.get("recurrence"), e.get("destination"),
                                      e.get("target") or "-", e.get("rule", "")[:120]))
    print("total:", len(entries))
    return 0


def selftest():
    """Deterministico, sin red: prueba las tres formas de fijar el ledger y la validacion."""
    import contextlib
    import io
    import shutil
    import tempfile
    d = tempfile.mkdtemp(prefix="peguelo_ledger_")
    checks = []
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        try:
            # 1. flag global ANTES del subcomando
            a = os.path.join(d, "a.jsonl")
            main(["--ledger", a, "add", "--rule", "regla uno", "--destination", "nada"])
            checks.append(("ledger_global_antes", len(load(a)), 1))

            # 2. flag DESPUES del subcomando (lo que el SKILL documenta de forma natural)
            b = os.path.join(d, "b.jsonl")
            try:
                main(["add", "--ledger", b, "--rule", "regla dos", "--destination", "nada"])
                n = len(load(b))
            except SystemExit:
                n = -1
            checks.append(("ledger_despues_subcomando", n, 1))

            # 3. count con el flag despues del subcomando, sobre el mismo ledger
            try:
                main(["count", "--ledger", b, "--rule", "regla dos"])
                ok = os.path.isfile(b) and len(load(b)) == 1
            except SystemExit:
                ok = False
            checks.append(("count_despues_subcomando", ok, True))

            # 4. un destino invalido sigue rechazandose
            try:
                main(["--ledger", a, "add", "--rule", "x", "--destination", "inventado"])
                bad = False
            except SystemExit:
                bad = True
            checks.append(("destino_invalido_rechazado", bad, True))
        finally:
            shutil.rmtree(d, ignore_errors=True)

    fails = [(n, g, e) for n, g, e in checks if g != e]
    for n, g, e in checks:
        print("%-26s %-8s got=%r exp=%r" % (n, "OK" if g == e else "FALLA", g, e))
    if fails:
        print("SELFTEST LEDGER FALLIDO: %d" % len(fails))
        return 1
    print("SELFTEST LEDGER OK (%d comprobaciones)" % len(checks))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Ledger de lecciones del peguelo")
    ap.add_argument("--ledger", default=DEFAULT_LEDGER)
    ap.add_argument("--selftest", action="store_true", help="prueba determinista de las formas de invocacion")
    sub = ap.add_subparsers(dest="cmd")
    a = sub.add_parser("add")
    a.add_argument("--ledger", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    a.add_argument("--rule", required=True)
    a.add_argument("--destination", required=True, choices=VALID)
    a.add_argument("--target", default="")
    a.add_argument("--session", default="")
    a.add_argument("--evidence", default="")
    c = sub.add_parser("count")
    c.add_argument("--ledger", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    c.add_argument("--rule", required=True)
    l = sub.add_parser("list")
    l.add_argument("--ledger", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    l.add_argument("--tail", type=int, default=20)
    args = ap.parse_args(argv)
    if getattr(args, "selftest", False) and not args.cmd:
        return selftest()
    if not args.cmd:
        ap.error("elige un subcomando: add | count | list")
    # El flag puede venir antes o despues del subcomando: se resuelve una sola vez aqui.
    args.ledger = getattr(args, "ledger", None) or DEFAULT_LEDGER
    return {"add": cmd_add, "count": cmd_count, "list": cmd_list}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
