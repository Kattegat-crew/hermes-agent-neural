#!/usr/bin/env python3
"""
Auditor de la cadena de respaldo.

Vigila lo que la auditoría del 23-sep encontró a faltar:

  1. EDAD del último snapshot local  -> si envejece, avisa (la red de seguridad se rompió).
  2. EDAD y ACCESIBILIDAD del destino off-site -> si no responde, avisa (A2).
  3. HONESTIDAD del manifiesto -> si el último dice FAILED, o envejece, avisa (A5).
  4. DERIVA (drift) entre lo DECLARADO en `docs/ops/backup-sources.yaml` y lo que el
     snapshot realmente contiene -> si divergen, avisa. Es el chequeo que habría
     cazado el fallo de las 361 fichas / 2,56 MB el primer día.

Salida: SILENCIO cuando todo está bien (pensado para cron); reporte cuando hay problema.
Siempre escribe `data/state/backup-audit.json`. Uso `--siempre` para forzar el reporte.

Uso:
    backup_audit.py [--siempre] [--sin-webhook]
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path("/opt/hermes-agent")          # repo de codigo: docs/ de la declaracion
DATA = Path("/opt/hermes-agent-data")     # estado nativo (F6, 29-sep-2026)
DECLARACION = RAIZ / "docs/ops/backup-sources.yaml"
ESTADO = DATA / "state/backup-audit.json"
MAESTRO = DATA / "scripts/vps_master_backup.py"

MAX_HORAS_LOCAL = 36.0
MAX_HORAS_OFFSITE = 36.0
MIN_FICHEROS = 1000
MIN_MB = 100.0


def ahora() -> datetime:
    return datetime.now(timezone.utc)


def horas_desde(iso: str) -> float:
    try:
        d = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except Exception:
        return -1.0
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return round((ahora() - d).total_seconds() / 3600, 1)


def restic(repo: str, llave: Path, args: list, timeout: int = 240) -> subprocess.CompletedProcess:
    entorno = dict(os.environ, RESTIC_PASSWORD_FILE=str(llave))
    try:
        return subprocess.run(["restic", "-r", repo, *args], capture_output=True,
                              text=True, env=entorno, timeout=timeout)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(args, 124, "", f"timeout tras {timeout}s")


def leer_declaracion() -> dict:
    import yaml
    return yaml.safe_load(DECLARACION.read_text(encoding="utf-8"))


def snapshots(repo: str, llave: Path) -> tuple[list, str]:
    r = restic(repo, llave, ["snapshots", "--json"])
    if r.returncode != 0:
        return [], (r.stderr or r.stdout or "error desconocido").strip()[:300]
    try:
        return json.loads(r.stdout or "[]"), ""
    except json.JSONDecodeError:
        return [], "salida ilegible de restic snapshots"


def fuentes_del_snapshot(repo: str, llave: Path) -> list:
    r = restic(repo, llave, ["ls", "latest"], timeout=300)
    salida = (r.stdout or "") + (r.stderr or "")
    m = re.search(r"snapshot [0-9a-f]+ of \[(.*?)\] filtered by", salida, re.S)
    if not m:
        return []
    return [p.strip() for p in m.group(1).split(" ") if p.strip()]


def manifiesto_mas_reciente() -> dict:
    ms = sorted(glob.glob(str(DATA / "backups/manifests/*.json")), key=os.path.getmtime)
    if not ms:
        return {}
    try:
        d = json.load(open(ms[-1]))
        d["_archivo"] = os.path.basename(ms[-1])
        d["_mtime"] = datetime.fromtimestamp(os.path.getmtime(ms[-1]), timezone.utc).isoformat()
        return d
    except Exception as e:
        return {"_archivo": os.path.basename(ms[-1]), "_error": str(e)}


def webhook_por_defecto() -> str:
    try:
        t = MAESTRO.read_text(encoding="utf-8", errors="ignore")
        m = re.search(r'DISCORD_WEBHOOK_DEFAULT\s*=\s*["\']([^"\']+)["\']', t)
        return m.group(1) if m else ""
    except Exception:
        return ""


def avisar(webhook: str, texto: str) -> None:
    if not webhook:
        return
    cuerpo = json.dumps({"content": texto[:1900]}).encode()
    req = urllib.request.Request(webhook, data=cuerpo,
                                 headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=20).read()
    except Exception as e:
        print(f"  (no se pudo avisar por webhook: {e})")


def main() -> int:
    p = argparse.ArgumentParser(description="Auditor de la cadena de respaldo")
    p.add_argument("--siempre", action="store_true", help="reportar tambien cuando todo esta bien")
    p.add_argument("--sin-webhook", action="store_true", help="no enviar aviso")
    args = p.parse_args()

    problemas, avisos, datos = [], [], {}

    decl = leer_declaracion()
    dev = decl.get("dev", {})
    repo_local = dev.get("repo_local", "/opt/hermes-backups/restic-local")
    repo_off = dev.get("repo_offsite", "rclone:onedrive:Backups/.250")
    llave = Path(dev.get("llave", str(DATA / "backup-keys/master-backup.key")))

    # 1. capa local
    snaps_l, err_l = snapshots(repo_local, llave)
    if err_l:
        problemas.append(f"capa LOCAL ilegible: {err_l}")
        datos["local"] = {"ok": False, "error": err_l}
    else:
        ult = snaps_l[-1].get("time", "") if snaps_l else ""
        h = horas_desde(ult) if ult else -1
        datos["local"] = {"snapshots": len(snaps_l), "ultimo": ult, "horas": h}
        if not snaps_l:
            problemas.append("capa LOCAL sin ningún snapshot")
        elif h > MAX_HORAS_LOCAL:
            problemas.append(f"capa LOCAL con {h} h sin snapshot (máx {MAX_HORAS_LOCAL})")

    # 2. capa off-site
    snaps_o, err_o = snapshots(repo_off, llave)
    if err_o:
        problemas.append("destino OFF-SITE inalcanzable: " + err_o)
        datos["offsite"] = {"ok": False, "error": err_o}
    else:
        ult = snaps_o[-1].get("time", "") if snaps_o else ""
        h = horas_desde(ult) if ult else -1
        datos["offsite"] = {"snapshots": len(snaps_o), "ultimo": ult, "horas": h}
        if not snaps_o:
            problemas.append("destino OFF-SITE sin ningún snapshot")
        elif h > MAX_HORAS_OFFSITE:
            problemas.append(f"destino OFF-SITE con {h} h sin snapshot (máx {MAX_HORAS_OFFSITE})")

        # 4. drift: declarado vs real
        reales = fuentes_del_snapshot(repo_off, llave)
        declaradas = [f for f in dev.get("fuentes", []) if Path(f).exists()]
        faltan = [f for f in declaradas if f not in reales]
        datos["drift"] = {"declaradas": len(declaradas), "en_snapshot": len(reales),
                          "faltantes": faltan}
        if reales and faltan:
            avisos.append("fuentes declaradas que el snapshot NO contiene: " + ", ".join(faltan[:6]))

    # 3. honestidad del manifiesto
    man = manifiesto_mas_reciente()
    if not man:
        problemas.append("no hay manifiestos de respaldo")
    else:
        h = horas_desde(man.get("_mtime", ""))
        st = man.get("status")
        est = man.get("stats", {}) or {}
        datos["manifiesto"] = {"archivo": man.get("_archivo"), "status": st, "horas": h,
                               "files": est.get("total_files"), "mb": est.get("total_bytes_mb")}
        if st != "SUCCESS":
            problemas.append(f"último manifiesto en estado {st}")
        if h > MAX_HORAS_LOCAL:
            problemas.append(f"último manifiesto con {h} h de antigüedad")
        if (est.get("total_files") or 0) < MIN_FICHEROS:
            problemas.append(f"el último manifiesto reporta solo {est.get('total_files')} ficheros")
        if (est.get("total_bytes_mb") or 0) < MIN_MB:
            problemas.append(f"volumen sospechosamente bajo: {est.get('total_bytes_mb')} MB")

    datos["fecha"] = ahora().isoformat()
    datos["problemas"] = problemas
    datos["avisos"] = avisos
    ESTADO.parent.mkdir(parents=True, exist_ok=True)
    ESTADO.write_text(json.dumps(datos, indent=2, ensure_ascii=False), encoding="utf-8")

    if not problemas and not avisos and not args.siempre:
        return 0  # silencio = todo bien

    lineas = ["🛡️ **Auditoría del respaldo** — " + ahora().strftime("%Y-%m-%d %H:%M UTC")]
    if problemas:
        lineas.append("**PROBLEMAS:**")
        lineas += ["• " + x for x in problemas]
    if avisos:
        lineas.append("**Avisos:**")
        lineas += ["• " + x for x in avisos]
    if args.siempre and not problemas and not avisos:
        lineas.append("• Todo en orden: capa local y off-site frescas, manifiesto honesto, sin deriva.")
    texto = "\n".join(lineas)
    print(texto)

    if problemas and not args.sin_webhook:
        avisar(os.environ.get("BACKUP_ALERT_WEBHOOK") or webhook_por_defecto(), texto)
    return 1 if problemas else 0


if __name__ == "__main__":
    sys.exit(main())
