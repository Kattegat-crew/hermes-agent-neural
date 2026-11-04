#!/usr/bin/env python3
"""
Watchdog de fallback para crons — escanea jobs.json de todos los perfiles y
re-ejecuta jobs fallidos vía proveedor alternativo (OpenCode-Go API).

Caso de uso (validado 26/08): un cron muerto sin error útil (drift_skip,
permisos, 429) deja `failure_streak >= 2` o `last_status != ok`. Este watchdog
(programado como cron no_agent cada ~30 min en el perfil de sistema) detecta el
job y re-ejecuta su `prompt` mediante una llamada HTTP al fallback, escribiendo
estado.json por si Vigía lo lee.

Advertencia honesta: la llamada a LLM vía API produce TEXTO, NO ejecuta las
herramientas de Hermes. Util para jobs que generan reportes/avisos; para jobs de
memoria/herramientas la protección real es pin del job + cascada de providers +
fix de permisos del runner.

Uso:
  python3 fallback_watchdog.py [--dry-run] [--model mimo-v2.5]
  (requiere OPENCODE_GO_API_KEY en env, o lee el provider del config del perfil)

Salida: líneas por job; exit 0 siempre (no romper el cron que lo dispara).
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROFILES = ["comms", "bragi", "sindri", "freyja", "vili", "ullr", "heimdall",
            "hermodr", "brokkr", "roshi", "vigia", "default"]
BASE_DIRS = [Path("/opt/data/profiles"), Path("/root/hermes-agent-legacy-docker/data/profiles")]
WRAPPER = Path("/opt/data/scripts/hermes-fallback-opencode-api.py")
THRESHOLD_STREAK = 2
KEY = os.environ.get("OPENCODE_GO_API_KEY", "")


def _iter_jobs():
    seen = set()
    for prof in PROFILES:
        for base in BASE_DIRS:
            jf = base / prof / "cron" / "jobs.json"
            if not jf.exists():
                continue
            if str(jf) in seen:
                continue
            seen.add(str(jf))
            try:
                d = json.loads(jf.read_text(encoding="utf-8"))
            except Exception:
                continue
            jobs = d.get("jobs", d) if isinstance(d, dict) else d
            jobs = jobs if isinstance(jobs, list) else list(jobs.values())
            for j in jobs:
                if isinstance(j, dict):
                    yield prof, jf, j


def _is_failed(job):
    if job.get("enabled") is False:
        return False
    if job.get("last_status") in ("ok", None):
        return False
    return (job.get("failure_streak") or 0) >= THRESHOLD_STREAK


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--model", default="mimo-v2.5")
    args = parser.parse_args()

    print(f"[{datetime.now(timezone.utc).isoformat(timespec='seconds')}] Watchdog fallback — escaneando jobs ...")
    failed = [(prof, name, job) for prof, _jf, job in _iter_jobs()
              if _is_failed(job) for name in [job.get("name") or "?"]]

    if not failed:
        print("  Ningún job fallido (todos ok o sin ejecutar aún).")
        return 0

    print(f"  {len(failed)} job(s) fallido(s):")
    for prof, name, job in failed:
        print(f"    - {prof}/{name} (streak={job.get('failure_streak')}, last={job.get('last_status')})")
        if args.dry_run:
            continue
        prompt = job.get("prompt") or ""
        if not prompt:
            print("      (sin prompt, salto)")
            continue
        env = dict(os.environ)
        if KEY:
            env["OPENCODE_GO_API_KEY"] = KEY
        cmd = [sys.executable, str(WRAPPER), prompt, "--model", args.model]
        print(f"      → ejecutando fallback vía OpenCode-Go/{args.model} ...")
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=180, env=env)
            tail = (res.stdout or res.stderr or "")[-500:]
            print(f"      exit={res.returncode} | {tail[:200]}")
        except Exception as e:
            print(f"      error lanzando fallback: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())