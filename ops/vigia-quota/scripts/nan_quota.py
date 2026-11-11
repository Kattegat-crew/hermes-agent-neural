#!/usr/bin/env python3
"""nan_quota — cuota de nan.builders: cliente + modelo de proyección (fuente única).

Extraído y adaptado del enfoque del repo prgr1no/gnome-nan-usage:
  - La alerta es POR CONSECUENCIA, no por porcentaje: ámbar si al ritmo medio del
    periodo la cuota proyecta >= 75% al reset; rojo si a ese ritmo se agota antes
    del reset dejando bloqueado al menos el 10% del periodo.
  - Si ha transcurrido < 5% del periodo no se extrapola (la media es ruido).

Rutas usadas (SIN contrato público — degradar en silencio si cambian):
  GET https://cloud-api.nan.builders/api/usage/quota
  GET https://cloud-api.nan.builders/api/auth/me

Usado por: scripts/nan_quota_watch.py (cron) y
plugins/nan-usage/dashboard/plugin_api.py (chip del Desktop).
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import re
import sys
import urllib.error
import urllib.request

API = "https://cloud-api.nan.builders"
UA = "Mozilla/5.0 (X11; Linux x86_64) hermes-nan-usage/1.0"

# Umbrales (mismos criterios que la extensión de referencia)
AMBER_RATIO = 0.75        # proyección al reset >= 75% del cap -> ámbar
MIN_ELAPSED = 0.05        # <5% del periodo transcurrido: no extrapolar
RED_BLOCK_RATIO = 0.10    # rojo si el bloqueo estimado >= 10% del periodo
LEVELS = {"ok": 0, "amber": 1, "red": 2}

DEFAULT_CONFIG = os.environ.get("HERMES_HOME", "/root/hermes-agent-legacy-docker/data") + "/config.yaml"


# --------------------------------------------------------------------------- key
def load_key(config_path: str | None = None) -> str:
    """Key de NaN: env -> config.yaml (providers.NaN-Builders.api_key) -> ~/.config/nan/api-key."""
    for var in ("NAN_API_KEY", "NAN_BUILDERS_API_KEY", "NANBUILDERS_API_KEY"):
        val = os.environ.get(var, "").strip()
        if val:
            return val

    try:  # fuente de secretos del perfil (Bitwarden) — esquema v0.22.x
        sys.path.insert(0, "/opt/hermes-agent")
        from hermes_cli.env_loader import hydrate_profile_secret_sources
        sec = hydrate_profile_secret_sources("/opt/hermes-agent-data")
        for var in ("NAN_API_KEY", "NAN_BUILDERS_API_KEY"):
            val = (sec.get(var) or "").strip()
            if val:
                return val
    except Exception:
        pass

    path = config_path or DEFAULT_CONFIG
    try:
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
        # bloque del proveedor NaN-Builders -> su api_key (sin PyYAML, para el cron)
        block = re.search(r"NaN-Builders:\s*\n((?:[ \t]+.*\n?)+)", text)
        if block:
            m = re.search(r"api_key:\s*[\"']?([^\"'\s]+)", block.group(1))
            if m:
                return m.group(1)
        m = re.search(r"^\s*api_key:\s*[\"']?(sk-[^\"'\s]+)", text, re.M)
        if m:
            return m.group(1)
    except OSError:
        pass

    for cand in (os.path.expanduser("~/.config/nan/api-key"), os.path.expanduser("~/.nan/api-key")):
        try:
            with open(cand, "r", encoding="utf-8") as fh:
                val = fh.read().strip()
            if val:
                return val
        except OSError:
            continue
    raise RuntimeError("no se encontró la API key de NaN (config.yaml / env / ~/.config/nan/api-key)")


# ------------------------------------------------------------------------- http
def _get(path: str, key: str, timeout: float = 20.0) -> dict:
    req = urllib.request.Request(
        API + path,
        headers={"Authorization": f"Bearer {key}", "User-Agent": UA, "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_quota(key: str, timeout: float = 20.0) -> dict:
    return _get("/api/usage/quota", key, timeout)


def fetch_identity(key: str, timeout: float = 20.0) -> dict:
    """handle/tier/region/features. NO devolver tal cual: trae email y discordId."""
    return _get("/api/auth/me", key, timeout)


# ---------------------------------------------------------------------- análise
def _parse_dt(value) -> _dt.datetime | None:
    if not value:
        return None
    txt = str(value).strip().replace("Z", "+00:00")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", txt):
        txt += "T00:00:00+00:00"
    try:
        dt = _dt.datetime.fromisoformat(txt)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=_dt.timezone.utc)


def analyze(quota: dict, now: _dt.datetime | None = None) -> dict:
    """Snapshot por modelo con proyección y nivel. Puro: sin red, sin estado."""
    now = now or _dt.datetime.now(_dt.timezone.utc)
    start = _parse_dt(quota.get("periodStart"))
    models = []
    for m in quota.get("models") or []:
        name = m.get("model") or "?"
        used = int(m.get("tokensUsed") or 0)
        cap = int(m.get("cap") or 0)
        end = _parse_dt(m.get("periodEnd"))
        window_tokens = m.get("fullWindowTokens")
        window_hours = m.get("windowHours")

        entry = {
            "model": name,
            "tokens_used": used,
            "cap": cap,
            "remaining": int(m.get("remaining") or max(cap - used, 0)),
            "updated_at": m.get("updatedAt"),
            "resets_at": end.isoformat() if end else None,
            "pct": round(used / cap * 100, 1) if cap else None,
            "kind": "window" if window_tokens else "period",
            # Packs de créditos comprados: NaN los reporta en tokens (extraTokens)
            # y sólo son consumibles si extraUsable no es False.
            "extra_tokens": int(m.get("extraTokens") or 0),
            "extra_usable": m.get("extraUsable"),
            "level": "ok",
            "projected_pct": None,
            "projected_tokens": None,
            "blocked_ratio": None,
            "note": None,
        }

        if window_tokens:
            # Ventana móvil (p.ej. 400M tokens / 4h): sólo porcentaje, sin proyección.
            eff = int(window_tokens)
            entry["window_tokens"] = eff
            entry["window_hours"] = window_hours
            entry["pct"] = round(used / eff * 100, 1) if eff else None
            if entry["pct"] is not None and entry["pct"] >= AMBER_RATIO * 100:
                entry["level"] = "amber"
                entry["note"] = f"ventana de {window_hours}h al {entry['pct']}%"
            models.append(entry)
            continue

        if not cap or not start or not end or end <= start:
            models.append(entry)
            continue

        total_s = (end - start).total_seconds()
        elapsed_s = (now - start).total_seconds()
        elapsed = max(0.0, min(1.0, elapsed_s / total_s))
        entry["elapsed_pct"] = round(elapsed * 100, 1)
        entry["days_to_reset"] = round(max((end - now).total_seconds(), 0) / 86400, 1)

        if elapsed < MIN_ELAPSED:
            entry["note"] = "periodo recién empezado: sin extrapolación"
            models.append(entry)
            continue

        projected = used / elapsed
        entry["projected_tokens"] = int(projected)
        entry["projected_pct"] = round(projected / cap * 100, 1)
        if entry["projected_pct"] >= AMBER_RATIO * 100:
            entry["level"] = "amber"
        if projected >= cap and used > 0:
            rate = used / max(elapsed_s, 1.0)          # tokens/s
            exhaust_s = (cap - used) / rate if rate else total_s
            blocked = (end - (now + _dt.timedelta(seconds=exhaust_s))).total_seconds()
            entry["blocked_ratio"] = round(blocked / total_s, 3)
            if blocked / total_s >= RED_BLOCK_RATIO:
                entry["level"] = "red"
                entry["note"] = f"se agotaría y quedaría bloqueado ~{blocked/86400:.0f} días"
            else:
                entry["note"] = "proyecta agotar la cuota antes del reset (bloqueo corto)"
        models.append(entry)

    models.sort(key=lambda e: (-LEVELS.get(e["level"], 0), -(e.get("projected_pct") or e.get("pct") or 0)))
    worst = next((m for m in models if m["level"] != "ok"), None)
    return {
        "generated_at": now.isoformat(),
        "period_start": start.isoformat() if start else quota.get("periodStart"),
        "period_end": next((m["resets_at"] for m in models if m["resets_at"]), None),
        "worst_level": worst["level"] if worst else "ok",
        "worst_model": worst["model"] if worst else None,
        "models": models,
    }


def to_snapshot(quota: dict, now: _dt.datetime | None = None) -> dict:
    """analyze() + metadatos de cuenta SIN datos personales."""
    snap = analyze(quota, now)
    snap["ok"] = True
    return snap


def human_alert(snap: dict) -> str:
    """Texto de alerta para los modelos en ámbar/rojo (vacío si todo ok)."""
    bad = [m for m in snap.get("models", []) if m.get("level") in ("amber", "red")]
    if not bad:
        return ""
    icon = {"amber": "🟠", "red": "🔴"}
    lines = []
    worst = "red" if any(m["level"] == "red" for m in bad) else "amber"
    lines.append(f"{icon[worst]} **Cuota NaN** — {len(bad)} modelo(s) en riesgo "
                 f"(periodo hasta {str(snap.get('period_end'))[:10]})")
    for m in bad[:6]:
        pct = m.get("pct")
        proj = m.get("projected_pct")
        tail = f"· proyección {proj}%" if proj is not None else ""
        reset = f"· reset en {m['days_to_reset']}d" if m.get("days_to_reset") is not None else ""
        lines.append(f"{icon[m['level']]} `{m['model']}` {pct}% ({m['tokens_used']/1e6:.0f}M/"
                     f"{m['cap']/1e6:.0f}M) {tail} {reset}".strip())
        if m.get("note"):
            lines.append(f"   └ {m['note']}")
    return "\n".join(lines)


def summarize(snap: dict) -> str:
    rows = []
    for m in snap.get("models", []):
        pct = m.get("pct")
        proj = m.get("projected_pct")
        rows.append(f"{m['level']:5} {m['model']:20} {pct if pct is not None else '-':>6}%"
                    + (f"  proy {proj:>6}%" if proj is not None else "")
                    + (f"  reset {m['days_to_reset']}d" if m.get("days_to_reset") is not None else ""))
    return "\n".join(rows)


if __name__ == "__main__":  # diagnóstico manual: python3 nan_quota.py
    key = load_key()
    snap = to_snapshot(fetch_quota(key))
    print(summarize(snap))
    alert = human_alert(snap)
    print("\n" + (alert or "sin alertas"))
