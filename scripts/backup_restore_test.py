#!/usr/bin/env python3
"""
Prueba de RESTAURACIÓN del respaldo (semanal).

Un respaldo del que no se ha restaurado nunca no es un respaldo: es una esperanza.
Este script toma el snapshot más reciente, **restaura una muestra real** a un directorio
temporal y verifica que el contenido sirve:

  - el fichero existe y no está vacío,
  - los `.yaml`/`.yml` parsean,
  - las bases de datos SQLite pasan `PRAGMA integrity_check`.

No toca nada del sistema: restaura a un temporal y lo borra al terminar.

Uso:
    backup_restore_test.py [--origen local|offsite|ambos] [--conservar]
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path("/opt/hermes-agent")          # repo de codigo: docs/ de la declaracion
DATA = Path("/opt/hermes-agent-data")     # estado nativo (F6, 29-sep-2026)
DECLARACION = RAIZ / "docs/ops/backup-sources.yaml"
ESTADO = DATA / "state/backup-restore-test.json"

# Muestra: un config, un secreto, un código, memorias y dos bases SQLite
MUESTRA = [
    "/opt/hermes-agent-data/config.yaml",
    "/opt/hermes-agent-data/.env",
    "/opt/hermes-agent-data/kanban.db",
    "/opt/hermes-agent-data/verification_evidence.db",
    "/opt/hermes-agent-data/profiles/roshi/memories/MEMORY.md",
    "/opt/hermes-agent-data/scripts/vps_master_backup.py",
]


def log(m: str) -> None:
    print(m, flush=True)


def restic(repo: str, llave: Path, args: list, timeout: int = 900) -> subprocess.CompletedProcess:
    entorno = dict(os.environ, RESTIC_PASSWORD_FILE=str(llave))
    try:
        return subprocess.run(["restic", "-r", repo, *args], capture_output=True,
                              text=True, env=entorno, timeout=timeout)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(args, 124, "", f"timeout tras {timeout}s")


def verificar(ruta: Path) -> tuple[bool, str]:
    if not ruta.exists():
        return False, "no se restauró"
    if ruta.stat().st_size == 0:
        return False, "vacío"
    sufijo = ruta.suffix.lower()
    if sufijo in (".yaml", ".yml"):
        try:
            import yaml
            yaml.safe_load(ruta.read_text(encoding="utf-8"))
            return True, f"YAML válido · {ruta.stat().st_size} B"
        except Exception as e:
            return False, f"YAML ilegible: {e}"
    if sufijo == ".db":
        try:
            con = sqlite3.connect(f"file:{ruta}?mode=ro", uri=True)
            res = con.execute("PRAGMA integrity_check").fetchone()[0]
            con.close()
            return (res == "ok"), f"SQLite integrity_check={res} · {ruta.stat().st_size // 1024} KB"
        except Exception as e:
            return False, f"SQLite ilegible: {e}"
    return True, f"{ruta.stat().st_size} B"


def probar(origen: str, repo: str, llave: Path, conservar: bool) -> dict:
    log(f"\n--- origen {origen}: {repo}")
    snaps = restic(repo, llave, ["snapshots", "--json"], timeout=300)
    if snaps.returncode != 0:
        return {"origen": origen, "ok": False,
                "error": (snaps.stderr or snaps.stdout or "inaccesible").strip()[:250]}
    try:
        lista = json.loads(snaps.stdout or "[]")
    except json.JSONDecodeError:
        return {"origen": origen, "ok": False, "error": "snapshots ilegible"}
    if not lista:
        return {"origen": origen, "ok": False, "error": "sin snapshots"}
    ultimo = lista[-1]

    temporal = Path(tempfile.mkdtemp(prefix=f"restore-test-{origen}-"))
    cmd = ["restore", ultimo["short_id"], "--target", str(temporal)]
    for p in MUESTRA:
        cmd += ["--include", p]
    r = restic(repo, llave, cmd, timeout=1200)
    if r.returncode != 0:
        return {"origen": origen, "ok": False, "snapshot": ultimo["short_id"],
                "error": (r.stderr or r.stdout)[-300:]}

    resultados, todos_ok = [], True
    for p in MUESTRA:
        destino = temporal / p.lstrip("/")
        ok, detalle = verificar(destino)
        todos_ok = todos_ok and ok
        resultados.append({"ruta": p, "ok": ok, "detalle": detalle})
        log(f"    {'OK  ' if ok else 'FALLO'} {p} -> {detalle}")

    if not conservar:
        shutil.rmtree(temporal, ignore_errors=True)
    else:
        log(f"    (conservado en {temporal})")

    return {"origen": origen, "ok": todos_ok, "snapshot": ultimo["short_id"],
            "hora_snapshot": ultimo.get("time"), "muestra": resultados,
            "archivos_probados": len(MUESTRA)}


def main() -> int:
    p = argparse.ArgumentParser(description="Prueba de restauración del respaldo")
    p.add_argument("--origen", choices=["local", "offsite", "ambos"], default="ambos")
    p.add_argument("--conservar", action="store_true", help="no borrar el temporal")
    args = p.parse_args()

    import yaml
    dev = yaml.safe_load(DECLARACION.read_text(encoding="utf-8")).get("dev", {})
    llave = Path(dev.get("llave", str(DATA / "backup-keys/master-backup.key")))

    log("=== PRUEBA DE RESTAURACIÓN ===")
    log("(un respaldo no probado es una esperanza, no un respaldo)")

    objetivos = []
    if args.origen in ("local", "ambos"):
        objetivos.append(("local", dev.get("repo_local", "/root/hermes-backups/restic-local")))
    if args.origen in ("offsite", "ambos"):
        objetivos.append(("offsite", dev.get("repo_offsite", "rclone:onedrive:Backups/.250")))

    pruebas = [probar(nombre, repo, llave, args.conservar) for nombre, repo in objetivos]
    ok_global = any(x.get("ok") for x in pruebas)

    estado = {"fecha": datetime.now(timezone.utc).isoformat(), "pruebas": pruebas,
              "ok_global": ok_global}
    ESTADO.parent.mkdir(parents=True, exist_ok=True)
    ESTADO.write_text(json.dumps(estado, indent=2, ensure_ascii=False), encoding="utf-8")

    log("\n=== RESUMEN ===")
    for x in pruebas:
        log(f"  {x['origen']:<8} {'RESTAURA OK' if x.get('ok') else 'FALLA'} "
            + (f"· snapshot {x.get('snapshot')}" if x.get("snapshot") else "")
            + (f"· {x.get('error')}" if x.get("error") else ""))
    log("  (basta con que UNA capa restaure para no estar vendido: " + ("sí" if ok_global else "NO") + ")")
    return 0 if ok_global else 1


if __name__ == "__main__":
    sys.exit(main())
