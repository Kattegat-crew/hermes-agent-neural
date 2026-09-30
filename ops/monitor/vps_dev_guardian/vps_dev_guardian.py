#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vps_dev_guardian.py — Monitor nativo de salud del VPS Dev (147.93.3.250).

Reemplazo del legacy /root/hermes-agent-legacy-docker/data/scripts/vps_health_watchdog.py.

Diferencias clave con el legacy:
  * Solo lectura: sin kill, sin drop_caches, sin reinicios, sin tocar sesiones WhatsApp.
  * systemctl show como señal primaria de las unidades nativas (PID aislado NO es salud).
  * Bridge WhatsApp vía HTTP local directo (sin docker exec ni pgrep como señal única).
  * Deduplicación de incidentes con confirmación por checks consecutivos (parametrizable)
    y estado atómico (tmp + os.replace).
  * Entrega a Discord REAL pero DESACTIVADA por defecto: requiere opt-in explícito
    (VPS_GUARDIAN_DELIVERY=discord) y webhook desde entorno o archivo privado.
    El secret NUNCA se hardcodea ni se registra. Incidente solo se marca 'alerted'
    tras entrega exitosa; fallo de entrega es reintentable sin falsa recuperación.
  * Lock flock para evitar ejecución simultánea de check periódico y resumen 09:00.
  * Vigía: marcado explícitamente como NO IMPLEMENTADO (diseño no resuelto); nunca
    se inventa salud para un componente no definido en la arquitectura actual.
  * --dry-run: no escribe estado, no envía mensajes, no modifica servicios.
  * Sin rutas del contenedor legacy en la lógica de chequeo (estado en /opt/hermes-agent-data).

Uso:
  vps_dev_guardian.py check            # revisión silenciosa periódica (cron */15)
  vps_dev_guardian.py summary          # resumen único 09:00 America/Bogota
  vps_dev_guardian.py check --dry-run  # ejercicio real sin escrituras ni envíos

Entrega a Discord (opt-in explícito, solo con autorización humana):
  VPS_GUARDIAN_DELIVERY=discord                                  # activa la entrega
  VPS_GUARDIAN_DISCORD_WEBHOOK_URL=...                           # secret por entorno, O
  VPS_GUARDIAN_DISCORD_WEBHOOK_FILE=/ruta/archivo_privado_0600   # secret por archivo
  VPS_GUARDIAN_FAILURE_THRESHOLD=2                               # checks consecutivos antes de avisar
"""

import argparse
import fcntl
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

VERSION = "1.1.1"

# Unidades systemd nativas esperadas activas en este VPS (definición explícita).
EXPECTED_UNITS = [
    "hermes-agent.service",       # Gateway Ragnar (perfil default)
    "hermes-agent-roshi.service", # Gateway Roshi (standalone Discord)
]

BRIDGE_URL = "http://127.0.0.1:3000/health"
BRIDGE_TIMEOUT_S = 5
BRIDGE_RETRIES = 3
BRIDGE_RETRY_DELAY_S = 2

# Umbrales (spec punto 7)
RAM_PCT_CRITICAL = 85.0
CPU_LOAD5_PER_CORE_CRITICAL = 1.0   # carga sostenida normalizada por núcleos
DISK_PCT_WARNING = 75.0
DISK_PCT_CRITICAL = 85.0
# Swap ocupado por sí solo NO demuestra presión actual: no genera incidente.

# --- Entrega Discord (REAL, DESACTIVADA por defecto; opt-in explícito) -----
DELIVERY_ENV = "VPS_GUARDIAN_DELIVERY"            # "discord" activa la entrega
WEBHOOK_URL_ENV = "VPS_GUARDIAN_DISCORD_WEBHOOK_URL"
WEBHOOK_FILE_ENV = "VPS_GUARDIAN_DISCORD_WEBHOOK_FILE"
WEBHOOK_FILE_DEFAULT = Path(
    "/opt/hermes-agent-data/home/secrets/vps-dev-guardian/discord_webhook_url.txt"
)
DISCORD_TIMEOUT_S = 10
DISCORD_MAX_CHARS = 1900  # límite práctico por mensaje de Discord

# Confirmación por checks consecutivos (spec punto 3): un incidente debe
# persistir en N checks consecutivos antes de avisar. Parametrizable entre
# checks vía VPS_GUARDIAN_FAILURE_THRESHOLD (por defecto 2: con cron */15
# son 30 minutos de fallo sostenido antes de la primera alerta).
FAILURE_THRESHOLD_ENV = "VPS_GUARDIAN_FAILURE_THRESHOLD"
DEFAULT_FAILURE_THRESHOLD = 2


def failure_threshold() -> int:
    try:
        return max(1, int(os.environ.get(FAILURE_THRESHOLD_ENV,
                                         DEFAULT_FAILURE_THRESHOLD)))
    except ValueError:
        return DEFAULT_FAILURE_THRESHOLD


def delivery_mode() -> str:
    """Modo de entrega efectivo. DESACTIVADO salvo opt-in explícito."""
    val = os.environ.get(DELIVERY_ENV, "").strip().lower()
    if val == "discord":
        return "discord"
    return "disabled"


def _load_webhook_url():
    """Carga el secret desde entorno o archivo privado. Nunca se loguea."""
    url = os.environ.get(WEBHOOK_URL_ENV, "").strip()
    if url:
        return url
    fpath = os.environ.get(WEBHOOK_FILE_ENV, "").strip()
    path = Path(fpath) if fpath else WEBHOOK_FILE_DEFAULT
    try:
        url = path.read_text().strip()
        return url or None
    except OSError:
        return None


# Estado de deduplicación — dueño hermes
STATE_DIR = Path("/opt/hermes-agent-data/home/monitor_state/vps_dev_guardian")
STATE_FILE = STATE_DIR / "incident_state.json"
LOCK_FILE = STATE_DIR / "guardian.lock"
SUMMARY_STAMP = STATE_DIR / "last_summary_date.txt"

BOGOTA = timezone(timedelta(hours=-5))

# Vigía — NO IMPLEMENTADO (diseño no resuelto; ver NOTA_VIGIA al final del archivo).
VIGIA_NOTE = (
    "Vigía: diseño no resuelto en arquitectura nativa (sin unidad systemd cargada ni "
    "señal definida). No se monitorea ni se inventa salud. Pendiente definición de reviewer."
)


# ---------------------------------------------------------------------------
# Escrituras atómicas
# ---------------------------------------------------------------------------

def _ensure_state_dir():
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(STATE_DIR, 0o700)


def _atomic_write(path: Path, data: bytes):
    """Escritura atómica (tmp + fsync + os.replace), sin tmps residuales."""
    _ensure_state_dir()
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-",
                               suffix=path.suffix or ".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def atomic_write_json(path: Path, data: dict):
    _atomic_write(path, json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8"))


def atomic_write_text(path: Path, text: str):
    _atomic_write(path, text.encode("utf-8"))


def atomic_read_json(path: Path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


class GuardianLock:
    """flock exclusivo no bloqueante: evita solapar check y summary."""

    def __init__(self, skip_write=False):
        self._fh = None
        self._skip_write = skip_write

    def __enter__(self):
        if self._skip_write:
            # dry-run: flock sobre el propio binario (solo lectura, sin crear nada)
            self._fh = open("/proc/self/exe" if not Path(LOCK_FILE).exists()
                            else LOCK_FILE, "r")
        else:
            _ensure_state_dir()
            self._fh = open(LOCK_FILE, "w")
        try:
            fcntl.flock(self._fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self._fh.close()
            self._fh = None
            raise RuntimeError(
                "Otra instancia del guardian está en ejecución; abortando para evitar duplicados."
            )
        try:
            os.chmod(LOCK_FILE, 0o600)
        except OSError:
            pass
        return self

    def __exit__(self, exc_type, exc, tb):
        if self._fh:
            try:
                fcntl.flock(self._fh, fcntl.LOCK_UN)
                self._fh.close()
            except OSError:
                pass
            self._fh = None
        return False


# ---------------------------------------------------------------------------
# Checks (solo lectura)
# ---------------------------------------------------------------------------

def check_units():
    results = []
    for unit in EXPECTED_UNITS:
        try:
            out = subprocess.run(
                ["systemctl", "show", unit, "--property=ActiveState,SubState,MainPID"],
                capture_output=True, text=True, timeout=10, check=False,
            )
            if out.returncode != 0:
                results.append({"name": unit, "kind": "unit", "healthy": False,
                                "detail": f"systemctl exit {out.returncode}"})
                continue
            props = {}
            for line in out.stdout.strip().splitlines():
                if "=" in line:
                    k, v = line.split("=", 1)
                    props[k.strip()] = v.strip()
            active = props.get("ActiveState", "unknown")
            sub = props.get("SubState", "unknown")
            mainpid = props.get("MainPID", "0")
            healthy = (active == "active" and sub == "running")
            results.append({"name": unit, "kind": "unit", "healthy": healthy,
                            "detail": f"ActiveState={active} SubState={sub} MainPID={mainpid}"})
        except (subprocess.TimeoutExpired, OSError) as e:
            results.append({"name": unit, "kind": "unit", "healthy": False,
                            "detail": f"error: {e}"})
    return results


def check_bridge():
    last_err = None
    for attempt in range(BRIDGE_RETRIES):
        try:
            req = urllib.request.Request(BRIDGE_URL,
                                         headers={"User-Agent": f"vps-dev-guardian/{VERSION}"})
            with urllib.request.urlopen(req, timeout=BRIDGE_TIMEOUT_S) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            status = data.get("status", "unknown")
            return {"name": "whatsapp-bridge", "kind": "bridge",
                    "healthy": status == "connected",
                    "detail": f"status={status} queueLength={data.get('queueLength', 0)}"}
        except (urllib.error.URLError, json.JSONDecodeError, OSError) as e:
            last_err = e
            if attempt < BRIDGE_RETRIES - 1:
                time.sleep(BRIDGE_RETRY_DELAY_S)
    return {"name": "whatsapp-bridge", "kind": "bridge", "healthy": False,
            "detail": f"unreachable tras {BRIDGE_RETRIES} intentos: {last_err}"}


def check_vigia():
    return {"name": "vigia", "kind": "vigia", "healthy": None, "detail": VIGIA_NOTE}


def get_memory():
    meminfo = {}
    with open("/proc/meminfo") as f:
        for line in f:
            if ":" in line:
                k, v = line.split(":", 1)
                meminfo[k.strip()] = int(v.strip().split()[0])
    total = meminfo.get("MemTotal", 0) / 1024
    avail = meminfo.get("MemAvailable", 0) / 1024
    used = total - avail
    swap_total = meminfo.get("SwapTotal", 0) / 1024
    swap_used = swap_total - meminfo.get("SwapFree", 0) / 1024
    return {
        "ram_pct": round(used / total * 100, 1) if total else 0.0,
        "ram_used_mb": round(used),
        "ram_total_mb": round(total),
        "swap_pct": round(swap_used / swap_total * 100, 1) if swap_total else 0.0,
        "swap_used_mb": round(swap_used),
        "swap_total_mb": round(swap_total),
    }


def get_load():
    l1, l5, l15 = os.getloadavg()
    cores = os.cpu_count() or 1
    return {"load1": round(l1, 2), "load5": round(l5, 2), "load15": round(l15, 2),
            "cores": cores, "load5_per_core": round(l5 / cores, 2)}


def get_disk():
    st = os.statvfs("/")
    total = st.f_blocks * st.f_frsize
    free = st.f_bavail * st.f_frsize
    used = total - free
    return {"used_pct": round(used / total * 100, 1),
            "used_gb": round(used / 2**30, 1),
            "total_gb": round(total / 2**30, 1)}


def run_checks() -> tuple:
    """Checks con aislamiento: un fallo parcial no bloquea al resto."""
    units: list = []
    bridge: dict = {"healthy": False, "detail": "not-run"}
    vigia: dict = check_vigia()
    mem: dict = {}
    load: dict = {}
    disk: dict = {}
    errors: list = []
    for name, fn in (("units", check_units), ("bridge", check_bridge),
                     ("memory", get_memory), ("load", get_load), ("disk", get_disk)):
        try:
            result: Any = fn()
        except Exception as e:  # aislamiento de fallos parciales
            errors.append(f"{name}: {e}")
            continue
        if name == "units":
            units = result
        elif name == "bridge":
            bridge = result
        elif name == "memory":
            mem = result
        elif name == "load":
            load = result
        elif name == "disk":
            disk = result
    return units, bridge, vigia, mem, load, disk, errors


# ---------------------------------------------------------------------------
# Evaluación y dedup
# ---------------------------------------------------------------------------

def evaluate(units, bridge, vigia, mem, load, disk):
    """Misma evaluación para check y summary (sin falsos OK RAM/disco/CPU)."""
    incidents = []
    for u in units:
        if not u["healthy"]:
            incidents.append(("unit_down", u["name"], u["detail"]))
    if not bridge["healthy"]:
        incidents.append(("bridge_down", bridge["name"], bridge["detail"]))
    # vigia (healthy=None) no genera incidente ni OK — diseño no resuelto.
    if mem and mem["ram_pct"] > RAM_PCT_CRITICAL:
        incidents.append(("ram_high", "memory", f"RAM {mem['ram_pct']}% > {RAM_PCT_CRITICAL}%"))
    if load and load["load5_per_core"] > CPU_LOAD5_PER_CORE_CRITICAL:
        incidents.append(("cpu_sustained", "cpu",
                          f"load5/core {load['load5_per_core']} > {CPU_LOAD5_PER_CORE_CRITICAL} "
                          f"({load['cores']} cores)"))
    if disk:
        if disk["used_pct"] > DISK_PCT_CRITICAL:
            incidents.append(("disk_high", "disk", f"disco {disk['used_pct']}% > {DISK_PCT_CRITICAL}%"))
        elif disk["used_pct"] > DISK_PCT_WARNING:
            incidents.append(("disk_warn", "disk", f"disco {disk['used_pct']}% > {DISK_PCT_WARNING}% (warn)"))
    return incidents


def _now_bogota():
    return datetime.now(BOGOTA).strftime("%Y-%m-%d %H:%M:%S -05")


# ---------------------------------------------------------------------------
# Entrega Discord (REAL; DESACTIVADA por defecto)
# ---------------------------------------------------------------------------

def format_discord_alert(kind, target, detail, consecutive=None, threshold=None):
    iid = f"{kind}:{target}"
    suffix = ""
    if consecutive is not None and threshold is not None:
        suffix = f" (confirmado en {consecutive} checks consecutivos, umbral {threshold})"
    return f"🔴 [VPS Dev Guardian] INCIDENTE {iid}: {detail}{suffix}"


def format_discord_recovery(iid):
    return f"🟢 [VPS Dev Guardian] RECUPERADO: {iid}"


def _real_discord_post(url, payload, timeout):
    """POST real al webhook. Aislado para poder mockearse en tests."""
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "User-Agent": f"vps-dev-guardian/{VERSION}"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status


def send_discord(content, post_fn=None):
    """POST real al webhook de Discord. Solo se invoca con entrega activada.

    post_fn(url, payload, timeout) -> status HTTP permite inyectar transporte
    mock en tests (nunca hay POST real en pruebas). El secret NUNCA se
    registra ni imprime: los errores son genéricos, sin URL ni cuerpo.
    """
    if post_fn is not None:
        url = "mock://discord-webhook"  # placeholder; el mock no lo usa como red
    else:
        url = _load_webhook_url()
        if not url:
            return False
        post_fn = _real_discord_post
    payload = {"content": content[:DISCORD_MAX_CHARS],
               "allowed_mentions": {"parse": []}}
    try:
        status = int(post_fn(url, payload, DISCORD_TIMEOUT_S))
        return 200 <= status < 300
    except Exception:
        # Sin detalle del secret: fallo genérico reintentable.
        return False


def process_incidents(incidents, dry_run=False, post_fn=None):
    """Dedup + confirmación por checks consecutivos + entrega + commit atómico.

    Reglas:
      * Un incidente avisa solo tras persistir failure_threshold() checks
        consecutivos (spec punto 3); un pico transitorio no genera alerta
        ni falso CRITICAL.
      * Con entrega activada, un incidente SOLO se marca 'alerted' tras
        entrega exitosa; un fallo de entrega NO marca nada y se reintenta
        en el siguiente check (sin falsa recuperación: el cierre también
        exige entrega exitosa).
      * Con entrega DESACTIVADA (default) los incidentes confirmados se
        marcan 'local-only' (NO 'alerted'): el dedup local no cuenta como
        aviso externo. Al activar la entrega, un incidente aún abierto se
        entrega UNA vez; y una recuperación SOLO sale si hubo alerta
        externa exitosa (sin cierres huérfanos).
      * Un incidente que desaparece antes de confirmarse baja en silencio
        (nunca tuvo aviso, no genera cierre).
      * dry_run: no lee ni escribe estado, no envía nada.
    """
    thr = failure_threshold()
    if dry_run:
        return {"to_alert": list(incidents), "to_recover": [],
                "delivered_alerts": [], "failed_alerts": [],
                "delivered_recovers": [], "failed_recovers": [],
                "delivery_mode": "dry-run", "delivery_errors": [],
                "consecutive": {}, "confirmed_any": False, "threshold": thr}
    prev = atomic_read_json(STATE_FILE, {})
    known = dict(prev.get("known", {}))
    prev_open = prev.get("open", {})
    now = _now_bogota()
    open_now, alerts = {}, []
    for kind, target, detail in incidents:
        iid = f"{kind}:{target}"
        consec = int(prev_open.get(iid, {}).get("consecutive", 0)) + 1
        open_now[iid] = {"first_seen": prev_open.get(iid, {}).get("first_seen", now),
                         "consecutive": consec}
        # 'alerted' = alerta externa ya entregada (NO repetir). 'local-only'
        # = confirmado solo en local: SI entra en alerts para que, si la
        # entrega se activa con el incidente aún abierto, la alerta se
        # entregue UNA vez (sin pérdida silenciosa).
        if consec >= thr and known.get(iid) != "alerted":
            alerts.append((kind, target, detail))
    recovers = []
    for iid in list(known):
        if iid not in open_now:
            if known[iid] == "alerted":
                recovers.append(iid)
            else:
                known.pop(iid)  # nunca llegó a alertarse: baja silenciosa
    mode = delivery_mode()
    delivery_errors = []
    delivered_alerts, failed_alerts = [], []
    delivered_recovers, failed_recovers = [], []
    if mode == "discord":
        for kind, target, detail in alerts:
            iid = f"{kind}:{target}"
            ok = send_discord(
                format_discord_alert(kind, target, detail,
                                     consecutive=open_now[iid]["consecutive"],
                                     threshold=thr),
                post_fn=post_fn)
            if ok:
                delivered_alerts.append(iid)
            else:
                failed_alerts.append(iid)
                delivery_errors.append(f"alerta {iid} no entregada")
        for iid in recovers:
            if send_discord(format_discord_recovery(iid), post_fn=post_fn):
                delivered_recovers.append(iid)
            else:
                failed_recovers.append(iid)
                delivery_errors.append(f"recuperación {iid} no entregada")
        # Marcar SOLO tras entrega exitosa; los fallidos quedan reintentables.
        for iid in delivered_alerts:
            known[iid] = "alerted"
        for iid in delivered_recovers:
            known[iid] = "recovered"
    else:
        # Entrega desactivada (default): dedup LOCAL del log; NO constituye
        # envío externo y NO se marca 'alerted' (ese estado queda reservado
        # para entrega externa exitosa). Se usa 'local-only'. Así:
        #   * si la entrega se activa con el incidente aún abierto, la alerta
        #     se entrega UNA vez (sin pérdida silenciosa);
        #   * la recuperación SOLO sale si hubo alerta externa exitosa
        #     (sin cierres huérfanos);
        #   * un incidente solo-local que se resuelve baja en silencio.
        local_alerts = [f"{kind}:{target}" for kind, target, _ in alerts]
        for kind, target, _ in alerts:
            known[f"{kind}:{target}"] = "local-only"
        delivered_alerts, delivered_recovers = [], []
        # 'recovers' solo contiene iids marcados 'alerted' (entrega externa
        # exitosa previa): se cierran en local, NADA sale externamente.
        for iid in recovers:
            known[iid] = "recovered"
    atomic_write_json(STATE_FILE, {"open": open_now, "known": known,
                                   "updated": now, "delivery": mode,
                                   "threshold_checks": thr})
    return {"to_alert": list(alerts), "to_recover": list(recovers),
            "delivered_alerts": delivered_alerts, "failed_alerts": failed_alerts,
            "delivered_recovers": delivered_recovers,
            "failed_recovers": failed_recovers,
            "delivery_mode": mode, "delivery_errors": delivery_errors,
            "consecutive": {iid: v["consecutive"] for iid, v in open_now.items()},
            "confirmed_any": any(v["consecutive"] >= thr for v in open_now.values()),
            "threshold": thr}


def build_report(status, units, bridge, vigia, mem, load, disk, incidents,
                 incident_meta=None):
    lines = [
        f"=== VPS DEV GUARDIAN v{VERSION} [{status}] ===",
        f"Fecha (Bogotá): {_now_bogota()}",
        f"RAM:  {mem.get('ram_pct', '?')}% ({mem.get('ram_used_mb', '?')}/{mem.get('ram_total_mb', '?')} MB)",
        f"SWAP: {mem.get('swap_pct', '?')}% — swap ocupado por sí solo no genera incidente",
        f"DISK: {disk.get('used_pct', '?')}% ({disk.get('used_gb', '?')}/{disk.get('total_gb', '?')} GB)",
        f"LOAD: 1m={load.get('load1', '?')} 5m={load.get('load5', '?')} 15m={load.get('load15', '?')} "
        f"({load.get('cores', '?')} cores; load5/core={load.get('load5_per_core', '?')})",
        "",
    ]
    for u in units:
        lines.append(f"  [{'OK' if u['healthy'] else 'DOWN'}] {u['name']}: {u['detail']}")
    lines.append(f"  [{'OK' if bridge['healthy'] else 'DOWN'}] {bridge['name']}: {bridge['detail']}")
    lines.append(f"  [--] vigia: {VIGIA_NOTE}")
    if incidents:
        lines.append("")
        lines.append("INCIDENTES ABIERTOS:")
        for kind, target, detail in incidents:
            iid = f"{kind}:{target}"
            meta = (incident_meta or {}).get(iid)
            suffix = f" [consecutivos: {meta}]" if meta else ""
            lines.append(f"  - {iid} — {detail}{suffix}")
    lines.append("")
    lines.append("Acciones destructivas: NINGUNA (monitor solo lectura).")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Comandos
# ---------------------------------------------------------------------------

def cmd_check(args):
    with GuardianLock(skip_write=args.dry_run):
        units, bridge, vigia, mem, load, disk, errors = run_checks()
        incidents = evaluate(units, bridge, vigia, mem, load, disk)
        for err in errors:
            print(f"[check-error] {err}", file=sys.stderr)
        res = process_incidents(incidents, dry_run=args.dry_run)
        if args.dry_run:
            status = "WATCH" if incidents else "OK"
        elif res["confirmed_any"]:
            status = "CRITICAL"
        elif incidents:
            status = "WATCH"
        else:
            status = "OK"
        if args.dry_run:
            print("[DRY-RUN] No se escribe estado, no se envía nada, no se modifica ningún servicio.")
            if incidents:
                print("[DRY-RUN] Incidentes listados son CANDIDATOS: sin historial de "
                      "checks consecutivos no se confirma ni se envía nada.")
        print(build_report(status, units, bridge, vigia, mem, load, disk, incidents,
                           incident_meta=res["consecutive"]))
        if not args.dry_run:
            if res["delivered_alerts"]:
                print(f"[alerta-nueva] {', '.join(res['delivered_alerts'])} "
                      f"(entrega: {res['delivery_mode']})")
            if res["failed_alerts"]:
                print(f"[alerta-pendiente-entrega] {', '.join(res['failed_alerts'])} "
                      f"(se reintenta en el próximo check)", file=sys.stderr)
            if res["delivered_recovers"]:
                print(f"[recuperacion] {', '.join(res['delivered_recovers'])} "
                      f"(entrega: {res['delivery_mode']})")
            if res["failed_recovers"]:
                print(f"[recuperacion-pendiente-entrega] {', '.join(res['failed_recovers'])} "
                      f"(se reintenta en el próximo check)", file=sys.stderr)
            for derr in res["delivery_errors"]:
                print(f"[entrega-error] {derr}", file=sys.stderr)
    return 0


def cmd_summary(args):
    with GuardianLock(skip_write=args.dry_run):
        units, bridge, vigia, mem, load, disk, errors = run_checks()
        # MISMA evaluación que el check: RAM/disco/CPU en incidente impiden OK.
        incidents = evaluate(units, bridge, vigia, mem, load, disk)
        status = "CRITICAL" if incidents else ("DEGRADED" if errors else "OK")
        report = build_report(status, units, bridge, vigia, mem, load, disk, incidents)
        if args.dry_run:
            print("[DRY-RUN] summary: no escribe estado, no envía, no pone stamp.")
            print(report)
            return 0
        # Override de fecha SOLO para tests (determinismo del stamp);
        # en producción la var no existe y se usa la fecha real de Bogotá.
        today = os.environ.get("VPS_GUARDIAN_FAKE_TODAY") or \
            datetime.now(BOGOTA).strftime("%Y-%m-%d")
        if SUMMARY_STAMP.exists() and SUMMARY_STAMP.read_text().strip() == today:
            print(f"[summary] ya emitido hoy ({today}); no se duplica.")
            return 0
        # Entrega (si está activada) ANTES del stamp: el stamp solo se escribe
        # tras entrega exitosa; un fallo deja el resumen reintentable.
        if delivery_mode() == "discord":
            if not send_discord(report):
                print("[summary-entrega-error] resumen NO entregado; stamp NO escrito; "
                      "se reintentará.", file=sys.stderr)
                return 1
        print(report)
        atomic_write_text(SUMMARY_STAMP, today + "\n")
    return 0


def main():
    ap = argparse.ArgumentParser(description=f"VPS Dev Guardian v{VERSION} (solo lectura)")
    ap.add_argument("command", choices=["check", "summary"])
    ap.add_argument("--dry-run", action="store_true",
                    help="no escribe estado, no envía mensajes, no modifica servicios")
    args = ap.parse_args()
    try:
        sys.exit(cmd_check(args) if args.command == "check" else cmd_summary(args))
    except RuntimeError as e:
        print(f"[lock] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

# =========================================================================
# NOTA_VIGIA — Diseño NO RESUELTO (marcado explícitamente, spec punto 4)
# =========================================================================
# El script legacy chequeaba Vigía con pgrep -f "hermes -p vigia gateway run",
# una señal de proceso aislado que la nueva especificación rechaza como salud.
# En la arquitectura nativa actual NO existe una unidad systemd de Vigía cargada
# (verificado: systemctl list-units 'hermes-agent*' solo muestra default y roshi).
# Mientras el diseño no se resuelva (¿unidad dedicada? ¿perfil multiplex?
# ¿componente retirado = no aplicable?), este monitor NO reporta salud de Vigía:
# no OK, no CRITICAL. Se marca [--] en cada reporte y en el resumen 09:00.
# Decisión pendiente: reviewer independiente / owner de arquitectura.
# =========================================================================
# NOTA_ENTREGA — Discord (v1.1.0)
# =========================================================================
# La entrega es REAL (POST urllib al webhook) pero está DESACTIVADA por defecto
# y requiere opt-in explícito: VPS_GUARDIAN_DELIVERY=discord más el secret en
# VPS_GUARDIAN_DISCORD_WEBHOOK_URL (entorno) o en un archivo privado 0600
# (VPS_GUARDIAN_DISCORD_WEBHOOK_FILE; default bajo /opt/hermes-agent-data/home/secrets/).
# NUNCA se hardcodea ni se imprime el secret. Las pruebas usan transporte mock
# (post_fn inyectado): cero POST real en tests. Un incidente solo se marca
# 'alerted' tras entrega exitosa (HTTP 2xx); fallos quedan reintentables y la
# recuperación también exige éxito, evitando falsas recuperaciones. La prueba
# de entrega real a Discord requiere autorización humana explícita (spec punto 9).
