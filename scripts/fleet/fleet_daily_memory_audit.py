#!/usr/bin/env python3
"""fleet_daily_memory_audit.py — audita que TODOS los perfiles guarden memoria y roten sesión.

Por qué existe: el 9-nov-2026 una pausa de emergencia dejó 19 crons congelados y solo dos
perfiles tenían reset de sesión real; el resto acumulaba conversaciones de semanas (Roshi
llegó a 38,9 días) y cada turno re-leía contexto viejo. Esta auditoría convierte ese estado
en un chequeo repetible en vez de una inspección manual.

Para cada perfil comprueba tres cosas:
  1. ``session_reset`` declarado en el config (mode timed) — sin esto el plugin no tiene qué aplicar.
  2. plugin ``hermes-session-reset-policy`` habilitado — desde que el core retiró el reset por
     temporizador, el bloque del config es letra muerta sin el plugin.
  3. job ``guardar-diario-memoria`` presente, habilitado y con última corrida ``ok``.

Uso:
    fleet_daily_memory_audit.py                 # audita y resume
    fleet_daily_memory_audit.py --json          # salida máquina
    fleet_daily_memory_audit.py --profiles a,b  # subconjunto

Salida: una línea por perfil con OK / faltantes. Exit 1 si algún perfil tiene huecos.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROFILES_ROOT = Path("/opt/hermes-agent-data/profiles")
EXCLUIR = {"default", "neural-admin-test", "test-onboarding-01"}
JOB = "guardar-diario-memoria"
PLUGIN = "hermes-session-reset-policy"
MODOS_TIMED = {"idle", "daily", "both"}


def perfiles(root: Path, excluir=None) -> list[str]:
    excluir = EXCLUIR if excluir is None else excluir
    if not root.is_dir():
        return []
    nombres = [
        p.name for p in root.iterdir()
        if p.is_dir() and (p / "config.yaml").exists() and p.name not in excluir
    ]
    return sorted(nombres)


def _bloque_session_reset(texto: str) -> dict:
    """Extrae las claves DIRECTAS del bloque top-level ``session_reset``.

    Sin PyYAML a propósito: solo interesan ``mode``/``idle_minutes``/``at_hour`` y el
    parser debe poder mirar configs con comentarios sin reescribirlos.

    Solo se aceptan los hijos de primer nivel (misma indentación que la primera clave
    del bloque): un ``mode:`` anidado más profundo (p. ej. bajo ``notify:``) NO cuenta,
    porque aprobaría un config cuyo ``session_reset`` real no declara ningún modo.

    Limitación conocida y deliberada: las formas no-bloque (``session_reset: {…}``,
    alias ``session_reset: *base`` o anidado bajo ``gateway:``) no se interpretan; se
    reportan como forma no soportada en vez de darse por buenas.
    """
    bloque: dict = {}
    dentro = False
    indent_hijos = None
    for linea in texto.splitlines():
        if not linea.strip() or linea.lstrip().startswith("#"):
            continue
        indent = len(linea) - len(linea.lstrip(" \t"))
        if indent == 0:
            clave, _, resto = linea.partition(":")
            dentro = clave.strip() == "session_reset"
            indent_hijos = None
            if dentro and resto.split("#")[0].strip():
                bloque["_forma"] = resto.split("#")[0].strip()
            continue
        if not dentro:
            continue
        if indent_hijos is None:
            indent_hijos = indent
        if indent != indent_hijos or ":" not in linea:
            continue
        clave, _, valor = linea.partition(":")
        bloque[clave.strip()] = valor.split("#")[0].strip().strip("\"'")
    return bloque


def plugin_habilitado(texto: str) -> bool:
    """``True`` si el plugin aparece en la lista ``plugins.enabled`` del config."""
    dentro = False
    en_enabled = False
    for linea in texto.splitlines():
        limpia = linea.strip()
        if not limpia or limpia.startswith("#"):
            continue
        if not linea.startswith((" ", "\t")):
            dentro = limpia.split(":", 1)[0].strip() == "plugins"
            en_enabled = False
            continue
        if not dentro:
            continue
        if limpia.startswith("enabled:"):
            en_enabled = True
            if PLUGIN in limpia.split(":", 1)[1]:
                return True
            continue
        if limpia.startswith(("disabled:", "entries:")):
            en_enabled = False
            continue
        if en_enabled and limpia.lstrip("- ").strip().strip("\"'") == PLUGIN:
            return True
    return False


def estado_job(jobs_json: Path):
    if not jobs_json.exists():
        return None
    try:
        data = json.loads(jobs_json.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    lista = (data.get("jobs") if isinstance(data, dict) else data) or []
    if not isinstance(lista, list):
        return None
    return next((j for j in lista if isinstance(j, dict) and j.get("name") == JOB), None)


def auditar_perfil(root: Path, perfil: str) -> dict:
    cfg = (root / perfil / "config.yaml").read_text(encoding="utf-8", errors="replace")
    reset = _bloque_session_reset(cfg)
    modo = str(reset.get("mode") or "").lower()
    job = estado_job(root / perfil / "cron" / "jobs.json")
    faltantes = []
    if reset.get("_forma"):
        faltantes.append(f"session_reset en forma no soportada ({reset['_forma'][:30]})")
    elif modo not in MODOS_TIMED:
        faltantes.append("session_reset ausente o inerte")
    if not plugin_habilitado(cfg):
        faltantes.append("plugin de reset apagado")
    if job is None:
        faltantes.append("job de memoria ausente")
    elif not job.get("enabled"):
        faltantes.append("job de memoria pausado")
    elif job.get("last_status") not in ("ok", None):
        faltantes.append(f"última corrida {job.get('last_status')}")
    return {
        "perfil": perfil,
        "reset_mode": modo or "—",
        "idle_minutes": reset.get("idle_minutes", "—"),
        "plugin": plugin_habilitado(cfg),
        "job": bool(job),
        "job_enabled": bool(job and job.get("enabled")),
        "job_last_status": (job or {}).get("last_status"),
        "job_last_run": (job or {}).get("last_run_at"),
        "faltantes": faltantes,
        "ok": not faltantes,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(PROFILES_ROOT))
    ap.add_argument("--profiles", default="")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    root = Path(args.root)
    lista = [p.strip() for p in args.profiles.split(",") if p.strip()] or perfiles(root)
    resultados = [auditar_perfil(root, p) for p in lista if (root / p / "config.yaml").exists()]
    if not resultados:
        print(f"❌ sin perfiles que auditar en {root} (¿ruta o nombres mal escritos?)")
        return 2
    if args.json:
        print(json.dumps(resultados, ensure_ascii=False, indent=1))
    else:
        for r in resultados:
            estado = "OK  " if r["ok"] else "HUECO"
            extra = "" if r["ok"] else " · " + ", ".join(r["faltantes"])
            print(
                f"{estado} {r['perfil']:10s} reset={r['reset_mode']:5s} "
                f"idle={r['idle_minutes']:>4} plugin={'sí' if r['plugin'] else 'no':2s} "
                f"job={'sí' if r['job_enabled'] else 'no':2s} "
                f"último={r['job_last_status'] or '—'}{extra}"
            )
        huecos = [r for r in resultados if not r["ok"]]
        print(f"\n{len(resultados) - len(huecos)}/{len(resultados)} perfiles completos")
    return 0 if all(r["ok"] for r in resultados) else 1


if __name__ == "__main__":
    sys.exit(main())
