"""Isolated CLI and transport contract tests; never invoke live services."""

from __future__ import annotations

import hashlib
import importlib
import io
import json
import os
import runpy
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from scripts.hermes_update_watch import model

NOW = datetime(2026, 10, 28, 14, 0, tzinfo=timezone.utc)
TARGET = "123456789012345678"
PROFILE = "default"
REPORT_ID = "f53f1f16-061d-4e48-9f7d-3d9e5e13dd29"


def _module(name: str) -> ModuleType:
    try:
        return importlib.import_module(f"scripts.hermes_update_watch.{name}")
    except ModuleNotFoundError:
        pytest.fail(f"T04 {name} behavior is not implemented", pytrace=False)


def _release() -> model.ReleaseMetadata:
    return model.ReleaseMetadata(
        release_id=42,
        tag="v1.2.3",
        published_at=datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc),
    )


class StaticReader:
    def __init__(self, releases: tuple[model.ReleaseMetadata, ...] | None = None) -> None:
        self.releases = (_release(),) if releases is None else releases
        self.calls: list[str] = []

    def list_releases(self) -> tuple[model.ReleaseMetadata, ...]:
        self.calls.append("list")
        return self.releases

    def resolve_tag(self, tag: str) -> tuple[str, str]:
        self.calls.append(tag)
        return "a" * 40, "b" * 40


class FailingReader:
    def list_releases(self) -> tuple[model.ReleaseMetadata, ...]:
        raise _module("releases").ReleaseError("timeout", "partial")

    def resolve_tag(self, tag: str) -> tuple[str, str]:
        raise AssertionError("partial listing must not resolve tags")


def _evidence() -> dict[str, Any]:
    categories = model.ENVIRONMENT_CATEGORIES
    dev = {
        "source_checkout": {
            "status": "observed",
            "reason": "read_only_git_observation",
            "sha": "c" * 40,
            "dirty": False,
            "dirty_count": 0,
        }
    }
    for category in categories[1:]:
        reason = "running_artifact_not_proven" if category == "runtime_image" else "not_collected"
        dev[category] = {"status": "unknown", "reason": reason}
    prod = {
        category: {"status": "unknown", "reason": "not_authorized_or_unavailable"}
        for category in categories
    }
    return {"dev": dev, "prod": prod}


class FakeTransport:
    def __init__(self, fail: Exception | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self.fail = fail

    def post(self, intent: Any, message: str, target: str, profile: str) -> Any:
        state = _module("state")
        self.calls.append({"intent": intent, "message": message, "target": target, "profile": profile})
        if self.fail is not None:
            raise self.fail
        return state.PostReceipt(
            destination_id=target,
            attempt_id=intent.attempt_id,
            message_id="223456789012345678",
            timestamp="2026-10-28T14:01:00Z",
            attachment_filename=intent.attachment_filename,
            attachment_size=intent.attachment_size,
            report_sha256=intent.report_sha256,
            message_sha256=intent.message_sha256,
        )


class Dependencies:
    def __init__(
        self,
        *,
        reader: Any | None = None,
        evidence: Any | None = None,
        transport: Any | None = None,
        now: datetime = NOW,
        store_factory: Any | None = None,
    ) -> None:
        state = _module("state")
        self.reader = StaticReader() if reader is None else reader
        self.evidence = _evidence if evidence is None else evidence
        self.transport = FakeTransport() if transport is None else transport
        self.now = lambda: now
        self.factory_calls = {"reader": 0, "evidence": 0, "transport": 0, "store": 0}

        def reader_factory() -> Any:
            self.factory_calls["reader"] += 1
            return self.reader

        def evidence_collector() -> Any:
            self.factory_calls["evidence"] += 1
            return self.evidence()

        def transport_factory() -> Any:
            self.factory_calls["transport"] += 1
            return self.transport

        def make_store(root: Path) -> Any:
            self.factory_calls["store"] += 1
            factory = state.StateStore if store_factory is None else store_factory
            return factory(root)

        self.reader_factory = reader_factory
        self.evidence_collector = evidence_collector
        self.transport_factory = transport_factory
        self.store_factory = make_store


def _run(argv: list[str], deps: Dependencies, *, stdout: io.StringIO | None = None) -> tuple[int, dict[str, Any] | None]:
    cli = _module("cli")
    output = io.StringIO() if stdout is None else stdout
    code = cli.run_cli(argv, dependencies=deps, stdout=output, stderr=io.StringIO())
    try:
        payload = json.loads(output.getvalue())
    except json.JSONDecodeError:
        payload = None
    return code, payload


def _deliver_args(root: Path, report_id: str, *, confirm: str | None = None, now: datetime = NOW) -> list[str]:
    args = [
        "deliver", report_id, "--state-root", str(root), "--target", TARGET,
        "--profile", PROFILE,
    ]
    if confirm is not None:
        args.extend(("--confirm-send", confirm))
    return args


def test_help_and_unknown_protected_verbs_are_offline_and_bounded() -> None:
    deps = Dependencies()
    stdout = io.StringIO()
    code = _module("cli").run_cli(["--help"], dependencies=deps, stdout=stdout, stderr=io.StringIO())
    assert code == 0
    assert "inspect" in stdout.getvalue() and "watch" in stdout.getvalue() and "deliver" in stdout.getvalue()
    assert deps.factory_calls == {"reader": 0, "evidence": 0, "transport": 0, "store": 0}

    for verb in ("activate", "recover", "not-a-command"):
        code, result = _run([verb], deps)
        assert code == 2
        assert result == {"status": "blocked", "reason_code": "unsupported_operation"}
    assert deps.factory_calls == {"reader": 0, "evidence": 0, "transport": 0, "store": 0}


def test_executable_help_delegates_to_offline_cli(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    script = Path(__file__).resolve().parents[2] / "scripts" / "hermes-update-watch.py"
    monkeypatch.setattr(sys, "argv", [str(script), "--help"])
    with pytest.raises(SystemExit) as exit_request:
        runpy.run_path(str(script), run_name="__main__")
    output = capsys.readouterr().out
    assert exit_request.value.code == 0
    assert "inspect" in output and "watch" in output and "deliver" in output


def test_executable_protected_verb_is_captured_offline_in_child_process() -> None:
    process = _module("process")
    script = Path(__file__).resolve().parents[2] / "scripts" / "hermes-update-watch.py"
    result = process.run_bounded_process(
        (sys.executable, str(script), "activate"),
        env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": "/nonexistent", "LANG": "C.UTF-8"},
        timeout_seconds=5,
        stdout_limit=2048,
        stderr_limit=1024,
    )
    assert result.started is True
    assert result.returncode == 2
    assert json.loads(result.stdout) == {"status": "blocked", "reason_code": "unsupported_operation"}
    assert result.stderr == b""


def test_package_exposes_cli_and_transport_entrypoints() -> None:
    from scripts.hermes_update_watch import DiscordTransport, main, run_cli

    assert callable(main)
    assert callable(run_cli)
    assert DiscordTransport is _module("transport").DiscordTransport


def test_inspect_is_read_only_and_watch_persists_pending_without_transport(tmp_path: Path) -> None:
    state = _module("state")
    deps = Dependencies()
    root = tmp_path / "watch"
    args = ["watch", "--state-root", str(root), "--target", TARGET]
    code, result = _run(args, deps)
    assert code == 0
    assert result["status"] == "available"
    assert len(result["report_ids"]) == 1
    snapshot = (root / "state.json").read_bytes()
    report_id = result["report_ids"][0]
    stored = state.StateStore(root).read_state()
    assert stored["outbox"][0]["state"] == "pending"
    assert deps.transport.calls == []

    inspect_deps = Dependencies()
    inspect_args = ["inspect", "--state-root", str(root)]
    inspect_code, inspect_result = _run(inspect_args, inspect_deps)
    assert inspect_code == 0
    assert inspect_result["status"] == "no_change"
    assert (root / "state.json").read_bytes() == snapshot
    assert inspect_deps.transport.calls == []

    repeat_code, repeat = _run(args, deps)
    assert repeat_code == 0 and repeat["status"] == "no_change"
    assert report_id in {item["report_id"] for item in state.StateStore(root).read_state()["outbox"]}
    assert deps.transport.calls == []


def test_incomplete_watch_does_not_initialize_or_advance_state(tmp_path: Path) -> None:
    deps = Dependencies(reader=FailingReader())
    root = tmp_path / "watch"
    code, result = _run(["watch", "--state-root", str(root), "--target", TARGET], deps)
    assert code == 3
    assert result["reason_code"] == "timeout"
    assert not root.exists()
    assert deps.factory_calls["evidence"] == 0
    assert deps.transport.calls == []


def test_delivery_requires_exact_confirmation_then_confirmed_release_cannot_resend(tmp_path: Path) -> None:
    state = _module("state")
    deps = Dependencies()
    root = tmp_path / "watch"
    code, watched = _run(["watch", "--state-root", str(root), "--target", TARGET], deps)
    assert code == 0
    report_id = watched["report_ids"][0]

    no_confirmation, blocked = _run(_deliver_args(root, report_id), deps)
    assert no_confirmation == 2
    assert blocked["reason_code"] == "send_confirmation_required"
    assert deps.transport.calls == []
    assert state.StateStore(root).read_state()["outbox"][0]["state"] == "pending"

    confirmation = f"SEND {report_id} TO {TARGET} AS {PROFILE}"
    sent, result = _run(_deliver_args(root, report_id, confirm=confirmation), deps)
    assert sent == 0 and result["status"] == "confirmed"
    assert len(deps.transport.calls) == 1
    final_state = state.StateStore(root).read_state()
    assert final_state["outbox"][0]["state"] == "confirmed"

    repeated, blocked = _run(_deliver_args(root, report_id, confirm=confirmation), deps)
    assert repeated == 5
    assert blocked["reason_code"] == "invalid_delivery_transition"
    assert len(deps.transport.calls) == 1


def test_expired_report_never_invokes_transport(tmp_path: Path) -> None:
    deps = Dependencies()
    root = tmp_path / "watch"
    code, watched = _run(["watch", "--state-root", str(root), "--target", TARGET], deps)
    assert code == 0
    report_id = watched["report_ids"][0]
    expired_deps = Dependencies(transport=FakeTransport(), now=NOW + timedelta(days=2))
    confirmation = f"SEND {report_id} TO {TARGET} AS {PROFILE}"
    code, result = _run(_deliver_args(root, report_id, confirm=confirmation), expired_deps)
    assert code == 5
    assert result["reason_code"] == "report_expired"
    assert expired_deps.transport.calls == []


def test_watch_refreshes_only_expired_unattempted_pending_reports(tmp_path: Path) -> None:
    state = _module("state")
    root = tmp_path / "watch"
    initial = Dependencies()
    code, first = _run(["watch", "--state-root", str(root), "--target", TARGET], initial)
    assert code == 0 and len(first["report_ids"]) == 1
    old_report_id = first["report_ids"][0]

    refreshed = Dependencies(now=NOW + timedelta(days=2))
    code, second = _run(["watch", "--state-root", str(root), "--target", TARGET], refreshed)
    assert code == 0
    assert second["status"] == "available"
    assert len(second["report_ids"]) == 1
    assert second["report_ids"][0] != old_report_id
    assert refreshed.reader.calls == ["list", "v1.2.3"]
    record = state.StateStore(root).read_state()["outbox"][0]
    assert record["state"] == "pending"
    assert record["report_id"] == second["report_ids"][0]
    assert record["attempt_id"] is None
    assert record["expires_at"] > (NOW + timedelta(days=2)).isoformat().replace("+00:00", "Z")


def test_incomplete_refresh_revalidation_preserves_expired_pending_state(tmp_path: Path) -> None:
    state = _module("state")
    root = tmp_path / "watch"
    initial = Dependencies()
    code, _ = _run(["watch", "--state-root", str(root), "--target", TARGET], initial)
    assert code == 0
    before = state.StateStore(root).read_state()

    failing = Dependencies(reader=FailingReader(), now=NOW + timedelta(days=2))
    code, result = _run(["watch", "--state-root", str(root), "--target", TARGET], failing)
    assert code == 3 and result["reason_code"] == "timeout"
    assert state.StateStore(root).read_state() == before
    assert failing.factory_calls["evidence"] == 0


def test_deliver_rejects_superseded_report_reference_without_outbox_mutation(tmp_path: Path) -> None:
    state = _module("state")
    root = tmp_path / "watch"
    initial = Dependencies()
    code, first = _run(["watch", "--state-root", str(root), "--target", TARGET], initial)
    assert code == 0
    stale_report_id = first["report_ids"][0]

    refresh_deps = Dependencies(now=NOW + timedelta(days=2))
    code, refreshed = _run(["watch", "--state-root", str(root), "--target", TARGET], refresh_deps)
    assert code == 0 and len(refreshed["report_ids"]) == 1
    before = state.StateStore(root).read_state()

    stale_confirmation = f"SEND {stale_report_id} TO {TARGET} AS {PROFILE}"
    delivery = Dependencies(transport=FakeTransport())
    code, result = _run(_deliver_args(root, stale_report_id, confirm=stale_confirmation), delivery)
    assert code == 5
    assert result["reason_code"] == "report_reference_changed"
    assert state.StateStore(root).read_state() == before
    assert delivery.transport.calls == []


@pytest.mark.parametrize("reason_code", ["upstream_unavailable", "upstream_rate_limited"])
def test_watch_maps_actual_upstream_failure_codes_to_exit_three(reason_code: str, tmp_path: Path) -> None:
    class UnavailableReader:
        def list_releases(self) -> tuple[model.ReleaseMetadata, ...]:
            raise _module("releases").ReleaseError(reason_code)

        def resolve_tag(self, _tag: str) -> tuple[str, str]:
            raise AssertionError("unavailable source must not resolve tags")

    deps = Dependencies(reader=UnavailableReader())
    root = tmp_path / "watch"
    code, result = _run(["watch", "--state-root", str(root), "--target", TARGET], deps)
    assert code == 3
    assert result["reason_code"] == reason_code
    assert not root.exists()


def test_ambiguous_post_is_retained_and_never_blindly_retried(tmp_path: Path) -> None:
    cli = _module("cli")
    transport_module = _module("transport")
    process = _module("process")
    deps = Dependencies()
    root = tmp_path / "watch"
    code, watched = _run(["watch", "--state-root", str(root), "--target", TARGET], deps)
    assert code == 0
    report_id = watched["report_ids"][0]
    attempts: list[tuple[str, ...]] = []

    def uncertain_runner(argv: Any, **kwargs: Any) -> Any:
        attempts.append(tuple(argv))
        return process.BoundedProcessResult(1, b"", b"private output", started=True)

    real_transport = transport_module.DiscordTransport(runner=uncertain_runner)
    sending_deps = Dependencies(transport=real_transport)
    confirmation = f"SEND {report_id} TO {TARGET} AS {PROFILE}"
    code, result = _run(_deliver_args(root, report_id, confirm=confirmation), sending_deps)
    assert code == 6 and result["reason_code"] == "transport_nonzero"
    assert len(attempts) == 1
    record = _module("state").StateStore(root).read_state()["outbox"][0]
    assert record["state"] == "ambiguous"

    retry_code, retry = _run(_deliver_args(root, report_id, confirm=confirmation), sending_deps)
    assert retry_code == 5 and retry["reason_code"] == "invalid_delivery_transition"
    assert len(attempts) == 1


def test_proven_preinvoke_failure_is_recorded_without_external_retry(tmp_path: Path) -> None:
    transport_module = _module("transport")
    process = _module("process")
    deps = Dependencies()
    root = tmp_path / "watch"
    code, watched = _run(["watch", "--state-root", str(root), "--target", TARGET], deps)
    assert code == 0
    report_id = watched["report_ids"][0]
    calls: list[tuple[str, ...]] = []

    def unavailable_runner(argv: Any, **_kwargs: Any) -> Any:
        calls.append(tuple(argv))
        return process.BoundedProcessResult(None, b"", b"", "process_unavailable", started=False)

    sending_deps = Dependencies(transport=transport_module.DiscordTransport(runner=unavailable_runner))
    confirmation = f"SEND {report_id} TO {TARGET} AS {PROFILE}"
    code, result = _run(_deliver_args(root, report_id, confirm=confirmation), sending_deps)
    assert code == 6
    assert result["status"] == "failed_no_send"
    assert result["reason_code"] == "transport_unavailable_before_invocation"
    assert _module("state").StateStore(root).read_state()["outbox"][0]["state"] == "failed_no_send"

    retry_code, retry = _run(_deliver_args(root, report_id, confirm=confirmation), sending_deps)
    assert retry_code == 5 and retry["reason_code"] == "invalid_delivery_transition"
    assert len(calls) == 1


def test_transport_factory_failure_is_recorded_as_proven_no_send(tmp_path: Path) -> None:
    deps = Dependencies()
    root = tmp_path / "watch"
    code, watched = _run(["watch", "--state-root", str(root), "--target", TARGET], deps)
    assert code == 0
    report_id = watched["report_ids"][0]
    confirmation = f"SEND {report_id} TO {TARGET} AS {PROFILE}"

    def unavailable_factory() -> Any:
        raise RuntimeError("private setup detail must not escape")

    deps.transport_factory = unavailable_factory
    code, result = _run(_deliver_args(root, report_id, confirm=confirmation), deps)
    assert code == 6
    assert result == {
        "status": "failed_no_send",
        "reason_code": "transport_unavailable_before_invocation",
        "report_id": report_id,
    }
    state = _module("state").StateStore(root).read_state()
    assert state["outbox"][0]["state"] == "failed_no_send"


def _send_intent() -> Any:
    state = _module("state")
    reports = _module("report")
    release = model.ReleaseIdentity(
        release_id=42,
        tag="v1.2.3",
        published_at=datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc),
        tag_sha="a" * 40,
        commit_sha="b" * 40,
    )
    report = reports.build_report(release, _evidence(), now=NOW, report_id=REPORT_ID)
    payload = reports.serialize_report(report)
    message = reports.render_alert(report)
    return state.SendIntent(
        attempt_id="d2d2df72-4370-420d-9845-fac14ff31849",
        destination_id=TARGET,
        report_id=REPORT_ID,
        attachment_filename=f"{REPORT_ID}.json",
        attachment_bytes=payload,
        report_sha256=hashlib.sha256(payload).hexdigest(),
        message_sha256=hashlib.sha256(message.encode("utf-8")).hexdigest(),
        expires_at=report["expires_at"],
        attachment_size=len(payload),
    )


def _alert(intent: Any) -> str:
    return _module("report").render_alert(_module("report").load_report(intent.attachment_bytes))


def test_transport_uses_sealed_snapshot_fd_and_maps_physical_receipt_name() -> None:
    transport_module = _module("transport")
    process = _module("process")
    intent = _send_intent()
    observed: dict[str, Any] = {}

    def verifying_runner(argv: Any, **kwargs: Any) -> Any:
        observed["argv"] = tuple(argv)
        observed["env"] = dict(kwargs["env"])
        fd_path = argv[5]
        physical_name = fd_path.rsplit("/", 1)[1]
        fd = int(physical_name)
        observed["fd"] = fd
        observed["pass_fds"] = kwargs["pass_fds"]
        assert kwargs["pass_fds"] == (fd,)
        assert fd in kwargs["pass_fds"]
        assert not any("TOKEN" in name or "SECRET" in name for name in kwargs["env"])

        import fcntl
        seals = fcntl.fcntl(fd, fcntl.F_GET_SEALS)
        required = fcntl.F_SEAL_WRITE | fcntl.F_SEAL_GROW | fcntl.F_SEAL_SHRINK | fcntl.F_SEAL_SEAL
        assert seals & required == required

        child = process.run_bounded_process(
            (sys.executable, "-c", "import sys;sys.stdout.buffer.write(open(sys.argv[1],'rb').read())", fd_path),
            env=kwargs["env"],
            timeout_seconds=kwargs["timeout_seconds"],
            stdout_limit=kwargs["stdout_limit"],
            stderr_limit=kwargs["stderr_limit"],
            pass_fds=kwargs["pass_fds"],
        )
        assert child.reason_code is None and child.started is True
        assert child.stdout == intent.attachment_bytes
        receipt = {
            "status": "ok",
            "channel_id": TARGET,
            "message_id": "223456789012345678",
            "message_ids": ["223456789012345678"],
            "timestamp": "2026-10-28T14:01:00Z",
            "attachments": [{"filename": physical_name, "size": len(intent.attachment_bytes), "url": "https://private.invalid/file"}],
        }
        return process.BoundedProcessResult(0, json.dumps(receipt).encode(), b"", started=True)

    transport = transport_module.DiscordTransport(runner=verifying_runner)
    receipt = transport.post(intent, _alert(intent), TARGET, PROFILE)
    assert observed["argv"][0] == "/usr/local/bin/ncl-discord"
    assert observed["argv"][1] == "post"
    assert observed["argv"][2] == TARGET
    assert observed["argv"][3] == _alert(intent)
    assert observed["argv"][4] == "--attach"
    assert observed["argv"][6:] == ("--as", PROFILE)
    assert observed["argv"][5].startswith("/proc/self/fd/")
    assert receipt.attachment_filename == intent.attachment_filename
    assert receipt.attachment_size == len(intent.attachment_bytes)
    with pytest.raises(OSError):
        os.fstat(observed["fd"])


@pytest.mark.parametrize(
    "change",
    [
        pytest.param({"channel_id": "223456789012345678"}, id="wrong-channel"),
        pytest.param({"message_ids": ["223456789012345678", "323456789012345678"]}, id="multiple-messages"),
        pytest.param({"attachments": [{"filename": "wrong", "size": 29}]}, id="wrong-attachment"),
        pytest.param({"attachments": [{"filename": "99", "size": True}]}, id="boolean-size"),
        pytest.param({"timestamp": "not-a-time"}, id="bad-time"),
    ],
)
def test_transport_rejects_untrusted_or_mismatched_receipt_as_ambiguous(change: dict[str, Any]) -> None:
    transport_module = _module("transport")
    process = _module("process")
    intent = _send_intent()
    descriptor: dict[str, int] = {}

    def invalid_receipt_runner(argv: Any, **kwargs: Any) -> Any:
        fd_name = argv[5].rsplit("/", 1)[1]
        descriptor["fd"] = int(fd_name)
        data = {
            "status": "ok",
            "channel_id": TARGET,
            "message_id": "223456789012345678",
            "message_ids": ["223456789012345678"],
            "timestamp": "2026-10-28T14:01:00Z",
            "attachments": [{"filename": fd_name, "size": len(intent.attachment_bytes)}],
        }
        data.update(change)
        return process.BoundedProcessResult(0, json.dumps(data).encode(), b"", started=True)

    with pytest.raises(transport_module.TransportError) as error:
        transport_module.DiscordTransport(runner=invalid_receipt_runner).post(intent, _alert(intent), TARGET, PROFILE)
    assert error.value.reason_code == "transport_output_invalid"
    assert error.value.invoked is True
    with pytest.raises(OSError):
        os.fstat(descriptor["fd"])


def test_transport_classifies_spawn_failure_as_preinvoke_and_timeout_as_ambiguous() -> None:
    transport_module = _module("transport")
    process = _module("process")
    intent = _send_intent()

    def spawn_failure(_argv: Any, **_kwargs: Any) -> Any:
        return process.BoundedProcessResult(None, b"", b"", "process_unavailable", started=False)

    with pytest.raises(transport_module.TransportError) as unavailable:
        transport_module.DiscordTransport(runner=spawn_failure).post(intent, _alert(intent), TARGET, PROFILE)
    assert unavailable.value.invoked is False

    def timeout(_argv: Any, **_kwargs: Any) -> Any:
        return process.BoundedProcessResult(None, b"", b"", "timeout", started=True)

    with pytest.raises(transport_module.TransportError) as uncertain:
        transport_module.DiscordTransport(runner=timeout).post(intent, _alert(intent), TARGET, PROFILE)
    assert uncertain.value.invoked is True
    assert uncertain.value.reason_code == "transport_timeout"


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param(b'{"number":' + b"9" * 5000 + b"}", id="huge-integer"),
        pytest.param(b"[" * 2000 + b"0" + b"]" * 2000, id="deeply-nested"),
    ],
)
def test_transport_sanitizes_huge_integer_and_deeply_nested_receipt(payload: bytes) -> None:
    transport_module = _module("transport")
    process = _module("process")
    intent = _send_intent()

    def malformed_runner(_argv: Any, **_kwargs: Any) -> Any:
        return process.BoundedProcessResult(0, payload, b"", started=True)

    with pytest.raises(transport_module.TransportError) as error:
        transport_module.DiscordTransport(runner=malformed_runner).post(intent, _alert(intent), TARGET, PROFILE)
    assert error.value.reason_code == "transport_output_invalid"
    assert error.value.invoked is True


def test_transport_fails_before_runner_when_proc_fd_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    transport_module = _module("transport")
    intent = _send_intent()
    original_stat = os.stat
    calls: list[str] = []

    def missing_proc_fd(path: Any, *args: Any, **kwargs: Any) -> Any:
        if isinstance(path, str) and path.startswith("/proc/self/fd/"):
            calls.append(path)
            raise FileNotFoundError
        return original_stat(path, *args, **kwargs)

    monkeypatch.setattr(transport_module.os, "stat", missing_proc_fd)
    invoked: list[bool] = []

    def runner(_argv: Any, **_kwargs: Any) -> Any:
        invoked.append(True)
        raise AssertionError("must not spawn without proc-fd access")

    with pytest.raises(transport_module.TransportError) as error:
        transport_module.DiscordTransport(runner=runner).post(intent, _alert(intent), TARGET, PROFILE)
    assert error.value.reason_code == "snapshot_unavailable"
    assert error.value.invoked is False
    assert calls
    assert invoked == []
