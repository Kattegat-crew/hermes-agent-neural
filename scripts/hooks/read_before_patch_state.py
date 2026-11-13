#!/usr/bin/env python3
"""Estado del guard `read-before-patch`: ledger JSONL por sesión + huellas (CA1-CA10).

Ledger: un JSONL por sesión bajo
    <root>/<session_id>.jsonl
con `root` default /opt/hermes-agent-data/state/hooks/read-before-patch (02-design §2.1).
Una línea por evento:

    {"t": "<ISO-UTC>", "ts": <epoch>, "ev": "post_tool_call",
     "tool": "read_file", "path": "/abs/x.py", "mtime_ns": ..., "size": ..., "ok": true}

- Escritura bajo `fcntl.flock` exclusivo (turnos concurrentes).
- Lectura bajo `fcntl.flock` COMPARTIDO (LOCK_SH, ronda 2 / H2): los hooks son
  procesos one-shot y un record() concurrente puede estar reescribiendo el
  archivo durante la poda; sin lock compartido la lectura ve el archivo a medias.
- Lectura tolerante: las líneas corruptas se ignoran, nunca rompen el hook.
- Retención: 7 días o 5.000 líneas por sesión; poda oportunista (ronda 2 / H3):
  se intenta SOLO si el mtime del ledger tiene más de 1 hora o su tamaño sugiere
  que supera MAX_LINES (comprobado con os.stat antes de abrir); y no se reescribe
  el archivo si no hay nada que podar. La ventana de 7 días se aplica TAMBIÉN al
  LEER (last_seen, ronda 4 / M2): una entrada con ts fuera de la ventana no
  autoriza aunque el ledger tenga actividad reciente y la poda no haya corrido.
- TOCTOU de la huella (ronda 4 / H1): el pre de read_file deja una entrada
  pendiente {'ev': 'read_pending', 'path', 'mtime_ns', 'size', 't'} con la huella
  ANTES de la lectura; el post ok la promueve a 'seen' con ESA huella (lo que el
  agente vio), no con la de disco al llegar el post.
- Última entrada por `path` gana (comparación por `os.path.realpath`).

Solo stdlib. Ninguna función de este módulo debe lanzar hacia el hook:
las operaciones de E/S se cuidan de degradar a "sin registro" antes que fallar.
"""

import fcntl
import hashlib
import json
import os
import sys
import time
from pathlib import Path

DEFAULT_ROOT = Path("/opt/hermes-agent-data/state/hooks/read-before-patch")
RETENTION_DAYS = 7
MAX_LINES = 5000
PRUNE_IDLE_S = 3600  # poda solo si el ledger lleva > 1 hora sin tocar (mtime)
# Cota inferior conservadora de bytes por línea JSONL (~40): si el archivo pesa
# menos que MAX_LINES * MIN_LINE_BYTES, seguro tiene menos de MAX_LINES líneas
# y la poda no hace falta ni intentarla (chequeo barato con os.stat, sin abrir).
MIN_LINE_BYTES = 40
DIGEST_CAP = 32 * 1024 * 1024  # no hashear archivos gigantes; fp-only arriba del cap

# Ronda 7 / H-A: el contenido previo que captura el pre para la certificación
# del post vive en un snapshot EFÍMERO fuera del ledger (el ledger JSONL jamás
# contiene contenido de archivo, 02-design §4). La poda barre huérfanos con
# este TTL corto (crash antes del post, archivos no consumidos).
SNAP_TTL_S = 600  # 10 minutos
SNAP_DIR_MODE = 0o700
SNAP_FILE_MODE = 0o600

_EV_POST = "post_tool_call"
_EV_READ_PENDING = "read_pending"
_EV_WRITE_PENDING = "write_pending"


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


def snapshots_dir(session_id, root=None) -> Path:
    """Directorio de snapshots efímeros de la sesión (ronda 7 / H-A):
    <root>/snapshots/<session>/ — 0700. Los snapshots (.snap) son archivos
    0600 con contenido previo de archivos, fuera del ledger JSONL."""
    base = Path(root) if root is not None else DEFAULT_ROOT
    return base / "snapshots" / _safe_session(session_id)


def _safe_call_id(call_id) -> str:
    """Nombre de archivo seguro para un call_id (puede venir derivado con ':' o
    ser None): mismo juego de caracteres que _safe_session."""
    raw = str(call_id) if call_id else ""
    safe = "".join(c if (c.isalnum() or c in "-_.") else "_" for c in raw)
    return safe or "call"


def snapshot_write(session_id, path, root=None, call_id=None):
    """Copia el contenido previo de `path` a un snapshot EFÍMERO fuera del
    ledger (ronda 7 / H-A): <root>/snapshots/<session>/<call_id>.snap, con
    directorio 0700 y archivo 0600 (open con modo 0600 + chmod para blindar
    contra umask). Devuelve la ruta del snapshot, o None si no se pudo escribir
    (permisos/ENOSPC o archivo > DIGEST_CAP): el post cae fail-closed en vez de
    certificar la huella de disco. Nunca lanza."""
    try:
        if os.path.getsize(str(path)) > DIGEST_CAP:
            return None
        with open(str(path), "r", encoding="utf-8", errors="surrogateescape") as f:
            content = f.read()
        d = snapshots_dir(session_id, root)
        d.mkdir(parents=True, exist_ok=True)
        os.chmod(str(d), SNAP_DIR_MODE)
        name = _safe_call_id(call_id) if call_id else "snap-" + os.urandom(8).hex()
        target = d / (name + ".snap")
        fd = os.open(str(target), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, SNAP_FILE_MODE)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", errors="surrogateescape") as f:
                f.write(content)
        except Exception:
            try:
                os.unlink(str(target))
            except OSError:
                pass
            return None
        try:
            os.chmod(str(target), SNAP_FILE_MODE)
        except OSError:
            pass
        return str(target)
    except Exception:
        return None


def snapshot_read(snap_path):
    """Lee el contenido de un snapshot efímero (None si no existe/ilegible)."""
    try:
        with open(str(snap_path), "r", encoding="utf-8", errors="surrogateescape") as f:
            return f.read()
    except OSError:
        return None


def snapshot_delete(snap_path) -> None:
    """Borra un snapshot efímero (el post que lo consume; barrido TTL)."""
    try:
        os.unlink(str(snap_path))
    except OSError:
        pass


def sweep_snapshots(root=None, now=None) -> None:
    """Barrido TTL de snapshots huérfanos (ronda 7 / H-A): borra los .snap con
    mtime anterior a SNAP_TTL_S y los directorios de sesión que quedan vacíos.
    Corre enganchado al gate barato de la poda oportunista (ronda 2 / H3) en
    _append. Nunca lanza."""
    base = Path(root) if root is not None else DEFAULT_ROOT
    cutoff = (time.time() if now is None else float(now)) - SNAP_TTL_S
    try:
        sessions = list((base / "snapshots").iterdir())
    except OSError:
        return
    for sess in sessions:
        try:
            if not sess.is_dir():
                continue
            entries = list(sess.iterdir())
        except OSError:
            continue
        empty = True
        for p in entries:
            try:
                if p.suffix == ".snap" and p.is_file() and p.stat().st_mtime < cutoff:
                    snapshot_delete(p)
                else:
                    empty = False
            except OSError:
                empty = False
        if empty:
            try:
                os.rmdir(str(sess))
            except OSError:
                pass


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
    tamaño dentro del mismo tick comparten (mtime_ns, size) pero no contenido.
    Se guarda SOLO el hexdigest (nunca contenido) y se calcula en cada record()
    y en el pre únicamente cuando (mtime_ns, size) coinciden (02-design §4)."""
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
    """Lee el ledger tolerando líneas corruptas/vacías (se ignoran, no rompen).

    Toma flock COMPARTIDO (LOCK_SH) mientras lee (ronda 2 / H2): los procesos
    del hook son one-shot sin estado en memoria, y la poda del writer trabaja
    bajo LOCK_EX reescribiendo el archivo; sin el lock compartido la lectura
    ve el archivo a medias y devuelve None para entradas que ya existían."""
    try:
        f = open(str(ledger), "r", encoding="utf-8")
    except OSError:
        return []
    try:
        fcntl.flock(f.fileno(), fcntl.LOCK_SH)
        try:
            raw = f.read()
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except OSError:
        return []
    entries = []
    for line in raw.splitlines():
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


def _should_attempt_prune(ledger: Path, now: float):
    """Chequeo barato con os.stat ANTES de abrir (ronda 2 / H3). Devuelve la razón
    de la poda o None: 'stale' (ledger sin tocar hace más de PRUNE_IDLE_S) o
    'size' (su tamaño hace posible que supere MAX_LINES). Un hook one-shot con
    un ledger pequeño y reciente (el caso común) no toca la poda en absoluto."""
    try:
        st = os.stat(str(ledger))
    except OSError:
        return None
    if now - st.st_mtime > PRUNE_IDLE_S:
        return "stale"
    if st.st_size > MAX_LINES * MIN_LINE_BYTES:
        return "size"
    return None


def _cleanup_locked(f, now: float, reason: str = "stale") -> None:
    """Poda por retención (7 días o 5.000 líneas). Debe llamarse con el lock tomado
    y `f` en modo 'a+' (lectura y append). NO reescribe si no hay nada que podar."""
    try:
        f.seek(0)
        raw = f.read()
    except OSError:
        return
    if reason == "size":
        # Gatillado solo por tamaño: recorte textual FIFO al tope de MAX_LINES,
        # sin parsear JSON (las líneas recientes del tope se conservan tal cual).
        lines = raw.splitlines()
        if len(lines) <= MAX_LINES:
            return  # sin exceso real: no reescribir
        kept = lines[-MAX_LINES:]
    else:
        # Gatillado por mtime (> 1 h): poda por retención (7 días) + tope.
        cutoff = now - RETENTION_DAYS * 86400
        total = 0
        kept = []
        for line in raw.splitlines():
            total += 1
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
        if len(kept) == total:
            return  # nada que podar: no reescribir el archivo
    try:
        f.seek(0)
        f.truncate()
        if kept:
            f.write("\n".join(kept) + "\n")
        f.flush()
    except OSError:
        pass


def _append(session_id, entry: dict, root=None) -> None:
    """Escribe una línea en el ledger bajo flock exclusivo. La poda oportunista
    se decide ANTES de abrir con os.stat (mtime > 1 h o posible exceso de
    líneas); el caso común (ledger reciente y pequeño) es un append puro."""
    ledger = ledger_path(session_id, root)
    ledger.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(entry, ensure_ascii=False)
    now = float(entry.get("ts") or time.time())
    prune_reason = _should_attempt_prune(ledger, now)
    with open(ledger, "a+", encoding="utf-8") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            f.write(line + "\n")
            f.flush()
            if prune_reason:
                _cleanup_locked(f, now, reason=prune_reason)
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    if prune_reason:
        # Ronda 7 / H-A: barrido TTL de snapshots huérfanos, enganchado al
        # mismo gate barato de la poda oportunista (ronda 2 / H3: no corre en
        # cada invocación, solo cuando el gate de os.stat dispara).
        sweep_snapshots(root)


def record_seen(session_id, tool, path, mtime_ns, size, ok=True, root=None, sha256=None):
    """Registra una huella YA capturada (ronda 4 / H1): la promoción de una
    entrada 'read_pending' usa la huella del contenido que el agente VIO, no la
    de disco al llegar el post. El digest solo se adjunta si la huella registrada
    coincide con el disco AHORA (si difiere, el sha256 sería de un contenido que
    el agente nunca vio y el desempate del pre daría un falso permiso).
    Ronda 5 / H2: `sha256` explícito (hexdigest de la intención reconstruida por
    el guard, p. ej. sha256 de tool_input['content'] tras verificar que coincide
    con el disco) se registra tal cual y tiene precedencia sobre el cálculo."""
    p = str(path)
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
    if sha256:
        entry["sha256"] = str(sha256)
    elif mtime_ns and size and tuple(fingerprint(p)) == (mtime_ns, size):
        digest = file_digest(p)
        if digest:
            entry["sha256"] = digest
    try:
        _append(session_id, entry, root=root)
    except Exception as exc:
        # fail-open: sin ledger no hay guard y el hook sigue, pero el fallo no
        # se traga en silencio (ronda 2 / L7): va a stderr para el runner.
        print(
            "read-before-patch: record_seen() no pudo escribir el ledger (%s): %s"
            % (type(exc).__name__, exc),
            file=sys.stderr,
        )


def record(session_id, tool, path, ok=True, root=None, sha256=None) -> None:
    """Registra (path, huella actual) para un tool de lectura/escritura.
    La huella se toma AHORA: el agente vio/escribió este contenido.
    (El post de read_file usa record_seen() con la huella pendiente del pre
    para cerrar la ventana TOCTOU, ronda 4 / H1.) `sha256` explícito se pasa
    tal cual a record_seen (ronda 5 / H2)."""
    p = str(path)
    mtime_ns, size = fingerprint(p)
    record_seen(session_id, tool, p, mtime_ns, size, ok=ok, root=root, sha256=sha256)


def _within_retention(entry: dict, cutoff: float) -> bool:
    """True si la entrada no está (o no se puede probar que esté) fuera de la
    ventana de retención de RETENTION_DAYS (ronda 4 / M2). Sin ts no hay edad
    conocida: se conserva (la poda por 't' ISO la limpiará a su momento)."""
    ts = entry.get("ts") if isinstance(entry, dict) else None
    if isinstance(ts, (int, float)):
        return ts >= cutoff
    return True


def last_seen(session_id, path, root=None):
    """Última entrada registrada para la ruta (por realpath) o None.
    Devuelve {'path', 'mtime_ns', 'size', 'tool', 't'} (más campos extra del ledger).
    Lectura bajo flock compartido vía _read_entries (ronda 2 / H2).
    Ronda 4 / M2: las entradas con ts anterior a la ventana de retención
    (RETENTION_DAYS) NO autorizan aunque el ledger tenga actividad reciente y
    la poda oportunista no haya corrido: el corte se aplica AL LEER, no solo
    al podar."""
    ledger = ledger_path(session_id, root)
    if not ledger.exists():
        return None
    try:
        want = os.path.realpath(str(path))
    except OSError:
        want = str(path)
    cutoff = time.time() - RETENTION_DAYS * 86400
    found = None
    for entry in _read_entries(ledger):
        if entry.get("ev") != _EV_POST:
            continue  # would_block / error / disabled no cuentan como "visto"
        if not _within_retention(entry, cutoff):
            continue  # M2: vencida, no autoriza
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


def _pending_entries(session_id, path, ev, root=None) -> list:
    """Todas las pendientes vivas `ev` de la ruta (por realpath), en orden de ledger.
    Común a read_pending y write_pending (ronda 6 / B1-B2)."""
    ledger = ledger_path(session_id, root)
    if not ledger.exists():
        return []
    try:
        want = os.path.realpath(str(path))
    except OSError:
        want = str(path)
    out = []
    for entry in _read_entries(ledger):
        if entry.get("ev") != ev:
            continue
        p = entry.get("path")
        if not isinstance(p, str) or not p:
            continue
        try:
            same = os.path.realpath(p) == want
        except OSError:
            same = p == want
        if same:
            out.append(entry)
    return out


def pending_read_match(session_id, path, root=None, call_id=None):
    """Empareje de la pendiente de lectura con el post (ronda 6 / B1).
    Devuelve (estado, entrada|None) con estado en:
      'match'     -> entrada correspondiente a ESTA llamada;
      'ambiguous' -> hay varias pendientes del mismo path y ninguna se puede
                     atribuir con certeza: el post NO debe promover ninguna
                     huella (fail-closed);
      'none'      -> sin pendiente (payload legacy sin pre): el post conserva
                     el comportamiento de antes (huella de disco).
    Empareje (en orden):
      1. por `call_id` (extra.tool_call_id o identificador derivado del payload
         pre que el post recalcula igual): gana la pendiente con ese call_id;
      2. sin call_id útil: SOLO si hay EXACTAMENTE una pendiente viva del path
         se asume que corresponde a la lectura en curso (contrato 1:1 pre/post
         de la ronda 4); con más de una es ambiguo y no se promueve nada.
    """
    lst = _pending_entries(session_id, path, _EV_READ_PENDING, root)
    if call_id:
        matched = [e for e in lst if e.get("call_id") == call_id]
        if len(matched) > 1:
            # Varios pendientes con el MISMO call_id (p. ej. ids derivados de
            # payloads idénticos en lecturas intercaladas): tampoco se puede
            # atribuir la huella a esta llamada -> fail-closed (ronda 6 / B1).
            return "ambiguous", None
        if matched:
            return "match", matched[-1]
        if len(lst) == 1:
            return "match", lst[0]  # call_id del post inútil (pre legacy): 1:1 igual
        if len(lst) > 1:
            return "ambiguous", None
        return "none", None
    if len(lst) == 1:
        return "match", lst[0]
    if len(lst) > 1:
        return "ambiguous", None  # B1: sin call_id y varias pendientes -> nada
    return "none", None


def pending_read(session_id, path, root=None):
    """Entrada 'read_pending' de la lectura en curso o None (ronda 4 / H1).
    Wrapper simple sobre pending_read_match() (ronda 6 / B1): None también
    cubre el caso ambiguo, así que el llamador que necesite distinguir
    'sin pendiente' de 'ambigua' debe usar pending_read_match()."""
    _st, entry = pending_read_match(session_id, path, root=root)
    return entry


def pending_write_match(session_id, path, root=None, call_id=None):
    """Empareje de la pendiente de ESCRITURA (snapshot del contenido previo
    capturado en el PRE de patch/edit_file, ronda 6 / B2). Mismas reglas de
    pending_read_match(): por call_id; fallback 1:1 solo con exactamente una
    pendiente viva; ambiguo -> no certificar."""
    lst = _pending_entries(session_id, path, _EV_WRITE_PENDING, root)
    if call_id:
        matched = [e for e in lst if e.get("call_id") == call_id]
        if len(matched) > 1:
            return "ambiguous", None  # mismo call_id en varias pendientes
        if matched:
            return "match", matched[-1]
        if len(lst) == 1:
            return "match", lst[0]
        if len(lst) > 1:
            return "ambiguous", None
        return "none", None
    if len(lst) == 1:
        return "match", lst[0]
    if len(lst) > 1:
        return "ambiguous", None
    return "none", None


def has_event(session_id, ev, root=None) -> bool:
    """True si el ledger de la sesión ya contiene un evento administrativo `ev`
    (lectura bajo LOCK_SH). Lo usa el kill switch para no loguear 'disabled'
    más de una vez entre procesos (ronda 2 / L1)."""
    ledger = ledger_path(session_id, root)
    if not ledger.exists():
        return False
    for entry in _read_entries(ledger):
        if entry.get("ev") == ev:
            return True
    return False


def log_event(session_id, ev, root=None, **fields) -> None:
    """Registra un evento administrativo del guard (would_block / error / disabled).
    Nunca lanza: sin ledger no hay registro, pero el hook sigue."""
    now = time.time()
    entry = {"t": _iso(now), "ts": now, "ev": str(ev)}
    entry.update(fields)
    try:
        _append(session_id, entry, root=root)
    except Exception as exc:
        print(
            "read-before-patch: log_event(%s) no pudo escribir el ledger (%s): %s"
            % (ev, type(exc).__name__, exc),
            file=sys.stderr,
        )


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
