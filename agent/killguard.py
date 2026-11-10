"""Identity-checked process-group and PID signalling (HERMES-KILLGUARD).

``os.killpg(os.getpgid(pid), SIG)`` resolves the group of whatever process holds ``pid``
*right now*. If the original child already exited and the PID was recycled, that resolves
to an innocent, unrelated group — and its scripts die with SIGTERM (exit code -15). That is
how cron jobs of other profiles were killed on 17-18 Oct 2026 (Jacqueline's morning report,
the Golden/Lucky sales captures, soul-plugin-guard).

The fix: every group/PID signal carries the target's kernel start time (field 22 of
``/proc/<pid>/stat``, stable for the life of the process). The stamp is pinned when the
identity is still guaranteed — at spawn for a ``Popen`` child, at entry for an already
running PID — and re-checked immediately before signalling. A changed or missing stamp
means "not our process anymore": refuse, log, and let the caller fall back.

Rule for callers: never derive ``expected_starttime`` from the same lookup you are about to
signal (that check would be vacuous).
"""
from __future__ import annotations

import logging
import os
import traceback

logger = logging.getLogger(__name__)


def proc_starttime(pid):
    """Kernel start time of ``pid`` (field 22 of /proc/<pid>/stat); None if gone."""
    try:
        with open("/proc/%d/stat" % int(pid), "rb") as fh:
            raw = fh.read()
        tail = raw[raw.rindex(b")") + 2:].split()
        return int(tail[19])
    except Exception:
        return None


def _caller(limit=10):
    try:
        stack = traceback.format_stack(limit=limit)[:-1]
        out = []
        for frame in stack[-3:]:
            line = frame.strip().splitlines()[0].strip()
            out.append(line.replace('File "', "").replace('", line ', ":").rstrip(","))
        return " <- ".join(reversed(out))
    except Exception:
        return "?"


def log_signal(site, pid, pgid, starttime):
    logger.info("killguard: %s pid=%s pgid=%s starttime=%s caller=%s",
                site, pid, pgid, starttime, _caller())


def log_refused(site, reason, pid, pgid=None):
    logger.warning("killguard: REFUSED %s pid=%s pgid=%s — %s caller=%s",
                   site, pid, pgid, reason, _caller())


def safe_killpg(pgid, sig, *, expected_starttime=None, site=""):
    """killpg that refuses a recycled group leader. True when a signal was delivered."""
    try:
        pgid = int(pgid)
    except Exception:
        return False
    try:
        if pgid <= 1 or pgid == os.getpgid(0):
            log_refused(site or "killguard.safe_killpg", "pgid protegido", pgid, pgid)
            return False
    except Exception:
        return False
    if expected_starttime is None:
        # Sin sello no hay forma de probar que el grupo sigue siendo nuestro: jamás se señala.
        log_refused(site or "killguard.safe_killpg", "sin starttime de referencia", pgid, pgid)
        return False
    now = proc_starttime(pgid)
    if now != expected_starttime:
        log_refused(site or "killguard.safe_killpg",
                    "líder reciclado (starttime esperado %s, encontrado %s)"
                    % (expected_starttime, now), pgid, pgid)
        return False
    try:
        os.killpg(pgid, sig)
        return True
    except (ProcessLookupError, PermissionError, OSError):
        return False


def safe_kill(pid, sig, *, expected_starttime=None, site=""):
    """``os.kill`` that refuses a recycled PID. True when a signal was delivered."""
    try:
        pid = int(pid)
    except Exception:
        return False
    try:
        if pid <= 1 or pid == os.getpid():
            log_refused(site or "killguard.safe_kill", "pid protegido", pid)
            return False
    except Exception:
        return False
    if expected_starttime is None:
        log_refused(site or "killguard.safe_kill", "sin starttime de referencia", pid)
        return False
    now = proc_starttime(pid)
    if now is None:
        # Ya no existe: no es un reciclado, es un proceso que terminó. No se señala y no se
        # grita "reciclado" (evita ruido en PROD con recolección rápida de s6/init).
        logger.debug("killguard: %s pid=%s ya no existe", site or "killguard.safe_kill", pid)
        return False
    if now != expected_starttime:
        log_refused(site or "killguard.safe_kill",
                    "PID reciclado (starttime esperado %s, encontrado %s)"
                    % (expected_starttime, now), pid)
        return False
    try:
        os.kill(pid, sig)
        return True
    except (ProcessLookupError, PermissionError, OSError):
        return False
