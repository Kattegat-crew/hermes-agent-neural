"""Tests for bounded local evidence and immutable report construction."""

from __future__ import annotations

import hashlib
import importlib
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from types import ModuleType
from typing import Any

import pytest

from scripts.hermes_update_watch import model


def _module(name: str) -> ModuleType:
    try:
        return importlib.import_module(f"scripts.hermes_update_watch.{name}")
    except ModuleNotFoundError:
        pytest.fail(f"T02 {name} behavior is not implemented", pytrace=False)


def _release(**changes: Any) -> model.ReleaseIdentity:
    values: dict[str, Any] = {
        "release_id": 42,
        "tag": "v1.2.3",
        "published_at": datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc),
        "tag_sha": "a" * 40,
        "commit_sha": "b" * 40,
    }
    values.update(changes)
    return model.ReleaseIdentity(**values)


class FakeRunner:
    def __init__(self, results: list[Any]) -> None:
        self.results = list(results)
        self.calls: list[dict[str, Any]] = []

    def __call__(self, argv: Any, env: Any, **kwargs: Any) -> Any:
        self.calls.append({"argv": tuple(argv), "env": dict(env), **kwargs})
        return self.results.pop(0)


def _process_result(returncode: int, stdout: bytes = b"", stderr: bytes = b"", reason_code: str | None = None) -> Any:
    process = _module("process")
    return process.BoundedProcessResult(returncode, stdout, stderr, reason_code)


def test_process_runner_caps_stream_while_child_is_writing() -> None:
    process = _module("process")
    result = process.run_bounded_process(
        (sys.executable, "-c", "import sys; sys.stdout.buffer.write(b'x' * 1000000)"),
        env={"PATH": "/usr/bin:/bin"},
        timeout_seconds=3,
        stdout_limit=128,
        stderr_limit=64,
    )
    assert result.reason_code == "stdout_limit_exceeded"
    assert result.stdout == b""
    assert len(result.stderr) <= 64

    stderr = process.run_bounded_process(
        (sys.executable, "-c", "import sys; sys.stderr.buffer.write(b'x' * 1000000)"),
        env={"PATH": "/usr/bin:/bin"},
        timeout_seconds=3,
        stdout_limit=64,
        stderr_limit=128,
    )
    assert stderr.reason_code == "stderr_limit_exceeded"
    assert stderr.stderr == b""
    invalid_deadline = process.run_bounded_process(
        (sys.executable, "-c", "pass"), env={"PATH": "/usr/bin:/bin"},
        timeout_seconds=float("inf"), stdout_limit=64, stderr_limit=64,
    )
    assert invalid_deadline.reason_code == "invalid_process_request"


def test_process_runner_times_out_and_sends_stdin_eof() -> None:
    process = _module("process")
    start = time.monotonic()
    timed_out = process.run_bounded_process(
        (sys.executable, "-c", "import time; time.sleep(10)"),
        env={"PATH": "/usr/bin:/bin"},
        timeout_seconds=0.05,
        stdout_limit=64,
        stderr_limit=64,
    )
    assert timed_out.reason_code == "timeout"
    assert time.monotonic() - start < 2

    eof = process.run_bounded_process(
        (sys.executable, "-c", "import sys; assert sys.stdin.read() == ''; print('eof')"),
        env={"PATH": "/usr/bin:/bin"},
        timeout_seconds=2,
        stdout_limit=64,
        stderr_limit=64,
    )
    assert eof.reason_code is None
    assert eof.stdout == b"eof\n"


def test_evidence_uses_only_fixed_git_calls_and_emits_no_paths() -> None:
    report = _module("report")
    sha = b"a" * 40 + b"\n"
    porcelain = b" M safe-but-private-name.py\n?? untracked-private-name\nR  old-name -> new-name\n"
    runner = FakeRunner([_process_result(0, sha), _process_result(0, porcelain)])

    evidence = report.collect_environment_evidence(runner=runner)

    assert len(runner.calls) == 2
    expected_prefix = (
        "/usr/bin/git", "-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false",
        "-c", "core.untrackedCache=false", "-c", "core.pager=cat", "-c", "core.quotePath=true",
        "-C", "/opt/hermes-agent",
    )
    assert runner.calls[0]["argv"] == (*expected_prefix, "rev-parse", "--verify", "HEAD^{commit}")
    assert runner.calls[1]["argv"] == (*expected_prefix, "status", "--porcelain=v1", "--untracked-files=all")
    for call in runner.calls:
        assert call["env"] == {
            "PATH": "/usr/bin:/bin", "HOME": "/nonexistent", "LC_ALL": "C",
            "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_OPTIONAL_LOCKS": "0", "GIT_TERMINAL_PROMPT": "0",
        }
        assert call["timeout_seconds"] == 5
        assert call["stdout_limit"] == 65536
        assert call["stderr_limit"] == 4096
    dev = evidence["dev"]
    assert dev["source_checkout"] == {
        "status": "observed", "reason": "read_only_git_observation", "sha": "a" * 40,
        "dirty": True, "dirty_count": 3,
    }
    assert evidence["prod"]["source_checkout"] == {
        "status": "unknown", "reason": "not_authorized_or_unavailable",
    }
    encoded = json.dumps(evidence)
    assert "safe-but-private-name.py" not in encoded
    assert "untracked-private-name" not in encoded
    assert "old-name" not in encoded


def test_failed_or_malformed_git_evidence_stays_unknown_with_reason_code_only() -> None:
    report = _module("report")
    runner = FakeRunner([_process_result(1, stderr=b"/private/path token=secret"), _process_result(0, b"not-a-sha\n")])
    evidence = report.collect_environment_evidence(runner=runner)
    assert evidence["dev"]["source_checkout"] == {
        "status": "unknown", "reason": "git_command_failed",
    }
    assert evidence["prod"]["source_checkout"]["reason"] == "not_authorized_or_unavailable"
    assert "private/path" not in json.dumps(evidence)
    assert "secret" not in json.dumps(evidence)

    malformed = report.collect_environment_evidence(
        runner=FakeRunner([_process_result(0, b"f" * 39 + b"\n"), _process_result(0, b"?? x\n")])
    )
    assert malformed["dev"]["source_checkout"] == {
        "status": "unknown", "reason": "git_output_invalid",
    }
    malformed_porcelain = report.collect_environment_evidence(
        runner=FakeRunner([_process_result(0, b"f" * 40 + b"\n"), _process_result(0, b"?M hidden\n")])
    )
    assert malformed_porcelain["dev"]["source_checkout"] == {
        "status": "unknown", "reason": "git_output_invalid",
    }


def test_report_roundtrip_digest_schema_and_expiry_are_strict() -> None:
    report_module = _module("report")
    evidence = report_module.collect_environment_evidence(
        runner=FakeRunner([_process_result(0, b"c" * 40 + b"\n"), _process_result(0, b"")])
    )
    now = datetime(2026, 10, 28, 14, 30, tzinfo=timezone.utc)
    report = report_module.build_report(
        _release(), evidence, report_id="123e4567-e89b-42d3-a456-426614174000", now=now
    )
    payload = report_module.serialize_report(report)
    assert len(payload) <= 65536
    decoded = json.loads(payload)
    assert decoded["expires_at"] == "2026-10-29T14:30:00Z"
    assert report_module.validate_report(decoded) == decoded
    assert report_module.load_report(payload) == decoded
    unsigned = {key: value for key, value in decoded.items() if key != "integrity_sha256"}
    canonical = json.dumps(unsigned, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    assert decoded["integrity_sha256"] == hashlib.sha256(canonical).hexdigest()
    assert decoded["assessment"] == "available_for_human_inspection"
    assert decoded["environments"]["dev"]["source_checkout"]["sha"] == "c" * 40
    assert decoded["environments"]["prod"]["source_checkout"]["status"] == "unknown"

    damaged = dict(decoded)
    damaged["source"] = dict(decoded["source"], commit_sha="d" * 40)
    with pytest.raises(report_module.ReportValidationError):
        report_module.validate_report(damaged)
    extra = dict(decoded, unexpected="must reject")
    with pytest.raises(report_module.ReportValidationError):
        report_module.validate_report(extra)
    expired = dict(decoded, expires_at="2026-10-28T14:29:59Z")
    with pytest.raises(report_module.ReportValidationError):
        report_module.validate_report(expired)


def test_report_rejects_untrusted_environment_fields_and_invalid_release_values() -> None:
    report_module = _module("report")
    evidence = report_module.collect_environment_evidence(
        runner=FakeRunner([_process_result(0, b"c" * 40 + b"\n"), _process_result(0, b"")])
    )
    tampered = json.loads(json.dumps(evidence))
    tampered["dev"]["source_checkout"]["filename"] = "/private/config.yaml"
    with pytest.raises(report_module.ReportValidationError):
        report_module.build_report(_release(), tampered)

    for invalid in (
        _release(tag="v01.2.3"), _release(release_id=True), _release(tag_sha="a" * 39),
        _release(published_at=datetime(2026, 10, 28, 12, 0)),
        _release(published_at=datetime(2026, 10, 28, 12, 0, tzinfo=timezone(timedelta(hours=1)))),
        _release(published_at=datetime(2026, 10, 28, 15, 0, tzinfo=timezone.utc)),
    ):
        with pytest.raises(report_module.ReportValidationError):
            report_module.build_report(
                invalid, evidence, now=datetime(2026, 10, 28, 14, 30, tzinfo=timezone.utc)
            )

    with pytest.raises(report_module.ReportValidationError):
        report_module.build_report(_release(), evidence, report_id="../../outside.json")


def test_fixed_prompt_and_alert_are_read_only_complete_and_bounded() -> None:
    report_module = _module("report")
    evidence = report_module.collect_environment_evidence(
        runner=FakeRunner([_process_result(0, b"c" * 40 + b"\n"), _process_result(0, b"")])
    )
    report = report_module.build_report(_release(), evidence, now=datetime(2026, 10, 28, 14, 30, tzinfo=timezone.utc))
    prompt = report_module.render_prompt(report)
    alert = report_module.render_alert(report)
    assert report["prompt"] == prompt
    assert prompt in alert
    for required in (
        "DEV or PROD", "read-only", "untrusted", "expiring", "verify", "unknowns", "risks",
        "Stop", "Do not fetch", "secrets", "transcripts", "backups", "build", "install",
        "update", "restart", "recover", "commit", "send", "no authorization",
        "fresh explicit authorization",
    ):
        assert required.casefold() in prompt.casefold()
    for forbidden_claim in ("safe", "compatible", "clean", "rollback guaranteed", "backup succeeded"):
        assert forbidden_claim not in alert.casefold()
    assert report_module.utf16_code_units(alert) <= 1900
    assert "v1.2.3" in alert
    assert "b" * 40 in alert
    assert report["report_id"] in alert
    assert report["expires_at"] in alert


def test_maximum_stable_tag_keeps_alert_within_budget_and_no_truncation() -> None:
    report_module = _module("report")
    tag = "v" + "9" * 40 + "." + "8" * 40 + "." + "7" * 40
    evidence = report_module.collect_environment_evidence(
        runner=FakeRunner([_process_result(0, b"c" * 40 + b"\n"), _process_result(0, b"")])
    )
    report = report_module.build_report(
        _release(tag=tag), evidence, now=datetime(2026, 10, 28, 14, 30, tzinfo=timezone.utc)
    )
    alert = report_module.render_alert(report)
    assert tag in alert
    assert report_module.utf16_code_units(alert) <= 1900
    assert len(report_module.serialize_report(report)) <= 65536


def test_report_loader_rejects_duplicate_keys_huge_integers_and_deep_nesting() -> None:
    report_module = _module("report")
    invalid_payloads = (
        b'{"schema":"x","schema":"y"}',
        b'{"release_id":' + b"9" * 5000 + b"}",
        b"[" * 1500 + b"0" + b"]" * 1500,
    )
    for payload in invalid_payloads:
        with pytest.raises(report_module.ReportValidationError) as error:
            report_module.load_report(payload)
        assert error.value.reason_code in {"invalid_report", "report_too_large"}


def test_report_loader_rejects_malformed_json_without_echoing_payload() -> None:
    report_module = _module("report")
    payload = b'{"schema":"hermes.update-watch-report/v1","secret":"dont-echo"}'
    with pytest.raises(report_module.ReportValidationError) as error:
        report_module.load_report(payload)
    assert "dont-echo" not in str(error.value)


def test_evidence_runner_exceptions_are_reduced_to_stable_unknown_codes() -> None:
    report = _module("report")

    def broken_runner(*_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError("/private/config secret-value")

    evidence = report.collect_environment_evidence(runner=broken_runner)
    assert evidence["dev"]["source_checkout"] == {
        "status": "unknown", "reason": "git_process_unavailable",
    }
    assert "private/config" not in json.dumps(evidence)
    assert "secret-value" not in json.dumps(evidence)


def test_valid_digest_cannot_make_future_publication_valid() -> None:
    report_module = _module("report")
    evidence = report_module.collect_environment_evidence(
        runner=FakeRunner([_process_result(0, b"c" * 40 + b"\n"), _process_result(0, b"")])
    )
    report = report_module.build_report(
        _release(), evidence, now=datetime(2026, 10, 28, 14, 0, tzinfo=timezone.utc)
    )
    forged = json.loads(json.dumps(report))
    forged["source"]["published_at"] = "2026-10-29T00:00:00Z"
    unsigned = {key: value for key, value in forged.items() if key != "integrity_sha256"}
    canonical = json.dumps(unsigned, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    forged["integrity_sha256"] = hashlib.sha256(canonical).hexdigest()

    with pytest.raises(report_module.ReportValidationError) as error:
        report_module.load_report(json.dumps(forged))
    assert error.value.reason_code == "invalid_timestamp"


def test_expiry_overflow_at_max_utc_time_is_sanitized() -> None:
    report_module = _module("report")
    evidence = report_module.collect_environment_evidence(
        runner=FakeRunner([_process_result(0, b"c" * 40 + b"\n"), _process_result(0, b"")])
    )
    with pytest.raises(report_module.ReportValidationError) as error:
        report_module.build_report(
            _release(), evidence, now=datetime(9999, 12, 31, tzinfo=timezone.utc)
        )
    assert error.value.reason_code == "invalid_timestamp"
