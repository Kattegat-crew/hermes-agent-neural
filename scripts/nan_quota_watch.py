#!/usr/bin/env python3
"""nan_quota_watch — watchdog de cuota de nan.builders para cron `no_agent`.

Silencioso por defecto: imprime SOLO cuando hay algo que decir (stdout vacío = el
cron no entrega nada). Escribe siempre el snapshot en el state file para que el
plugin de Desktop (chip/panel) lo sirva sin golpear la API.

  python3 nan_quota_watch.py            # tick normal (lo que corre el cron)
  python3 nan_quota_watch.py --force    # imprime el resumen aunque no haya alerta
  python3 nan_quota_watch.py --dry      # no escribe estado, sólo muestra
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nan_quota  # noqa: E402

HOME = os.environ.get("HERMES_HOME", "/root/hermes-agent-legacy-docker/data")
STATE = os.path.join(HOME, "state", "nan-quota.json")
LOG = os.path.join(HOME, "logs", "nan-quota-watch.log")
REALERT_H = 6           # reavisar del mismo modelo/estado cada N horas
ERROR_ALERT_AT = 3      # avisar tras N fallos consecutivos (~1h a 30min/tick)
ERROR_REALERT = 48      # y repetir cada N ticks (~24h)


def log(msg: str) -> None:
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as fh:
            fh.write(f"{dt.datetime.now(dt.timezone.utc).isoformat()} {msg}\n")
    except OSError:
        pass


def read_state() -> dict:
    try:
        with open(STATE, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def write_state(snap: dict, extra: dict | None = None) -> None:
    payload = dict(snap)
    payload.update(extra or {})
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    tmp = STATE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, STATE)


def parse_iso(value):
    if not value:
        return None
    try:
        return dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def main(argv: list[str]) -> int:
    now = dt.datetime.now(dt.timezone.utc)
    state = read_state()
    alerts = state.get("alerts") or {}
    errors = int(state.get("consecutive_errors") or 0)

    try:
        key = nan_quota.load_key()
        snap = nan_quota.to_snapshot(nan_quota.fetch_quota(key), now)
    except Exception as exc:  # noqa: BLE001 — nunca reventar el cron
        errors += 1
        log(f"ERROR #{errors}: {exc.__class__.__name__}: {exc}")
        log(traceback.format_exc(limit=3))
        out = ""
        if errors == ERROR_ALERT_AT or (errors > ERROR_ALERT_AT and errors % ERROR_REALERT == 0):
            out = (f"⚠️ **Cuota NaN: sin datos** — {errors} fallos consecutivos consultando "
                   f"`cloud-api.nan.builders/api/usage/quota`.\nÚltimo error: `{exc.__class__.__name__}: {exc}`\n"
                   "El endpoint no tiene contrato público: si sigue así, revisar la ruta.")
        if "--dry" not in argv:
            write_state(state, {"consecutive_errors": errors, "last_error": f"{exc.__class__.__name__}: {exc}",
                                "last_error_at": now.isoformat()})
        if out:
            print(out)
        return 0

    models = snap.get("models", [])
    emitted, touched = {}, {}
    for m in models:
        name, level = m["model"], m["level"]
        prev = alerts.get(name) or {}
        prev_level = prev.get("level", "ok")
        last_at = parse_iso(prev.get("at"))
        worse = nan_quota.LEVELS.get(level, 0) > nan_quota.LEVELS.get(prev_level, 0)
        stale = last_at is None or (now - last_at).total_seconds() >= REALERT_H * 3600
        if level != "ok" and (worse or stale):
            touched[name] = {"level": level, "at": now.isoformat()}
            emitted[name] = level
        elif level == "ok":
            touched[name] = {"level": "ok", "at": (last_at.isoformat() if last_at and prev_level == "ok"
                                                   else now.isoformat())}
        else:
            touched[name] = prev or {"level": level, "at": now.isoformat()}

    out = ""
    if emitted:
        snap_for_text = dict(snap)
        snap_for_text["models"] = [m for m in models if m["model"] in emitted]
        out = nan_quota.human_alert(snap_for_text)

    if "--force" in argv and not out:
        worst = snap.get("worst_level", "ok")
        head = {"red": "🔴", "amber": "🟠", "ok": "✅"}[worst]
        tail = {"red": "hay riesgo alto", "amber": "hay un modelo en ámbar", "ok": "sin riesgos"}[worst]
        out = f"{head} **Cuota NaN** — {tail}.\n```\n" + nan_quota.summarize(snap) + "\n```"

    if "--dry" not in argv:
        write_state(snap, {"alerts": touched or alerts, "consecutive_errors": 0, "last_error": None})
    if out:
        print(out)
    log(f"tick ok worst={snap.get('worst_level')} alertas={len(touched)} salida={'sí' if out else 'no'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
