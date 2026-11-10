"""HERMES-KILLGUARD — group/PID signals must refuse a recycled identity.

Regression cover for the "Script exited with code -15" deaths: a cron/verify child exited,
its PID was recycled by an unrelated process, and the scheduler's process-group signal landed
on the *new* process's group, killing another job's script.

The guard's contract: a group or PID is only signalled while its kernel start time still
matches the stamp pinned when the identity was guaranteed (spawn time for ``Popen`` children,
function entry for an already-running PID).
"""
from __future__ import annotations

import contextlib
import os
import signal
import subprocess

import pytest

pytestmark = pytest.mark.skipif(os.name != "posix", reason="POSIX process-group semantics")


class _FakeProc:
    """Minimal ``Popen`` stand-in: no real child, records wait/kill."""

    def __init__(self, pid: int, starttime: int | None = None) -> None:
        self.pid = pid
        if starttime is not None:
            self.hermes_starttime = starttime
        self.waited = False
        self.killed = False

    def poll(self):
        return None

    def wait(self, timeout=None):
        self.waited = True
        return 0

    def kill(self):
        self.killed = True


@pytest.fixture()
def killpg_calls(monkeypatch):
    calls: list[tuple[int, int]] = []
    monkeypatch.setattr(os, "killpg", lambda pgid, sig: calls.append((pgid, sig)))
    return calls


@pytest.fixture()
def kill_calls(monkeypatch):
    calls: list[tuple[int, int]] = []
    monkeypatch.setattr(os, "kill", lambda pid, sig: calls.append((pid, sig)))
    return calls


class TestKillguardPrimitives:
    def test_safe_killpg_refuses_recycled_leader(self, monkeypatch, killpg_calls):
        from agent import killguard

        monkeypatch.setattr(killguard, "proc_starttime", lambda pid: 999)
        assert killguard.safe_killpg(4242, signal.SIGTERM, expected_starttime=111, site="t") is False
        assert killpg_calls == []

    def test_safe_killpg_delivers_when_identity_matches(self, monkeypatch, killpg_calls):
        from agent import killguard

        monkeypatch.setattr(killguard, "proc_starttime", lambda pid: 111)
        assert killguard.safe_killpg(4242, signal.SIGTERM, expected_starttime=111, site="t") is True
        assert killpg_calls == [(4242, signal.SIGTERM)]

    def test_safe_killpg_refuses_own_group(self, killpg_calls):
        from agent import killguard

        assert killguard.safe_killpg(os.getpgid(0), signal.SIGTERM, site="t") is False
        assert killpg_calls == []

    def test_safe_killpg_refuses_without_reference_stamp(self, killpg_calls):
        from agent import killguard

        assert killguard.safe_killpg(4242, signal.SIGTERM, site="t") is False
        assert killpg_calls == []

    def test_safe_kill_refuses_without_reference_stamp(self, kill_calls):
        from agent import killguard

        assert killguard.safe_kill(4242, signal.SIGTERM, site="t") is False
        assert kill_calls == []


class TestCronScriptGroupTermination:
    def test_refuses_when_leader_was_recycled(self, monkeypatch, killpg_calls):
        from cron import scheduler_script

        monkeypatch.setattr(os, "getpgid", lambda pid: pid)
        monkeypatch.setattr(scheduler_script.killguard, "proc_starttime", lambda pid: 777)
        proc = _FakeProc(pid=4242, starttime=111)

        scheduler_script._terminate_process_group(proc)

        assert killpg_calls == []

    def test_refuses_a_group_another_pid_leads(self, monkeypatch, killpg_calls):
        from cron import scheduler_script

        monkeypatch.setattr(os, "getpgid", lambda pid: 9999)
        monkeypatch.setattr(scheduler_script.killguard, "proc_starttime", lambda pid: 111)
        proc = _FakeProc(pid=4242, starttime=111)

        scheduler_script._terminate_process_group(proc)

        assert killpg_calls == []

    def test_refuses_when_spawn_stamp_is_missing(self, monkeypatch, killpg_calls):
        from cron import scheduler_script

        monkeypatch.setattr(os, "getpgid", lambda pid: pid)
        proc = _FakeProc(pid=4242)  # no hermes_starttime pinned at spawn

        scheduler_script._terminate_process_group(proc)

        assert killpg_calls == []

    def test_signals_its_own_group_once_leader_is_gone(self, monkeypatch, killpg_calls):
        from cron import scheduler_script

        monkeypatch.setattr(os, "getpgid", lambda pid: pid)
        stamps = [111, None]  # matched at TERM, gone at the probe
        monkeypatch.setattr(scheduler_script.killguard, "proc_starttime",
                            lambda pid: stamps.pop(0) if stamps else None)
        proc = _FakeProc(pid=4242, starttime=111)

        scheduler_script._terminate_process_group(proc)

        assert killpg_calls == [(4242, signal.SIGTERM)]
        assert proc.waited

    def test_orphans_in_the_group_are_killed_by_their_own_identity(self, monkeypatch, killpg_calls, kill_calls):
        """Líder recolectado + miembros vivos: se rematan por su starttime, nunca por el grupo."""
        from cron import scheduler_script

        monkeypatch.setattr(os, "getpgid", lambda pid: pid)
        state = {"checks": 0}

        def fake_start(pid):
            if pid == 5151:
                return 777  # el huérfano sigue vivo y con su identidad
            state["checks"] += 1
            return 111 if state["checks"] == 1 else None  # el líder desaparece tras el TERM

        monkeypatch.setattr(scheduler_script.killguard, "proc_starttime", fake_start)
        scans = [{"4242": 111}, {"5151": 777}]  # 1er scan antes del TERM, 2º tras la gracia
        monkeypatch.setattr(scheduler_script, "_group_members",
                            lambda pgid: scans.pop(0) if scans else {})
        proc = _FakeProc(pid=4242, starttime=111)

        scheduler_script._terminate_process_group(proc)

        assert killpg_calls == [(4242, signal.SIGTERM)]
        assert kill_calls == [(5151, signal.SIGKILL)]

    def test_real_child_group_is_terminated(self):
        from agent import killguard
        from cron import scheduler_script

        proc = subprocess.Popen(
            ["sleep", "60"], start_new_session=True,
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        setattr(proc, "hermes_starttime", killguard.proc_starttime(proc.pid))
        try:
            scheduler_script._terminate_process_group(proc)
            assert proc.wait(timeout=5) is not None
        finally:
            if proc.poll() is None:
                proc.kill()

    def test_innocent_bystander_group_survives_a_stale_stamp(self):
        """The real incident: the PID is recycled and a live, unrelated group is spared."""
        from cron import scheduler_script

        bystander = subprocess.Popen(
            ["sleep", "60"], start_new_session=True,
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            stale = _FakeProc(pid=bystander.pid, starttime=1)  # stamp from the dead process
            scheduler_script._terminate_process_group(stale)
            assert bystander.poll() is None, "an innocent group was signalled"
        finally:
            bystander.kill()
            bystander.wait(timeout=5)


class TestKillProcessTreeIdentity:
    def test_refuses_recycled_target(self, monkeypatch, killpg_calls, kill_calls):
        from agent import deadline, killguard

        monkeypatch.setattr(os, "getpgid", lambda pid: pid)
        monkeypatch.setattr(deadline, "_process_tree_snapshot",
                            lambda pid, hard_kill=False: contextlib.nullcontext([]))
        stamps = [111, 222]  # pinned at entry, changed by signal time
        monkeypatch.setattr(killguard, "proc_starttime",
                            lambda pid: stamps.pop(0) if stamps else None)

        assert deadline.kill_process_tree(4242) is False
        assert killpg_calls == [] and kill_calls == []

    def test_signals_when_identity_holds(self, monkeypatch, killpg_calls):
        from agent import deadline, killguard

        monkeypatch.setattr(os, "getpgid", lambda pid: pid)
        monkeypatch.setattr(deadline, "_process_tree_snapshot",
                            lambda pid, hard_kill=False: contextlib.nullcontext([]))
        monkeypatch.setattr(killguard, "proc_starttime", lambda pid: 111)

        assert deadline.kill_process_tree(4242, sig=signal.SIGTERM) is True
        assert killpg_calls == [(4242, signal.SIGTERM)]
