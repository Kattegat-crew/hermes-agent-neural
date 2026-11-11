#!/usr/bin/env python3
"""quota_digest — informe de cuotas de suscripciones para el cron de Vigía.

Dos veces al día resume OpenCode Go, Codex, Antigravity y NaN (nan.builders)
con la granularidad correcta de cada proveedor:

  * Codex / OpenCode Go / Antigravity : ventanas de cuota (5 h, semanal, mensual)
    leídas del quota_cache.json que escribe el plugin `quota`.
  * NaN (nan.builders)                : uso por modelo en tokens (usado/cap,
    proyección al reset y packs `extraTokens`) desde /api/usage/quota.

NaN NO expone % de créditos del plan ni saldo de packs con API key: ese endpoint
(/api/usage/credits) exige cookie de sesión del dashboard y responde 401
session_required. Hasta que exista una cookie válida el informe declara esa
limitación en vez de inventar un porcentaje.

Uso:
  python3 quota_digest.py              # informe a stdout (lo que corre el cron)
  python3 quota_digest.py --json       # datos normalizados, sin formatear
  python3 quota_digest.py --no-refresh # no intenta refrescar quota_cache.json
"""
from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys
import urllib.error as _urlerr
from pathlib import Path

HOME = Path(os.environ.get("HERMES_HOME") or "/opt/hermes-agent-data")
QUOTA_CACHE = HOME / "quota_cache.json"
SCRIPTS = HOME / "scripts"

# Nombres tal y como los reconoce el humano.
SUBS = [
    ("opencode-go", "OpenCode Go"),
    ("openai-codex", "Codex"),
    ("antigravity", "Antigravity"),
]

TARGET_TZ = dt.timezone(dt.timedelta(hours=-5))  # America/Bogota
CACHE_MAX_AGE_S = 1800  # 30 min: más viejo que esto se refresca antes de leer
MAX_NAN_ROWS = 10  # Discord corta a 2000 chars: no listar 20+ modelos seguidos


# ------------------------------------------------------------------ utilidades
def _parse_iso(value):
    if not value:
        return None
    try:
        text = str(value).replace("Z", "+00:00")
        when = dt.datetime.fromisoformat(text)
    except ValueError:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=dt.timezone.utc)
    return when


def _fmt_reset(value, now=None):
    """'hoy 13:02' / 'mañana 23:15' / '16-nov 19:00', en hora de Bogotá."""
    when = _parse_iso(value)
    if when is None:
        return "sin reset"
    now = now or dt.datetime.now(dt.timezone.utc)
    local = when.astimezone(TARGET_TZ)
    today = now.astimezone(TARGET_TZ).date()
    delta = (local.date() - today).days
    if delta == 0:
        return f"hoy {local:%H:%M}"
    if delta == 1:
        return f"mañana {local:%H:%M}"
    return f"{local:%d-%b} {local:%H:%M}".replace(".", "")


def _fmt_tokens(n):
    n = int(n or 0)
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.2f}B"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.0f}M"
    if n >= 1_000:
        return f"{n / 1_000:.0f}k"
    return str(n)


def _fmt_credits(n):
    """Créditos: miles con punto y un decimal cuando son pocos."""
    try:
        v = float(n or 0)
    except (TypeError, ValueError):
        return "—"
    if v >= 100:
        return f"{v:,.0f}".replace(",", ".")
    return f"{v:.1f}"


def cache_age_seconds():
    try:
        return dt.datetime.now().timestamp() - QUOTA_CACHE.stat().st_mtime
    except OSError:
        return None


def refresh_cache():
    """Pide al CLI de Hermes el refresco (hidrata secrets que un script suelto no ve)."""
    env = dict(os.environ, HERMES_HOME=str(HOME))
    try:
        subprocess.run(
            ["hermes", "quota", "refresh"],
            capture_output=True,
            timeout=90,
            env=env,
            check=False,
        )
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def read_cache():
    try:
        return json.loads(QUOTA_CACHE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


# --------------------------------------------------------- suscripciones (quota)
def subscription_rows(cache):
    """Normaliza las ventanas de cada suscripción desde quota_cache.json."""
    providers = (cache or {}).get("providers") or {}
    rows = []
    for pid, label in SUBS:
        rec = providers.get(pid)
        if rec is None:
            rows.append({"id": pid, "label": label, "state": "missing", "windows": [], "details": []})
            continue
        windows = [
            {
                "label": w.get("label") or "ventana",
                "used_percent": w.get("used_percent"),
                "reset_at": w.get("reset_at"),
            }
            for w in (rec.get("windows") or [])
        ]
        rows.append(
            {
                "id": pid,
                "label": label,
                "plan": rec.get("plan"),
                "account": rec.get("account_label"),
                "unavailable_reason": rec.get("unavailable_reason"),
                "state": "unavailable" if rec.get("unavailable_reason") else "ok",
                "windows": windows,
                "details": list(rec.get("details") or []),
            }
        )
    return rows


def _worst_level(used_percent):
    if not isinstance(used_percent, (int, float)):
        return "ok"
    if used_percent >= 95:
        return "red"
    if used_percent >= 80:
        return "amber"
    return "ok"


# ------------------------------------------------------------------------ NaN
def nan_summary():
    """Snapshot de NaN: créditos si hay sesión, si no uso por modelo en tokens."""
    sys.path.insert(0, str(SCRIPTS))
    try:
        import nan_quota  # noqa: E402
    except Exception as exc:  # pragma: no cover - import roto no debe romper el cron
        return {"state": "error", "reason": f"nan_quota no importable: {exc}"}

    try:
        key = nan_quota.load_key(str(HOME / "config.yaml"))
        quota = nan_quota.fetch_quota(key)
        snap = nan_quota.analyze(quota)
    except Exception as exc:
        return {"state": "error", "reason": f"{type(exc).__name__}: {exc}"}

    models = []
    for m in snap.get("models") or []:
        models.append(
            {
                "model": m.get("model"),
                "pct": m.get("pct"),
                "tokens_used": m.get("tokens_used"),
                "cap": m.get("cap"),
                "kind": m.get("kind"),
                "level": m.get("level"),
                "projected_pct": m.get("projected_pct"),
                "days_to_reset": m.get("days_to_reset"),
                "note": m.get("note"),
                "pack_tokens": m.get("extra_tokens") or 0,
                # Resets: el de periodo (snapshot) y el propio de una ventana móvil.
                "resets_at": m.get("resets_at"),
                "period_resets_at": snap.get("period_end"),
            }
        )

    # Créditos del plan: solo con la cookie del dashboard (la API key da 401).
    credits = None
    credits_state = "sin_sesion"
    credits_reason = "no hay sesión guardada (magic link al correo)"
    session_days = None
    try:
        meta = nan_quota.session_meta()
        cookie = meta.get("cookie")
        if cookie:
            exp = _parse_iso(meta.get("expires_iso"))
            if exp is not None:
                session_days = (exp - dt.datetime.now(dt.timezone.utc)).days
            try:
                credits = nan_quota.credits_summary(nan_quota.fetch_credits(cookie))
                credits_state = "ok"
                credits_reason = ""
            except _urlerr.HTTPError as exc:
                if exc.code in (401, 403):
                    credits_state = "sesion_caducada"
                    credits_reason = f"sesión caducada (HTTP {exc.code}): regenerar magic link"
                else:
                    credits_state = "error"
                    credits_reason = f"HTTP {exc.code} al leer créditos"
            except Exception as exc:  # red, timeout, JSON raro
                credits_state = "error"
                credits_reason = f"{type(exc).__name__} leyendo créditos"
    except Exception as exc:  # pragma: no cover - nan_quota roto ya se filtró arriba
        credits_state = "error"
        credits_reason = f"{type(exc).__name__} inicializando sesión"

    return {
        "state": "ok",
        "credits_available": credits_state == "ok",
        "credits_state": credits_state,
        "credits_reason": credits_reason,
        "credits": credits,
        "session_days": session_days,
        "worst_level": snap.get("worst_level"),
        "worst_model": snap.get("worst_model"),
        "period_end": snap.get("period_end"),
        "models": models,
    }


# ------------------------------------------------------------------- informe
ICON = {"ok": "·", "amber": "!", "red": "X", "unavailable": "–", "missing": "?"}


def render(subs, nan, fetched_at, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    lines = ["**Cuotas de suscripciones**", ""]

    for row in subs:
        head = f"**{row['label']}**"
        if row.get("plan"):
            head += f" · {row['plan']}"
        if row.get("account"):
            head += f" · {row['account']}"
        if row["state"] == "unavailable":
            lines.append(f"{head} — no disponible ({row['unavailable_reason']})")
            continue
        if row["state"] == "missing":
            lines.append(f"{head} — sin datos en el cache")
            continue
        lines.append(head)
        for w in row["windows"]:
            pct = w.get("used_percent")
            if isinstance(pct, (int, float)):
                used = f"{float(pct):.0f}% usado"
            else:
                used = "—"
            lines.append(f"  {ICON[_worst_level(pct)]} {w['label']}: {used} · reset {_fmt_reset(w['reset_at'], now)}")
        for d in row["details"][:2]:
            lines.append(f"  · {d}")
        lines.append("")

    lines.append("**NaN (nan.builders)**")
    if nan.get("state") != "ok":
        lines.append(f"  no disponible ({nan.get('reason')})")
    else:
        credits = nan.get("credits") or {}
        if credits:
            pct = credits.get("pct")
            pct_txt = "—" if pct is None else f"{pct}%"
            left = ""
            if credits.get("remaining") is not None:
                left = f" · quedan {_fmt_credits(credits['remaining'])}"
            lines.append(
                f"  {ICON[_worst_level(pct)]} Plan: {_fmt_credits(credits.get('used'))}"
                f"/{_fmt_credits(credits.get('allowance'))} cr ({pct_txt}){left}"
                f" · reset {_fmt_reset(credits.get('period_end'), now)}"
            )
            if credits.get("pack_credits"):
                exp = credits.get("pack_expires_at")
                exp_txt = f" · caduca {_fmt_reset(exp, now)}" if exp else ""
                lines.append(f"  · Pack: {_fmt_credits(credits['pack_credits'])} cr{exp_txt}")
            flags = [
                txt
                for txt, on in (("congelado", credits.get("frozen")), ("frontier en pausa", credits.get("frontier_paused")))
                if on
            ]
            if flags:
                lines.append(f"  ! {' · '.join(flags)}")
            days = nan.get("session_days")
            if isinstance(days, int) and days <= 4:
                lines.append(f"  ! sesión NaN caduca en {days} día{'s' if days != 1 else ''}: regenerar magic link")
        cred_by_model = {m.get("model"): m for m in credits.get("models") or []}
        all_models = nan["models"]
        shown = all_models[:MAX_NAN_ROWS]
        for m in shown:
            if m.get("kind") == "window":
                pct = m.get("pct")
                pct_txt = "—" if not isinstance(pct, (int, float)) else f"{pct}%"
                lines.append(
                    f"  {ICON.get(m['level'], '·')} {m['model']}: {pct_txt} de la ventana "
                    f"(reset {_fmt_reset(_nan_reset(m, nan), now)})"
                )
                continue
            pct = "—" if m.get("pct") is None else f"{m['pct']}%"
            extra = ""
            if m.get("pack_tokens"):
                extra = f" · pack {_fmt_tokens(m['pack_tokens'])}"
            proj = ""
            if m.get("projected_pct") is not None:
                proj = f" · proy. {m['projected_pct']}% al reset"
            tokens = f"({_fmt_tokens(m.get('tokens_used'))}/{_fmt_tokens(m.get('cap'))}{extra})"
            cred = ""
            cm = cred_by_model.get(m["model"])
            if cm and cm.get("credits"):
                cred = f" · {cm['credits']:.1f} cr"
            lines.append(f"  {ICON.get(m['level'], '·')} {m['model']}: {pct} {tokens}{proj}{cred}")
        if nan.get("worst_level") != "ok":
            lines.append(f"  → en riesgo: {nan.get('worst_model')} ({nan['worst_level']})")
        hidden = len(all_models) - len(shown)
        if hidden > 0:
            lines.append(f"  …y {hidden} modelo{'s' if hidden != 1 else ''} más")
        if nan.get("credits_state") != "ok":
            reason = nan.get("credits_reason") or "no disponibles"
            lines.append(f"  · créditos: {reason}")

    age = cache_age_seconds()
    stamp = "?" if fetched_at is None else _fmt_reset(fetched_at, now)
    age_txt = "cache desconocido" if age is None else f"cache {int(age // 60)} min"
    lines.append("")
    lines.append(f"-# datos: {stamp} · {age_txt}")
    return "\n".join(lines)


def _nan_reset(model_row, nan):
    """Reset de una fila NaN.

    Los modelos de periodo comparten el `period_resets_at` del snapshot; los de
    ventana móvil (p.ej. 4 h) traen su propio `resets_at`.
    """
    if model_row.get("kind") == "window" and model_row.get("resets_at"):
        return model_row["resets_at"]
    # Cada modelo de periodo trae su propio periodEnd; `period_resets_at` es el
    # del snapshot y puede venir contaminado por una ventana móvil (analyze toma
    # el periodEnd del primer modelo), así que sólo es respaldo.
    return model_row.get("resets_at") or model_row.get("period_resets_at") or nan.get("period_end")


def build(refresh=True):
    if refresh and (cache_age_seconds() is None or cache_age_seconds() > CACHE_MAX_AGE_S):
        refresh_cache()
    cache = read_cache()
    subs = subscription_rows(cache)
    nan = nan_summary()
    return subs, nan, cache.get("fetched_at")


def main(argv):
    if "--json" in argv:
        subs, nan, fetched_at = build(refresh="--no-refresh" not in argv)
        print(json.dumps({"subscriptions": subs, "nan": nan, "fetched_at": fetched_at}, ensure_ascii=False, indent=1, default=str))
        return 0
    subs, nan, fetched_at = build(refresh="--no-refresh" not in argv)
    print(render(subs, nan, fetched_at))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
