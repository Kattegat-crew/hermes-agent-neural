#!/usr/bin/env python3
"""Estado del guard `read-before-patch`: ledger JSONL por sesión + huellas (CA1-CA10).

Ledger: un JSONL por sesión bajo
    <root>/<session_id>.jsonl
con `root` default /opt/hermes-agent-data/state/hooks/read-before-patch (02-design §2.1).
Una línea por evento:

    {"t": "<ISO-UTC>", "ts": <epoch>, "ev": "post_tool_call",
     "tool": "read_file", "path": "/abs/x.py", "mtime_ns": ..., "size": ..., "ok": true}

- Escritura bajo `fcntl.flock` exclusivo (turnos concurrentes).
- Lectura tolerante: las líneas corruptas se ignoran, nunca rompen el hook.
- Retención: 7 días o 5.000 líneas por sesión; limpieza oportunista (1 de cada 50
  escrituras) bajo el mismo lock.
- Última entrada por `path` gana (comparación por `os.path.realpath`).

Solo stdlib. Ninguna función de este módulo debe lanzar hacia el hook:
las operaciones de E/S se cuidan de degradar a "sin registro" antes que fallar.
"""

import fcntl
import hashlib
import json
import os
import time
from pathlib import Path

DEFAULT_ROOT = Path("/opt/hermes-agent-data/state/hooks/read-before-patch")
RETENTION_DAYS = 7
MAX_LINES = 5000
CLEANUP_EVERY = 50  # 1 de cada 50 escrituras dispara limpieza oportunista
DIGEST_CAP = 32 * 1024 * 1024  # no hashear archivos gigantes; fp-only arriba del cap

_EV_POST = "post_tool_call"

_appends = 0  # contador de proceso para la limpieza oportunista


def _safe_session(session_id) -> str:
    """Nombre de archivo seguro para el session_id (sin '/', solo [A-Za-z0-9._-])."""
    raw = str(session_id) if session_id else "unknown"
    safe = "".join(c if (c.isalnum() or c in "-_.") else "_" for c in raw)
    return safe or "unknown"


def ledger_path(session_id, root=None) -> Path:
    """Ruta del ledger de la sesión. `root` parametriza el directorio de estado
    (los tests nunca tocan el real); None -> default del despliegue."""
    base = Path(root) if root is not None else DEFAULT_ROOT
    return base / (_safe_session(session_id) + ".jsonl")


def fingerprint(path) -> tuple:
    """Huella del archivo: (st_mtime_ns, st_size). Sigue symlinks (os.stat).
    Ruta inexistente -> (0, 0) (nunca lanza; el guard trata la existencia aparte)."""
    try:
        st = os.stat(str(path))
        return (st.st_mtime_ns, st.st_size)
    except OSError:
        return (0, 0)


def file_digest(path, cap=DIGEST_CAP):
    """sha256 del contenido (o None si no se puede/convine: archivo > cap).
    Desempata la ventana de granularidad del reloj: dos escrituras del mismo
    tamaño dentro del mismo tick comparten (mtime_ns, size) pero no contenido."""
    try:
        if os.path.getsize(str(path)) > cap:
            return None
        h = hashlib.sha256()
        with open(str(path), "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def _iso(epoch: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(epoch))


def _read_entries(ledger: Path) -> list:
    """Lee el ledger tolerando líneas corruptas/vacías (se ignoran, no rompen)."""
    try:
        text = ledger.read_text(encoding="utf-8")
    except OSError:
        return []
    entries = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(entry, dict):
            entries.append(entry)
    return entries


def _cleanup_locked(f, now: float) -> None:
    """Poda por retención (7 días o 5.000 líneas). Debe llamarse con el lock tomado
    y `f` en modo 'a+' (lectura y append)."""
    try:
        f.seek(0)
        raw = f.read()
    except OSError:
        return
    cutoff = now - RETENTION_DAYS * 86400
    kept = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue  # línea corrupta: se descarta en la poda
        ts = entry.get("ts") if isinstance(entry, dict) else None
        if isinstance(ts, (int, float)) and ts < cutoff:
            continue
        kept.append(line)
    if len(kept) > MAX_LINES:
        kept = kept[-MAX_LINES:]
    try:
        f.seek(0)
        f.truncate()
        if kept:
            f.write("\n".join(kept) + "\n")
        f.flush()
    except OSError:
        pass


def _append(session_id, entry: dict, root=None) -> None:
    """Escribe una línea en el ledger bajo flock exclusivo, con poda oportunista."""
    global _appends
    ledger = ledger_path(session_id, root)
    ledger.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(entry, ensure_ascii=False)
    now = float(entry.get("ts") or time.time())
    with open(ledger, "a+", encoding="utf-8") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            f.write(line + "\n")
            f.flush()
            _appends += 1
            if _appends % CLEANUP_EVERY == 1:
                _cleanup_locked(f, now)
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def record(session_id, tool, path, ok=True, root=None) -> None:
    """Registra (path, huella actual) para un tool de lectura/escritura.
    La huella se toma AHORA: el agente vio/escribió este contenido."""
    p = str(path)
    mtime_ns, size = fingerprint(p)
    now = time.time()
    entry = {
        "t": _iso(now),
        "ts": now,
        "ev": _EV_POST,
        "tool": str(tool),
        "path": p,
        "mtime_ns": mtime_ns,
        "size": size,
        "ok": bool(ok),
    }
    if mtime_ns or size:
        digest = file_digest(p)
        if digest:
            entry["sha256"] = digest
    try:
        _append(session_id, entry, root=root)
    except Exception:
        pass  # sin ledger no hay guard: el hook sigue (fail-open)


def last_seen(session_id, path, root=None):
    """Última entrada registrada para la ruta (por realpath) o None.
    Devuelve {'path', 'mtime_ns', 'size', 'tool', 't'} (más campos extra del ledger)."""
    ledger = ledger_path(session_id, root)
    if not ledger.exists():
        return None
    try:
        want = os.path.realpath(str(path))
    except OSError:
        want = str(path)
    found = None
    for entry in _read_entries(ledger):
        if entry.get("ev") != _EV_POST:
            continue  # would_block / error / disabled no cuentan como "visto"
        p = entry.get("path")
        if not isinstance(p, str) or not p:
            continue
        try:
            same = os.path.realpath(p) == want
        except OSError:
            same = p == want
        if same:
            found = entry  # la última línea gana
    return found


def log_event(session_id, ev, root=None, **fields) -> None:
    """Registra un evento administrativo del guard (would_block / error / disabled).
    Nunca lanza: sin ledger no hay registro, pero el hook sigue."""
    now = time.time()
    entry = {"t": _iso(now), "ts": now, "ev": str(ev)}
    entry.update(fields)
    try:
        _append(session_id, entry, root=root)
    except Exception:
        pass


def mode(root=None) -> str:
    """Modo del guard: 'shadow' (default) | 'enforce'.
    Prioridad: env READ_BEFORE_PATCH_MODE > archivo MODE junto al ledger > shadow."""
    env = (os.environ.get("READ_BEFORE_PATCH_MODE") or "").strip().lower()
    if env in ("shadow", "enforce"):
        return env
    base = Path(root) if root is not None else DEFAULT_ROOT
    try:
        raw = (base / "MODE").read_text(encoding="utf-8").strip().lower()
    except OSError:
        raw = ""
    return raw if raw in ("shadow", "enforce") else "shadow"


def disabled(root=None) -> bool:
    """Kill switch: el archivo DISABLED en el directorio de estado apaga el guard."""
    base = Path(root) if root is not None else DEFAULT_ROOT
    try:
        return (base / "DISABLED").exists()
    except OSError:
        return False
