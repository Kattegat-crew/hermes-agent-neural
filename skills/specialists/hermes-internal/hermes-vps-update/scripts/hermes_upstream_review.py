#!/usr/bin/env python3
"""hermes_upstream_review.py — Estudio semanal de actualizaciones de Hermes.

Compara el repo oficial (NousResearch/hermes-agent) contra NUESTRO fork local,
mide el riesgo real de actualizar (solape de archivos + parches propios que no
existen upstream) y emite un informe de decisión en markdown (<=1900 chars,
listo para un mensaje de Discord; el detalle completo va a /opt/data/logs).

Uso: python3 hermes_upstream_review.py [--verbose]
Requiere: /opt/hermes-agent con remoto 'upstream' y tags fetcheados.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime

REPO = "/opt/hermes-agent"
UPSTREAM = "upstream"

# Features propias que NO deben perderse en una actualización.
SIGNATURE_FEATURES = [
    ("DSML guard", "DSML"),
    ("glm5.3-flash context", "glm5.3-flash"),
    ("Memoria on-demand", "index_char_limit"),
    ("Heartbeat efímero", "ephemeral progress"),
    ("Frenos Telegram", "flood brake"),
    ("Config Shield", "lock_default_in_config"),
    ("skill_route", "skill_route"),
]

SKIP_PREFIXES = ("skills/", "docs/", "tests/", ".agents/", ".specs/", ".claude/", "ops/")


def run(*args, timeout=300):
    try:
        r = subprocess.run(args, cwd=REPO, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except (subprocess.SubprocessError, OSError) as exc:
        return 1, "", str(exc)


def git(*a, **k):
    return run("git", *a, **k)


def sh(cmd):
    try:
        return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60).stdout.strip()
    except (subprocess.SubprocessError, OSError):
        return ""


def semver(tag):
    """Solo tags v0.X.Y (los v2026.M.D son tags de fecha del repo, no versiones)."""
    m = re.fullmatch(r"v0\.(\d+)\.(\d+)", tag)
    return (int(m.group(1)), int(m.group(2))) if m else None


def main():
    verbose = "--verbose" in sys.argv
    now = datetime.now()
    short = []

    _, branch, _ = git("branch", "--show-current")
    _, head, _ = git("log", "-1", "--format=%h|%s")
    _, dirty, _ = git("status", "--porcelain")
    dirty_n = len([x for x in dirty.splitlines() if x.strip()])
    health = sh("curl -s --max-time 3 http://127.0.0.1:9112/api/health")
    try:
        serving = (json.loads(health).get("commit") or "")[:12]
    except ValueError:
        serving = ""

    git("fetch", UPSTREAM, "--tags", "--prune", timeout=240)
    _, tags_raw, _ = git("tag", "--list", "v*")
    parsed = sorted((semver(t), t) for t in tags_raw.splitlines() if semver(t))
    if not parsed:
        print("⚠️ Estudio semanal de Hermes: no pude leer tags upstream (red/credenciales).")
        return
    newest = parsed[-1][1]
    prev = parsed[-2][1] if len(parsed) > 1 else None

    _, base, _ = git("describe", "--tags", "--abbrev=0", "HEAD")
    _, mb, _ = git("merge-base", "HEAD", f"{UPSTREAM}/main")
    behind = int(git("rev-list", "--count", f"HEAD..{newest}")[1] or 0)
    ahead = int(git("rev-list", "--count", f"{mb}..HEAD")[1] or 0)
    between = int(git("rev-list", "--count", f"{prev}..{newest}")[1] or 0) if prev else 0
    newest_date = git("log", "-1", "--format=%cs", newest)[1]

    up_files = [f for f in git("diff", "--name-only", f"{mb}..{newest}")[1].splitlines() if f.strip()]
    local_files = [f for f in git("diff", "--name-only", f"{mb}..HEAD")[1].splitlines() if f.strip()]
    overlap = sorted(set(up_files) & set(local_files))
    overlap_code = [f for f in overlap if not f.startswith(SKIP_PREFIXES)]
    local_skills = [f for f in local_files if f.startswith("skills/")]
    code_commits = [x for x in git("log", "--oneline", f"{mb}..HEAD", "--",
                                   "agent", "hermes_cli", "gateway", "tools", "plugins", "cron")[1].splitlines() if x.strip()]
    n_code = len(code_commits)

    ours_only = []
    for label, pat in SIGNATURE_FEATURES:
        hits = [h for h in git("grep", "-l", pat, newest, "--", ":!tests", ":!*.md")[1].splitlines() if h.strip()]
        if not hits:
            ours_only.append(label)

    if behind == 0:
        verdict = f"✅ Sin pendientes: ya estamos en `{newest}`."
    elif len(overlap_code) <= 15 and n_code <= 25:
        verdict = f"🟢 **Actualizar recomendado** a `{newest}` (riesgo bajo)."
    elif len(overlap_code) <= 35:
        verdict = f"🟡 **Actualizar con cuidado** a `{newest}` (riesgo medio)."
    else:
        verdict = f"🔴 **Actualizar solo con plan** a `{newest}` (riesgo alto)."

    short += [
        f"# 📦 Estudio semanal de Hermes — {now.strftime('%d-%b-%Y')}",
        "",
        f"**1) Nosotros:** rama `{branch}` · HEAD `{head.split('|')[0]}` "
        f"({dirty_n} cambios sin commitear) · base `{base or '?'}` · backend sirviendo `{serving or 'n/d'}`",
        "",
        f"**2) Upstream:** última estable `{newest}` ({newest_date})"
        + (f", {between} commits desde `{prev}`" if prev else "")
        + f". **{behind} commits por detrás**; {ahead} propios desde el punto común.",
        "",
        f"**3) Riesgo:** solape en **{len(overlap)} archivos** ({len(overlap_code)} de código). "
        f"Parches propios de código a preservar: **{n_code}**.",
    ]
    if overlap_code:
        short.append("Campos de batalla: " + ", ".join(f"`{f}`" for f in overlap_code[:6])
                     + ("…" if len(overlap_code) > 6 else ""))
    short += [
        "",
        f"**4) Features nuestras:** {len(ours_only)} de {len(SIGNATURE_FEATURES)} no existen upstream "
        f"({', '.join(ours_only) if ours_only else 'ninguna'}).",
        "",
        "**5) Estrategia:** nada de `merge` upstream. Se parte del tag limpio y se re-aplican "
        f"los {n_code} commits propios con `cherry-pick` (rerere activo), se copia nuestro `skills/` "
        f"({len(local_skills)} archivos), tests en puerto canario y cutover con rollback.",
        "",
        f"**6) Veredicto:** {verdict}",
        "",
        f"**7) Autorización:** responde **`AUTORIZO ACTUALIZAR {newest}`** y arranco el replay de "
        "parches + tests; publico aquí el informe final (sha, tests, riesgos). El despliegue va aparte, con segundo OK.",
        "",
        f"-# base común `{mb[:12]}`",
    ]

    text = "\n".join(short if not verbose else short + ["", "```", "\n".join(code_commits), "```"])
    with open("/opt/data/logs/hermes-upstream-review-latest.md", "w") as f:
        f.write(text + "\n")
    print(text)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"⚠️ Estudio semanal de Hermes: fallo al generar el informe: {exc}")
