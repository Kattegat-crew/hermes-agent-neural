"""Offline orchestration and pending-recovery contract tests."""

from __future__ import annotations

import importlib
import io
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from scripts.hermes_update_watch import model

NOW = datetime(2026, 10, 28, 14, 0, tzinfo=timezone.utc)
TARGET = "1493432785245962250"
PROFILE = "roshi"


def _module(name: str) -> ModuleType:
    try:
        return importlib.import_module(f"scripts.hermes_update_watch.{name}")
    except ModuleNotFoundError:
        pytest.fail(f"weekly {name} behavior is not implemented", pytrace=False)


def _releases(count: int) -> tuple[model.ReleaseMetadata, ...]:
    return tuple(
        model.ReleaseMetadata(
            release_id=100 + index,
            tag=f"v1.0.{index + 1}",
            published_at=NOW - timedelta(days=count - index),
        )
        for index in range(count)
    )


def _evidence() -> dict[str, Any]:
    dev = {
        "source_checkout": {
            "status": "observed",
            "reason": "read_only_git_observation",
            "sha": "c" * 40,
            "dirty": False,
            "dirty_count": 0,
        }
    }
    for category in model.ENVIRONMENT_CATEGORIES[1:]:
        reason = "running_artifact_not_proven" if category == "runtime_image" else "not_collected"
        dev[category] = {"status": "unknown", "reason": reason}
    prod = {
        category: {"status": "unknown", "reason": "not_authorized_or_unavailable"}
        for category in model.ENVIRONMENT_CATEGORIES
    }
    return {"dev": dev, "prod": prod}


class FakeReader:
    def __init__(self, releases: tuple[model.ReleaseMetadata, ...]) -> None:
        self.releases = releases
        self.calls: list[str] = []

    def list_releases(self) -> tuple[model.ReleaseMetadata, ...]:
        self.calls.append("list")
        return self.releases

    def resolve_tag(self, tag: str) -> tuple[str, str]:
        self.calls.append(tag)
        index = next(i for i, release in enumerate(self.releases) if release.tag == tag)
        return f"{index + 1:040x}", f"{index + 101:040x}"


class FakeTransport:
    def __init__(self, failure: Exception | None = None) -> None:
        self.failure = failure
        self.calls: list[dict[str, Any]] = []

    def post(self, intent: Any, message: str, target: str, profile: str) -> Any:
        self.calls.append({"intent": intent, "message": message, "target": target, "profile": profile})
        if self.failure is not None:
            raise self.failure
        return _module("state").PostReceipt(
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
        releases: tuple[model.ReleaseMetadata, ...],
        *,
        transport: FakeTransport | None = None,
        now: datetime = NOW,
        reader_error: str | None = None,
    ) -> None:
        state = _module("state")
        releases_module = _module("releases")
        self.reader = FakeReader(releases)
        self.transport = FakeTransport() if transport is None else transport
        self.now = now
        self.reader_error = reader_error
        self.factories = {"reader": 0, "evidence": 0, "store": 0, "transport": 0}

        def reader_factory() -> FakeReader:
            self.factories["reader"] += 1
            if self.reader_error is not None:
                error_code = self.reader_error

                class UnavailableReader:
                    def list_releases(self) -> tuple[model.ReleaseMetadata, ...]:
                        raise releases_module.ReleaseError(error_code)

                    def resolve_tag(self, _tag: str) -> tuple[str, str]:
                        raise AssertionError("failed listing must not resolve tags")

                return UnavailableReader()  # type: ignore[return-value]
            return self.reader

        def evidence_collector() -> dict[str, Any]:
            self.factories["evidence"] += 1
            return _evidence()

        def store_factory(root: Path) -> Any:
            self.factories["store"] += 1
            return state.StateStore(root)

        def transport_factory() -> FakeTransport:
            self.factories["transport"] += 1
            return self.transport

        self.cli_dependencies = _module("cli").Dependencies(
            reader_factory=reader_factory,
            evidence_collector=evidence_collector,
            store_factory=store_factory,
            transport_factory=transport_factory,
            now=lambda: self.now,
        )


def _run_watch(root: Path, dependencies: Dependencies) -> tuple[int, dict[str, Any]]:
    cli = _module("cli")
    output = io.StringIO()
    code = cli.run_cli(
        ["watch", "--state-root", str(root), "--target", TARGET],
        dependencies=dependencies.cli_dependencies,
        stdout=output,
        stderr=io.StringIO(),
    )
    return code, json.loads(output.getvalue())


def _run_weekly(root: Path, dependencies: Dependencies) -> tuple[int, dict[str, Any]]:
    output = io.StringIO()
    code = _module("weekly").run_weekly(
        ["--state-root", str(root), "--target", TARGET, "--profile", PROFILE],
        dependencies=dependencies.cli_dependencies,
        stdout=output,
        stderr=io.StringIO(),
    )
    return code, json.loads(output.getvalue())


def test_weekly_recovers_pending_after_watch_without_new_release(tmp_path: Path) -> None:
    state = _module("state")
    root = tmp_path / "watch"
    releases = _releases(1)
    deps = Dependencies(releases)
    watch_code, watched = _run_watch(root, deps)
    assert watch_code == 0 and watched["status"] == "available"
    original_report_ids = [record["report_id"] for record in state.StateStore(root).read_state()["outbox"]]
    assert len(original_report_ids) == 1

    code, result = _run_weekly(root, deps)
    assert code == 0 and result["status"] == "completed"
    assert result["delivered_count"] == 1
    assert deps.transport.calls[0]["intent"].report_id == original_report_ids[0]
    assert deps.transport.calls[0]["target"] == TARGET
    assert deps.transport.calls[0]["profile"] == PROFILE
    final = state.StateStore(root).read_state()
    assert final["outbox"][0]["state"] == "confirmed"
    assert final["outbox"][0]["report_id"] == original_report_ids[0]

    later = Dependencies(releases)
    later_code, later_result = _run_weekly(root, later)
    assert later_code == 0 and later_result["delivered_count"] == 0
    assert later.transport.calls == []


def test_weekly_persists_overflow_in_publication_order_not_numeric_order(
    tmp_path: Path,
) -> None:
    state = _module("state")
    root = tmp_path / "watch"
    baseline = model.ReleaseMetadata(
        release_id=1,
        tag="v1.0.0",
        published_at=NOW - timedelta(days=30),
    )
    initial = Dependencies((baseline,))
    code, result = _run_watch(root, initial)
    assert code == 0 and result["status"] == "available"

    release_ids = (90, 80, 70, 60, 50, 100, 2)
    releases = tuple(
        model.ReleaseMetadata(
            release_id=release_id,
            tag=f"v2.0.{index + 1}",
            published_at=NOW - timedelta(days=len(release_ids) - index - 1),
        )
        for index, release_id in enumerate(release_ids)
    )
    updated = Dependencies(releases)
    code, result = _run_watch(root, updated)

    assert code == 0 and result["status"] == "available"
    snapshot = state.StateStore(root).read_state()
    assert snapshot["pending_release_ids"] == [100, 2]
    assert len(snapshot["outbox"]) == 6
    assert len(updated.reader.calls) == 7


def test_weekly_drains_seven_expired_pending_reports_across_bounded_runs(
    tmp_path: Path,
) -> None:
    state = _module("state")
    root = tmp_path / "watch"
    baseline = model.ReleaseMetadata(
        release_id=1,
        tag="v1.0.0",
        published_at=NOW - timedelta(days=30),
    )
    code, _result = _run_watch(root, Dependencies((baseline,)))
    assert code == 0
    code, result = _run_weekly(root, Dependencies((baseline,)))
    assert code == 0 and result["delivered_count"] == 1

    first_batch = tuple(
        model.ReleaseMetadata(
            release_id=release_id,
            tag=f"v2.0.{index + 1}",
            published_at=NOW - timedelta(days=6 - index),
        )
        for index, release_id in enumerate((90, 80, 70, 60, 50))
    )
    code, result = _run_watch(root, Dependencies(first_batch))
    assert code == 0 and result["candidate_count"] == 5

    all_releases = first_batch + (
        model.ReleaseMetadata(100, "v2.0.6", NOW - timedelta(days=1)),
        model.ReleaseMetadata(2, "v2.0.7", NOW),
    )
    code, result = _run_watch(root, Dependencies(all_releases))
    assert code == 0 and result["candidate_count"] == 2
    snapshot = state.StateStore(root).read_state()
    assert len(snapshot["outbox"]) == 8
    assert sum(item["state"] == "pending" for item in snapshot["outbox"]) == 7

    day_two = Dependencies(all_releases, now=NOW + timedelta(days=2))
    code, result = _run_weekly(root, day_two)
    assert code == 0 and result["delivered_count"] == 5
    assert len(day_two.reader.calls) - day_two.reader.calls.count("list") <= model.MAX_RESOLVED_IDENTITIES
    assert len(day_two.transport.calls) == 5
    snapshot = state.StateStore(root).read_state()
    assert sum(item["state"] == "confirmed" for item in snapshot["outbox"]) == 6
    assert sum(item["state"] == "pending" for item in snapshot["outbox"]) == 2
    assert state.StateStore(root).pending_report_ids(TARGET, now=NOW + timedelta(days=2)) == ()

    day_nine = Dependencies(all_releases, now=NOW + timedelta(days=9))
    code, result = _run_weekly(root, day_nine)
    assert code == 0 and result["delivered_count"] == 2
    assert len(day_nine.reader.calls) - day_nine.reader.calls.count("list") <= model.MAX_RESOLVED_IDENTITIES
    assert len(day_nine.transport.calls) == 2
    final = state.StateStore(root).read_state()
    assert all(item["state"] == "confirmed" for item in final["outbox"])


def test_weekly_refreshes_expired_pending_report_before_recovery_send(tmp_path: Path) -> None:
    state = _module("state")
    root = tmp_path / "watch"
    releases = _releases(1)
    initial = Dependencies(releases)
    code, first = _run_watch(root, initial)
    assert code == 0
    old_report_id = first["report_ids"][0]

    recovery = Dependencies(releases, now=NOW + timedelta(days=2))
    code, result = _run_weekly(root, recovery)
    assert code == 0 and result["delivered_count"] == 1
    new_report_id = recovery.transport.calls[0]["intent"].report_id
    assert new_report_id != old_report_id
    final = state.StateStore(root).read_state()["outbox"][0]
    assert final["state"] == "confirmed" and final["report_id"] == new_report_id
    assert state.StateStore(root).read_report(new_report_id)["report_id"] == new_report_id


def test_pending_report_enumeration_is_locked_filtered_and_bounded(tmp_path: Path) -> None:
    state = _module("state")
    root = tmp_path / "watch"
    deps = Dependencies(_releases(1))
    code, watched = _run_watch(root, deps)
    assert code == 0 and len(watched["report_ids"]) == 1
    store = state.StateStore(root)
    assert store.pending_report_ids(TARGET, now=NOW) == tuple(watched["report_ids"])
    assert store.pending_report_ids(TARGET, now=NOW + timedelta(days=2)) == ()
    assert store.pending_report_ids(TARGET, now=NOW, limit=1) == tuple(watched["report_ids"])
    for invalid_now in (NOW.replace(tzinfo=None), NOW.astimezone(timezone(timedelta(hours=1)))):
        with pytest.raises(state.StateError) as invalid_time:
            store.pending_report_ids(TARGET, now=invalid_now)
        assert invalid_time.value.reason_code == "invalid_timestamp"
    with store.transaction():
        with pytest.raises(state.StateError) as locked:
            store.pending_report_ids(TARGET)
    assert locked.value.reason_code == "lock_busy"
    for invalid in (0, True, model.MAX_CANDIDATES + 1):
        with pytest.raises(state.StateError) as error:
            store.pending_report_ids(TARGET, limit=invalid)
        assert error.value.reason_code == "invalid_pending_limit"


def test_weekly_delivery_is_capped_at_five_pending_ids(tmp_path: Path) -> None:
    state = _module("state")
    root = tmp_path / "watch"
    first = Dependencies(_releases(1))
    first_code, _ = _run_watch(root, first)
    assert first_code == 0
    expanded = Dependencies(_releases(6))
    expanded_code, expanded_result = _run_watch(root, expanded)
    assert expanded_code == 0
    assert len(expanded_result["report_ids"]) == 5
    assert len(state.StateStore(root).pending_report_ids(TARGET)) == 5

    # Additional never-attempted records can remain from earlier bounded cycles.
    sixth = Dependencies(_releases(7))
    sixth_code, sixth_result = _run_watch(root, sixth)
    assert sixth_code == 0 and len(sixth_result["report_ids"]) == 1
    assert len(state.StateStore(root).read_state()["outbox"]) == 7

    drain = Dependencies(_releases(7))
    code, result = _run_weekly(root, drain)
    assert code == 0 and result["delivered_count"] == model.MAX_CANDIDATES
    assert len(drain.transport.calls) == model.MAX_CANDIDATES
    assert len(state.StateStore(root).pending_report_ids(TARGET)) == 2


@pytest.mark.parametrize(
    ("failure", "expected_state"),
    [
        pytest.param("ambiguous", "ambiguous", id="ambiguous-not-retried"),
        pytest.param("failed_no_send", "failed_no_send", id="failed-no-send-not-retried"),
    ],
)
def test_weekly_never_retries_terminal_send_outcomes(
    tmp_path: Path,
    failure: str,
    expected_state: str,
) -> None:
    state = _module("state")
    transport_module = _module("transport")
    root = tmp_path / "watch"
    releases = _releases(1)
    initial = Dependencies(releases)
    code, _ = _run_watch(root, initial)
    assert code == 0
    exception = transport_module.TransportError(
        "transport_timeout" if failure == "ambiguous" else "transport_unavailable_before_invocation",
        invoked=failure == "ambiguous",
    )
    failed = Dependencies(releases, transport=FakeTransport(exception))
    code, result = _run_weekly(root, failed)
    assert code == 6 and result["status"] in {"ambiguous", "failed_no_send"}
    stored = state.StateStore(root).read_state()
    assert stored["outbox"][0]["state"] == expected_state

    retry = Dependencies(releases)
    retry_code, retry_result = _run_weekly(root, retry)
    assert retry_code == 0 and retry_result["delivered_count"] == 0
    assert retry.transport.calls == []
    assert state.StateStore(root).read_state()["outbox"][0]["state"] == expected_state


def test_weekly_does_not_retry_interrupted_sending_record(tmp_path: Path) -> None:
    import hashlib

    state = _module("state")
    report = _module("report")
    root = tmp_path / "watch"
    releases = _releases(1)
    initial = Dependencies(releases)
    code, watched = _run_watch(root, initial)
    assert code == 0
    report_id = watched["report_ids"][0]
    report_value = state.StateStore(root).read_report(report_id)
    source = report_value["source"]
    identity = model.ReleaseIdentity(
        release_id=source["release_id"],
        tag=source["tag"],
        published_at=datetime.fromisoformat(source["published_at"].replace("Z", "+00:00")),
        tag_sha=source["tag_sha"],
        commit_sha=source["commit_sha"],
        repository=source["repository"],
    )
    message = report.render_alert(report_value)
    with state.StateStore(root).transaction() as transaction:
        transaction.begin_send(
            identity,
            TARGET,
            hashlib.sha256(message.encode("utf-8")).hexdigest(),
            now=NOW,
        )

    after_crash = Dependencies(releases)
    code, result = _run_weekly(root, after_crash)
    assert code == 5
    assert result["reason_code"] == "state_changed_during_scan"
    assert after_crash.transport.calls == []
    record = state.StateStore(root).read_state()["outbox"][0]
    assert record["state"] == "ambiguous"
    assert record["reason_code"] == "send_outcome_unknown_after_restart"


def test_weekly_stops_batch_on_first_delivery_failure(tmp_path: Path) -> None:
    state = _module("state")
    transport_module = _module("transport")
    root = tmp_path / "watch"
    first = Dependencies(_releases(1))
    assert _run_watch(root, first)[0] == 0
    expanded = Dependencies(_releases(6))
    assert _run_watch(root, expanded)[0] == 0
    assert len(state.StateStore(root).pending_report_ids(TARGET)) == model.MAX_CANDIDATES

    transport = FakeTransport(transport_module.TransportError("transport_timeout", invoked=True))
    failure = Dependencies(_releases(6), transport=transport)
    code, result = _run_weekly(root, failure)
    assert code == 6 and result["status"] == "ambiguous"
    assert len(transport.calls) == 1
    stored = state.StateStore(root).read_state()
    assert sum(item["state"] == "pending" for item in stored["outbox"]) == model.MAX_CANDIDATES


def test_weekly_stops_on_incomplete_watch_before_enumerating_or_sending(tmp_path: Path) -> None:
    state = _module("state")
    root = tmp_path / "watch"
    initial = Dependencies(_releases(1))
    code, _ = _run_watch(root, initial)
    assert code == 0
    before = state.StateStore(root).read_state()

    incomplete = Dependencies(_releases(1), reader_error="upstream_unavailable")
    code, result = _run_weekly(root, incomplete)
    assert code == 3
    assert result["status"] == "blocked"
    assert result["reason_code"] == "upstream_unavailable"
    assert incomplete.factories["transport"] == 0
    assert state.StateStore(root).read_state() == before


def test_weekly_help_and_invalid_target_are_offline(tmp_path: Path) -> None:
    root = tmp_path / "not-created"
    deps = Dependencies(_releases(1))
    weekly = _module("weekly")
    help_output = io.StringIO()
    help_code = weekly.run_weekly(["--help"], dependencies=deps.cli_dependencies, stdout=help_output)
    assert help_code == 0 and "--target" in help_output.getvalue()
    for invalid_args in (
        ["--state-root", str(root), "--target", "123456789012345678", "--profile", PROFILE],
        ["--state-root", str(root), "--target", TARGET, "--profile", "default"],
    ):
        output = io.StringIO()
        code = weekly.run_weekly(invalid_args, dependencies=deps.cli_dependencies, stdout=output)
        assert code == 2
        assert json.loads(output.getvalue())["reason_code"] == "target_profile_not_authorized"
    assert deps.factories == {"reader": 0, "evidence": 0, "store": 0, "transport": 0}
    assert not root.exists()


def test_weekly_entrypoint_help_runs_offline_in_bounded_child_process() -> None:
    process = _module("process")
    script = Path(__file__).resolve().parents[2] / "scripts" / "hermes-update-watch-weekly.py"
    result = process.run_bounded_process(
        (sys.executable, str(script), "--help"),
        env={"PATH": "/usr/bin:/bin", "HOME": "/nonexistent", "LANG": "C.UTF-8"},
        timeout_seconds=5,
        stdout_limit=2048,
        stderr_limit=1024,
    )
    assert result.started is True
    assert result.returncode == 0
    assert b"--state-root" in result.stdout and b"--profile" in result.stdout
    assert result.stderr == b""
