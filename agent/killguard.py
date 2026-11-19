"""Identity-checked process signalling (HERMES-KILLGUARD, 18-oct-2026).

``os.killpg(os.getpgid(pid), SIG)`` on a PID that already exited resolves to whatever
process holds that PID *now*. If that process leads its own group, the signal kills an
innocent group — that is how cron scripts of unrelated jobs died with SIGTERM (exit -15)
on 17-18 Oct 2026 (Jacqueline's morning report, the Golden/Lucky sales captures,
soul-plugin-guard) and again on 14 Nov 2026 after the 2026-11-10 image rebuild shipped
``cron/scheduler_script.py`` and ``agent/deadline.py`` without the wrap.

Every guarded signal re-reads the target's kernel start time (field 22 of
``/proc/<pid>/stat``) and is refused when it no longer matches the value captured at the
call site. Behaviour when the reference start time is unavailable differs on purpose:
``safe_killpg`` fails *open* (signals anyway and logs the degradation) because refusing
would leave alive the script tree the cron runner is actively stopping, while
``safe_kill`` fails *closed* (refuses), as its callers have no group-level fallback.
"""
from __future__ import annotations

import logging
import os
import traceback
from typing import Optional

logger = logging.getLogger(__name__)


def proc_starttime(pid: int) -> Optional[int]:
    """Kernel start time of ``pid`` (field 22 of ``/proc/<pid>/stat``); None if unreadable/gone."""
    try:
        with open("/proc/%d/stat" % int(pid), "rb") as fh:
            raw = fh.read()
        tail = raw[raw.rindex(b")") + 2:].split()
        return int(tail[19])
    except Exception as exc:
        logger.debug("killguard: proc_starttime(%r) no disponible: %s", pid, exc)
        return None


def _caller(limit: int = 10) -> str:
    """Compact ``caller=`` attribution (last three stack frames) for killguard log lines."""
    try:
        stack = traceback.format_stack(limit=limit)[:-1]
        out = []
        for frame in stack[-3:]:
            line = frame.strip().splitlines()[0].strip()
            out.append(line.replace('File "', "").replace('", line ', ":").rstrip(","))
        return " <- ".join(reversed(out))
    except Exception as exc:
        logger.debug("killguard: no pude resolver el caller: %s", exc)
        return "?"


def log_signal(site: str, pid: Optional[int], pgid: Optional[int],
               starttime: Optional[int]) -> None:
    """Audit line recording every group signal a guarded call site attempts."""
    logger.info("killguard: %s pid=%s pgid=%s starttime=%s caller=%s",
                site, pid, pgid, starttime, _caller())


def safe_killpg(pgid: int, sig: int, *, expected_starttime: Optional[int] = None,
                site: str = "") -> bool:
    """killpg that refuses a recycled group leader (HERMES-KILLGUARD).

    Args:
        pgid: Process group to signal.
        sig: Signal number.
        expected_starttime: Leader start time captured at the call site. ``None`` logs a
            ``DEGRADED`` warning and signals anyway (fail open — see module docstring);
            a mismatch refuses the signal and logs ``REFUSED`` with both values.
        site: Log attribution of the calling site.

    Returns:
        True only when ``os.killpg`` was reached and did not raise.
    """
    try:
        pgid = int(pgid)
    except Exception as exc:
        logger.warning("killguard: refused %s sig=%s: pgid %r no es int (%s)",
                       site, sig, pgid, exc)
        return False
    try:
        if pgid <= 1 or pgid == os.getpgid(0):
            logger.warning("killguard: refused %s sig=%s: pgid %s is protected",
                           site, sig, pgid)
            return False
    except Exception as exc:
        logger.warning("killguard: refused %s sig=%s pgid=%s: no pude validar el grupo (%s)",
                       site, sig, pgid, exc)
        return False
    if expected_starttime is None:
        logger.warning(
            "killguard: DEGRADED %s sig=%s pgid=%s — sin starttime de referencia: "
            "senal sin verificacion de identidad (fail-open)", site, sig, pgid)
    else:
        now = proc_starttime(pgid)
        if now != expected_starttime:
            logger.warning(
                "killguard: REFUSED %s sig=%s pgid=%s — leader recycled "
                "(starttime esperado %s, encontrado %s) caller=%s",
                site, sig, pgid, expected_starttime, now, _caller())
            return False
    try:
        os.killpg(pgid, sig)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        logger.warning("killguard: delivered %s sig=%s pgid=%s bloqueado por permisos",
                       site, sig, pgid)
        return False
    except OSError as exc:
        logger.warning("killguard: killpg(%s, %s) en %s fallo: %s", pgid, sig, site, exc)
        return False


def safe_kill(pid: int, sig: int, *, expected_starttime: Optional[int] = None,
              site: str = "") -> bool:
    """os.kill that refuses a recycled PID (HERMES-KILLGUARD-PID).

    Args:
        pid: Process to signal.
        sig: Signal number.
        expected_starttime: Target start time captured at the call site. ``None`` refuses
            the signal (fail closed — no group-level fallback exists here).
        site: Log attribution of the calling site.

    Returns:
        True only when ``os.kill`` was reached and did not raise.
    """
    try:
        pid = int(pid)
    except Exception as exc:
        logger.warning("killguard: refused %s sig=%s: pid %r no es int (%s)",
                       site, sig, pid, exc)
        return False
    try:
        if pid <= 1 or pid == os.getpid():
            logger.warning("killguard: refused %s sig=%s: pid %s is protected",
                           site, sig, pid)
            return False
    except Exception as exc:
        logger.warning("killguard: refused %s sig=%s pid=%s: validacion fallo (%s)",
                       site, sig, pid, exc)
        return False
    if expected_starttime is None:
        logger.warning("killguard: refused %s sig=%s pid=%s: sin starttime de referencia",
                       site, sig, pid)
        return False
    now = proc_starttime(pid)
    if now != expected_starttime:
        logger.warning(
            "killguard: REFUSED %s sig=%s pid=%s — PID reciclado "
            "(starttime esperado %s, encontrado %s) caller=%s",
            site, sig, pid, expected_starttime, now, _caller())
        return False
    try:
        os.kill(pid, sig)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        logger.warning("killguard: delivered %s sig=%s pid=%s bloqueado por permisos",
                       site, sig, pid)
        return False
    except OSError as exc:
        logger.warning("killguard: kill(%s, %s) en %s fallo: %s", pid, sig, site, exc)
        return False
