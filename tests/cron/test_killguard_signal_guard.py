"""Regression tests for the HERMES-KILLGUARD signal guard.

``os.killpg(os.getpgid(pid), SIG)`` on a PID that already exited resolves to whatever
process holds that PID *now*; when that process leads its own group the signal kills an
innocent group. Cron scripts of unrelated jobs died that way with SIGTERM (exit -15)
on 17-18 Oct 2026, and again on 14 Nov 2026 after an image rebuild (2026-11-10) shipped
``cron/scheduler_script.py`` / ``agent/deadline.py`` without the guard. These tests pin
both halves of the contract: the guard module must exist and be wired into the two
signalling sites, and it must refuse a recycled identity while still delivering to the
process it was asked to signal.
"""

from __future__ import annotations

import os
import signal
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _source(rel: str) -> str:
    return (REPO_ROOT / rel).read_text(encoding="utf-8")


def test_killguard_module_is_present_and_marked():
    """The guard module ships with the tree (an update must not silently drop it)."""
    from agent import killguard

    assert "HERMES-KILLGUARD" in (killguard.__doc__ or "")
    assert callable(killguard.safe_killpg)
    assert callable(killguard.proc_starttime)


@pytest.mark.parametrize(
    "rel",
    ["cron/scheduler_script.py", "agent/deadline.py"],
)
def test_signalling_sites_are_guarded(rel: str):
    """Both sites that signal a process group/ pid route through the guard."""
    src = _source(rel)
    assert "HERMES-KILLGUARD" in src, f"{rel} lost its KILLGUARD wrap"
    assert "safe_killpg(" in src, f"{rel} no longer calls killguard.safe_killpg"


def _child_in_own_group():
    """A live child that leads its own session/group (so killpg would reach it)."""
    return subprocess.Popen(
        ["sleep", "30"], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )


def test_safe_killpg_refuses_a_recycled_group_leader():
    from agent import killguard

    proc = _child_in_own_group()
    try:
        pgid = os.getpgid(proc.pid)
        assert pgid == proc.pid, "child must lead its own group for this test"
        live = killguard.proc_starttime(pgid)
        assert live is not None

        delivered = killguard.safe_killpg(
            pgid, signal.SIGTERM, expected_starttime=live + 1, site="test.recycled"
        )
        assert delivered is False, "a mismatched starttime must refuse the signal"
        assert proc.poll() is None, "the innocent group must have received nothing"
    finally:
        proc.kill()
        proc.wait(timeout=5)


def test_safe_killpg_refuses_protected_groups():
    from agent import killguard

    own = os.getpgid(0)
    assert killguard.safe_killpg(1, signal.SIGTERM, expected_starttime=1, site="test.init") is False
    assert killguard.safe_killpg(own, signal.SIGTERM, expected_starttime=1, site="test.own") is False
    assert killguard.safe_killpg("not-an-int", signal.SIGTERM, site="test.bad") is False


def test_safe_killpg_delivers_when_identity_matches():
    """The guard must not swallow legitimate terminations."""
    from agent import killguard

    proc = _child_in_own_group()
    try:
        pgid = os.getpgid(proc.pid)
        stamp = killguard.proc_starttime(pgid)
        delivered = killguard.safe_killpg(
            pgid, signal.SIGTERM, expected_starttime=stamp, site="test.deliver"
        )
        assert delivered is True
        assert proc.wait(timeout=5) == -signal.SIGTERM
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)


def test_safe_kill_refuses_a_recycled_pid():
    """Phase 2: the direct os.kill(pid) branch refuses a recycled PID too."""
    from agent import killguard

    assert callable(getattr(killguard, "safe_kill", None)), "phase-2 safe_kill missing"

    proc = _child_in_own_group()
    try:
        stamp = killguard.proc_starttime(proc.pid)
        assert killguard.safe_kill(
            proc.pid, signal.SIGTERM, expected_starttime=stamp + 1, site="test.pid-recycled"
        ) is False
        assert proc.poll() is None

        assert killguard.safe_kill(os.getpid(), signal.SIGTERM, expected_starttime=stamp) is False
        assert killguard.safe_kill(proc.pid, signal.SIGTERM, site="test.no-stamp") is False
    finally:
        proc.kill()
        proc.wait(timeout=5)


def test_safe_kill_delivers_when_identity_matches():
    from agent import killguard

    proc = _child_in_own_group()
    try:
        stamp = killguard.proc_starttime(proc.pid)
        assert killguard.safe_kill(
            proc.pid, signal.SIGTERM, expected_starttime=stamp, site="test.pid-deliver"
        ) is True
        assert proc.wait(timeout=5) == -signal.SIGTERM
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)


def test_registrar_pid_senalado_acota_el_set():
    """El registro de pids senalados por el runner no puede crecer sin techo."""
    from cron import scheduler_script as ss

    before = set(ss._PIDS_SENALADOS)
    ss._PIDS_SENALADOS.clear()
    try:
        for i in range(ss._PIDS_SENALADOS_MAX + 5):
            ss._registrar_pid_senalado(900000 + i)
        assert len(ss._PIDS_SENALADOS) <= ss._PIDS_SENALADOS_MAX
        assert (900000 + ss._PIDS_SENALADOS_MAX + 4) in ss._PIDS_SENALADOS
    finally:
        ss._PIDS_SENALADOS.clear()
        ss._PIDS_SENALADOS.update(before)
