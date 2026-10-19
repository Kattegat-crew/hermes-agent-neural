"""A dispatch that dies before the ownership ack must not leave a recoverable attempt.

Field evidence (2026-10-19, DEV): the 10:00 dispatch of four jobs reported
``cron external worker exited before ownership acknowledgement (exit -15)`` and the
jobs were recorded as failed — yet all four delivered their normal output moments
later. Two executions for one fire means the failed attempt stayed recoverable and
something re-ran it. This pins the contract: once the gateway declares the dispatch
failed, the attempt is terminal, so the dead-owner recovery cannot fire it again.
"""

import signal
import sys

import pytest


def test_dispatch_failure_terminalizes_the_attempt(tmp_path, monkeypatch):
    from cron import executions
    from cron import scheduler
    from cron.jobs import claim_job_for_fire, create_job, get_job, use_cron_store
    from tools.process_registry import GatewayChildDispatch

    home = tmp_path / "profile"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setattr(executions, "EXECUTIONS_FILE", home / "cron" / "executions.db")
    monkeypatch.setattr(scheduler, "load_config_readonly", dict)

    delivered = []
    monkeypatch.setattr(
        scheduler, "_deliver_result", lambda *a, **k: delivered.append(True)
    )

    # A worker that dies the way the field workers died: SIGTERM, before any ack.
    worker = tmp_path / "dying_worker.py"
    worker.write_text(
        "import os, signal, sys\n"
        "sys.stderr.write('worker-probe-killed-before-ack\\n')\n"
        "sys.stderr.flush()\n"
        "os.kill(os.getpid(), signal.SIGTERM)\n",
        encoding="utf-8",
    )

    def dispatch(command, **kwargs):
        return GatewayChildDispatch("degraded", [sys.executable, str(worker)])

    monkeypatch.setattr(
        "tools.process_registry.restart_safe_gateway_child_argv", dispatch
    )

    with use_cron_store(home):
        job = create_job(prompt="Reply OK", schedule="every 1h", deliver="local")
        claimed = claim_job_for_fire(job["id"], manual=True, return_job=True)
        assert claimed
        execution = executions.create_execution(job["id"], source="builtin")
        claimed["execution_id"] = execution["id"]

        assert scheduler.run_one_job(claimed)
        record = get_job(job["id"])
        row = executions.get_execution(claimed["execution_id"])

        assert "-15" in (record.get("last_error") or ""), record.get("last_error")
        assert row["status"] not in ("running", "pending", "handoff_pending"), row["status"]

        # The whole point: nothing left for the dead-owner recovery to adopt.
        assert executions.recover_interrupted_executions() == 0, (
            f"attempt left recoverable in status {row['status']!r}: "
            "recovery would run the same fire a second time"
        )


@pytest.mark.platforms("linux")
def test_ack_published_before_death_is_still_a_handoff(tmp_path, monkeypatch):
    """The mirror case: if the ack exists, the -15 exit is not a dispatch failure."""
    from cron import executions
    from cron import scheduler
    from cron.jobs import claim_job_for_fire, create_job, get_job, use_cron_store
    from tools.process_registry import GatewayChildDispatch

    home = tmp_path / "profile"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setattr(executions, "EXECUTIONS_FILE", home / "cron" / "executions.db")
    monkeypatch.setattr(scheduler, "load_config_readonly", dict)

    worker = tmp_path / "acking_worker.py"
    worker.write_text(
        "import json, os, signal, sys\n"
        "from pathlib import Path\n"
        "args = sys.argv\n"
        "ack = Path(args[args.index('--ack-file') + 1])\n"
        "payload = Path(args[args.index('--external-worker-file') + 1])\n"
        "eid = json.loads(payload.read_text())['job']['execution_id']\n"
        "ack.write_text(json.dumps({'pid': os.getpid(), 'execution_id': eid}))\n"
        "os.kill(os.getpid(), signal.SIGTERM)\n",
        encoding="utf-8",
    )

    def dispatch(command, **kwargs):
        flags = command[command.index("--external-worker-file") :]
        return GatewayChildDispatch("degraded", [sys.executable, str(worker), *flags])

    monkeypatch.setattr(
        "tools.process_registry.restart_safe_gateway_child_argv", dispatch
    )

    with use_cron_store(home):
        job = create_job(prompt="Reply OK", schedule="every 1h", deliver="local")
        claimed = claim_job_for_fire(job["id"], manual=True, return_job=True)
        assert claimed
        execution = executions.create_execution(job["id"], source="builtin")
        claimed["execution_id"] = execution["id"]

        scheduler.run_one_job(claimed)
        record = get_job(job["id"])
        assert "before ownership acknowledgement" not in (record.get("last_error") or ""), (
            "a published ack means the worker owned the attempt; a -15 exit is not a "
            f"dispatch failure (got: {record.get('last_error')!r})"
        )


def test_dispatch_failure_consumes_the_scheduled_instant(tmp_path, monkeypatch):
    """The failed fire must not leave the job due, or the ticker re-runs it seconds later.

    Field evidence (2026-10-19, vigia): 10:00:28 dispatch died with exit -15, and the same
    job ran again in-process at 10:00:47 — one instant, two attempts.
    """
    from cron import executions
    from cron import scheduler
    from cron.jobs import claim_job_for_fire, create_job, get_job, use_cron_store
    from tools.process_registry import GatewayChildDispatch

    home = tmp_path / "profile"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setattr(executions, "EXECUTIONS_FILE", home / "cron" / "executions.db")
    monkeypatch.setattr(scheduler, "load_config_readonly", dict)

    worker = tmp_path / "dying_worker2.py"
    worker.write_text(
        "import os, signal\nos.kill(os.getpid(), signal.SIGTERM)\n", encoding="utf-8"
    )

    def dispatch(command, **kwargs):
        return GatewayChildDispatch("degraded", [sys.executable, str(worker)])

    monkeypatch.setattr(
        "tools.process_registry.restart_safe_gateway_child_argv", dispatch
    )

    with use_cron_store(home):
        job = create_job(prompt="Reply OK", schedule="every 1h", deliver="local")
        claimed = claim_job_for_fire(job["id"], manual=True, return_job=True)
        assert claimed
        execution = executions.create_execution(job["id"], source="builtin")
        claimed["execution_id"] = execution["id"]

        scheduler.run_one_job(claimed)
        record = get_job(job["id"])
        assert record.get("next_run_at"), (
            "a failed dispatch left next_run_at empty: the job is immediately due again "
            f"(last_error={record.get('last_error')!r})"
        )
