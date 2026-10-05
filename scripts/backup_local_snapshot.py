#!/usr/bin/env python3
"""
Capa 1 del respaldo: SNAPSHOT LOCAL con restic.

Por qué existe (hallazgo A2, 23-sep-2026): el único destino era OneDrive y su token
caduca cada ~1 h; cuando el refresco falla, el día entero se pierde. Esta capa no
depende de red, ni de tokens, ni de proveedores: escribe a disco local.

Lee las fuentes declaradas de `docs/ops/backup-sources.yaml` (fuente de verdad única).
Además espeja las credenciales que el respaldo off-site excluye (`data/home/**`) a
`data/backups/staging/dumps/_creds/`, que sí está en la lista de Plon: por esa vía
llegan también a OneDrive cuando su token esté vivo.

Uso:
    backup_local_snapshot.py [--ensayo] [--sin-prune] [--sin-espejo]

Salida: una línea de resumen. Exit 0 si el snapshot quedó; !=0 si falló.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path("/opt/hermes-agent")          # repo de codigo: docs/ de la declaracion
DATA = Path("/opt/hermes-agent-data")     # estado nativo (F6, 29-sep-2026)
DECLARACION = RAIZ / "docs/ops/backup-sources.yaml"
ESTADO = DATA / "state/backup-local.json"
STAGING_CREDS = DATA / "backups/staging/dumps/_creds"


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def cargar_declaracion() -> dict:
    try:
        import yaml
    except ImportError:
        log("ERROR: falta PyYAML")
        sys.exit(2)
    if not DECLARACION.is_file():
        log(f"ERROR: no existe la declaración {DECLARACION}")
        sys.exit(2)
    return yaml.safe_load(DECLARACION.read_text(encoding="utf-8"))


def espejar_credenciales(decl: dict) -> list:
    """Copia las credenciales excluidas del off-site a una ruta que SI se respalda."""
    espejados = []
    for item in decl.get("dev", {}).get("espejo_credenciales", []) or []:
        origen = Path(item["origen"])
        if not origen.is_file():
            log(f"  aviso: credencial ausente, no se espeja: {origen}")
            continue
        STAGING_CREDS.mkdir(parents=True, exist_ok=True)
        destino = STAGING_CREDS / item["destino_nombre"]
        shutil.copy2(origen, destino)
        os.chmod(destino, 0o600)
        espejados.append(item["destino_nombre"])
    return espejados


def restic(repo: str, llave: Path, args: list, timeout: int = 3000) -> subprocess.CompletedProcess:
    entorno = dict(os.environ, RESTIC_PASSWORD_FILE=str(llave))
    return subprocess.run(["restic", "-r", repo, *args], capture_output=True, text=True,
                          env=entorno, timeout=timeout)


def repo_existe(repo: str, llave: Path) -> bool:
    return restic(repo, llave, ["snapshots", "--json"], timeout=120).returncode == 0


def main() -> int:
    p = argparse.ArgumentParser(description="Capa 1: snapshot local del respaldo")
    p.add_argument("--ensayo", action="store_true", help="no escribe nada (restic --dry-run)")
    p.add_argument("--sin-prune", action="store_true", help="no aplica retencion")
    p.add_argument("--sin-espejo", action="store_true", help="no espeja credenciales")
    args = p.parse_args()

    t0 = time.time()
    decl = cargar_declaracion()
    dev = decl.get("dev", {})
    repo = os.environ.get("LOCAL_RESTIC_REPO", dev.get("repo_local", "/opt/hermes-backups/restic-local"))
    llave = Path(dev.get("llave", str(DATA / "backup-keys/master-backup.key")))
    if not llave.is_file():
        log(f"ERROR: falta la llave {llave}")
        return 2

    log(f"capa 1 · repo local: {repo}")

    # 1. Espejo de credenciales (para que viajen tambien al off-site)
    espejados = [] if args.sin_espejo else espejar_credenciales(decl)

    # 2. Fuentes declaradas que existen
    fuentes = [f for f in dev.get("fuentes", []) if Path(f).exists()]
    faltantes = [f for f in dev.get("fuentes", []) if not Path(f).exists()]
    staging = DATA / "backups/staging/dumps"
    if staging.is_dir():
        fuentes.append(str(staging))
    log(f"  fuentes: {len(fuentes)} presentes · {len(faltantes)} ausentes · credenciales espejadas: {len(espejados)}")
    for f in faltantes:
        log(f"    ausente: {f}")

    # 3. Repositorio: crear si no existe
    if not repo_existe(repo, llave):
        log("  repositorio local no existe -> init")
        if args.ensayo:
            log("  (ensayo: no se inicializa)")
        else:
            r = restic(repo, llave, ["init"], timeout=300)
            if r.returncode != 0:
                log("ERROR al inicializar: " + (r.stderr or r.stdout)[:300])
                return 1

    # 4. Backup
    cmd = ["backup", "--json"]
    for ex in dev.get("exclusiones", []) or []:
        cmd += ["--iexclude", ex]
    cmd += fuentes
    if args.ensayo:
        cmd.append("--dry-run")
    r = restic(repo, llave, cmd)
    if r.returncode != 0:
        log("ERROR del backup: " + (r.stderr or r.stdout)[-400:])
        return 1

    resumen = {}
    for linea in (r.stdout or "").splitlines():
        try:
            d = json.loads(linea)
        except json.JSONDecodeError:
            continue
        if d.get("message_type") == "summary":
            resumen = d

    snapshot_id = (resumen.get("snapshot_id") or "")[:10]
    archivos = resumen.get("total_files_processed", 0)
    bytes_tot = resumen.get("total_bytes_processed", 0)
    mb = round(bytes_tot / 1024 / 1024, 1)

    # 5. Retencion
    podado = False
    if not args.sin_prune and not args.ensayo and snapshot_id:
        pr = restic(repo, llave, ["forget", "--keep-daily", "7", "--keep-weekly", "4",
                                  "--keep-monthly", "3", "--prune"], timeout=1800)
        podado = pr.returncode == 0

    duracion = round(time.time() - t0, 1)
    ok = bool(snapshot_id) and archivos > 0
    estado = {
        "fecha": datetime.now(timezone.utc).isoformat(),
        "capa": "local",
        "repo": repo,
        "ok": ok,
        "snapshot_id": snapshot_id,
        "archivos": archivos,
        "mb": mb,
        "fuentes": len(fuentes),
        "ausentes": faltantes,
        "credenciales_espejadas": espejados,
        "retencion_aplicada": podado,
        "duracion_s": duracion,
        "ensayo": args.ensayo,
    }
    ESTADO.parent.mkdir(parents=True, exist_ok=True)
    if not args.ensayo:
        ESTADO.write_text(json.dumps(estado, indent=2, ensure_ascii=False), encoding="utf-8")

    log(f"RESULTADO: {'OK' if ok else 'FALLO'} · snapshot={snapshot_id or 'ninguno'} · "
        f"{archivos} ficheros · {mb} MB · {duracion}s" + (" · (ensayo)" if args.ensayo else ""))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
