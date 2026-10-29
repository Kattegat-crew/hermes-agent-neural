"""Temporary-directory tests for the atomic update-watch state store."""

from __future__ import annotations

import hashlib
import importlib
import json
import multiprocessing
import os
import stat
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from scripts.hermes_update_watch import model
from scripts.hermes_update_watch.report import build_report


def _state_module() -> ModuleType:
    try:
        return importlib.import_module("scripts.hermes_update_watch.state")
    except ModuleNotFoundError:
        pytest.fail("T03 persistent state behavior is not implemented", pytrace=False)


def _identity(
    release_id: int = 10,
    tag: str = "v1.2.3",
    commit: str = "b" * 40,
    tag_sha: str = "a" * 40,
) -> model.ReleaseIdentity:
    return model.ReleaseIdentity(
        release_id=release_id,
        tag=tag,
        published_at=datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc),
        tag_sha=tag_sha,
        commit_sha=commit,
    )


def _discovery(
    identities: tuple[model.ReleaseIdentity, ...] | None = None,
    *,
    candidates: tuple[model.ReleaseIdentity, ...] | None = None,
    seen: tuple[int, ...] = (),
    pending: tuple[int, ...] = (),
    status: str = "available",
) -> model.DiscoveryResult:
    identities = identities or (_identity(),)
    candidates = identities if candidates is None else candidates
    identity_rows = tuple((item.release_id, item.tag, item.commit_sha) for item in identities)
    tag_rows = tuple(sorted({(item.tag, item.commit_sha) for item in identities}))
    latest = identities[-1] if status in ("available", "no_change") else None
    discovery_state = model.DiscoveryState(
        has_completed_scan=status in ("available", "no_change"),
        identities_by_release_id=identity_rows,
        tag_commit_shas=tag_rows,
        seen_not_notified=seen,
        pending_release_ids=pending,
    )
    return model.DiscoveryResult(
        status=status, reason_code=None if status in ("available", "no_change") else "partial",
        candidates=candidates, latest_identity=latest, seen_not_notified=seen,
        pending_release_ids=pending, republished_release_ids=(), state=discovery_state,
    )


def _report(identity: model.ReleaseIdentity, *, report_id: str | None = None, now: datetime | None = None) -> dict[str, Any]:
    evidence = {
        "dev": {
            "source_checkout": {"status": "observed", "reason": "read_only_git_observation", "sha": "c" * 40, "dirty": False, "dirty_count": 0},
            "runtime_image": {"status": "unknown", "reason": "running_artifact_not_proven"},
            "effective_config": {"status": "unknown", "reason": "not_collected"},
            "customizations_mounts_profiles_data_sessions_plugins_skills_integrations": {"status": "unknown", "reason": "not_collected"},
            "backup_restore": {"status": "unknown", "reason": "not_collected"},
        },
        "prod": {
            category: {"status": "unknown", "reason": "not_authorized_or_unavailable"}
            for category in model.ENVIRONMENT_CATEGORIES
        },
    }
    return build_report(identity, evidence, now=now or datetime(2026, 10, 28, 14, 0, tzinfo=timezone.utc), report_id=report_id)


def _store(root: Path) -> Any:
    state = _state_module()
    return state.StateStore(root)


def _commit_discovery(store: Any, result: model.DiscoveryResult, reports: list[dict[str, Any]], destination: str = "123456789012345678") -> None:
    with store.transaction() as tx:
        tx.commit_discovery(result, reports, destination_id=destination)


def _hold_lock(root: str, pipe: Any, release: Any) -> None:
    store = _store(Path(root))
    with store.transaction():
        pipe.send("held")
        release.wait(5)


def _initialize_with_umask(root: str, pipe: Any) -> None:
    os.umask(0o777)
    try:
        _store(Path(root)).initialize()
        pipe.send("ok")
    except Exception as error:
        pipe.send(getattr(error, "reason_code", "unexpected_error"))
    finally:
        pipe.close()


def test_readonly_constructor_and_load_do_not_create_root_or_state(tmp_path: Path) -> None:
    missing = tmp_path / "missing-watch"
    store = _store(missing)
    with pytest.raises(_state_module().StateError) as error:
        store.read_state()
    assert error.value.reason_code == "store_not_initialized"
    assert not missing.exists()


def test_initialize_creates_private_store_and_loads_empty_schema(tmp_path: Path) -> None:
    state = _state_module()
    root = tmp_path / "watch"
    store = state.StateStore(root)
    initial = store.initialize()
    assert initial["schema"] == "hermes.update-watch-state/v1"
    assert initial["last_complete_scan"] is None
    assert initial["seen_not_notified"] == []
    assert initial["pending_release_ids"] == []
    assert initial["outbox"] == []
    assert stat.S_IMODE(root.stat().st_mode) == 0o700
    assert stat.S_IMODE((root / "state.json").stat().st_mode) == 0o600
    assert stat.S_IMODE((root / "state.lock").stat().st_mode) == 0o600
    assert stat.S_IMODE((root / "reports").stat().st_mode) == 0o700


def test_initialize_sets_modes_for_files_it_created_even_under_restrictive_umask(tmp_path: Path) -> None:
    root = tmp_path / "watch"
    receive, send = multiprocessing.Pipe(duplex=False)
    process = multiprocessing.get_context("fork").Process(
        target=_initialize_with_umask, args=(str(root), send)
    )
    process.start()
    send.close()
    try:
        assert receive.poll(5)
        result = receive.recv()
    finally:
        process.join(timeout=5)
        if process.is_alive():
            process.terminate()
            process.join(timeout=5)
    assert process.exitcode == 0
    assert result == "ok"
    assert stat.S_IMODE(root.stat().st_mode) == 0o700
    assert stat.S_IMODE((root / "state.lock").stat().st_mode) == 0o600


def test_root_mode_and_owner_are_rejected_without_repair(tmp_path: Path) -> None:
    state = _state_module()
    root = tmp_path / "watch"
    store = state.StateStore(root)
    store.initialize()
    root.chmod(0o750)
    with pytest.raises(state.StateError) as error:
        store.read_state()
    assert error.value.reason_code == "store_mode_invalid"
    assert stat.S_IMODE(root.stat().st_mode) == 0o750
    root.chmod(0o700)

    if os.geteuid() != 0:
        pytest.skip("wrong-owner fixture requires temporary-directory chown privilege")
    original_uid = root.stat().st_uid
    os.chown(root, original_uid + 1, -1)
    try:
        with pytest.raises(state.StateError) as error:
            store.read_state()
        assert error.value.reason_code == "store_owner_invalid"
    finally:
        os.chown(root, original_uid, -1)
    assert stat.S_IMODE(root.stat().st_mode) == 0o700


def test_symlink_ancestry_and_checkout_roots_are_rejected_without_writes(tmp_path: Path) -> None:
    state = _state_module()
    target = tmp_path / "target"
    target.mkdir(mode=0o700)
    link = tmp_path / "link"
    link.symlink_to(target, target_is_directory=True)
    with pytest.raises(state.StateError) as error:
        state.StateStore(link / "watch").initialize()
    assert error.value.reason_code == "unsafe_store_path"
    assert not (target / "watch").exists()

    for checkout in (Path("/opt/hermes-agent"), Path("/opt/hermes-agent-worktrees/hermes-update-watch")):
        with pytest.raises(state.StateError) as error:
            state.StateStore(checkout).initialize()
        assert error.value.reason_code == "unsafe_store_path"


def test_incomplete_discovery_cannot_advance_state_or_write_reports(tmp_path: Path) -> None:
    store = _store(tmp_path / "watch")
    store.initialize()
    incomplete = _discovery(status="partial", candidates=())
    with pytest.raises(_state_module().StateError) as error:
        _commit_discovery(store, incomplete, [])
    assert error.value.reason_code == "incomplete_discovery"
    snapshot = store.read_state()
    assert snapshot["last_complete_scan"] is None
    assert list((tmp_path / "watch" / "reports").iterdir()) == []


def test_discovery_rejects_duplicate_pending_release_ids(tmp_path: Path) -> None:
    store = _store(tmp_path / "watch")
    store.initialize()
    candidate = _identity()
    pending = _identity(20, "v1.2.4", "c" * 40, "d" * 40)
    result = _discovery(
        (candidate, pending),
        candidates=(candidate,),
        pending=(pending.release_id, pending.release_id),
    )

    with pytest.raises(_state_module().StateError) as error:
        _commit_discovery(store, result, [])

    assert error.value.reason_code == "state_corrupt"
    assert store.read_state()["last_complete_scan"] is None


def test_complete_discovery_persists_report_before_cursor_and_keeps_seen_distinct(tmp_path: Path) -> None:
    store = _store(tmp_path / "watch")
    store.initialize()
    identity = _identity()
    result = _discovery((identity,), seen=(1, 2), pending=(20,))
    report = _report(identity)
    _commit_discovery(store, result, [report])
    snapshot = store.read_state()
    assert snapshot["last_complete_scan"] is not None
    assert snapshot["seen_not_notified"] == [1, 2]
    assert snapshot["pending_release_ids"] == [20]
    assert len(snapshot["identities"]) == 1
    assert len(snapshot["outbox"]) == 1
    item = snapshot["outbox"][0]
    assert item["state"] == "pending"
    assert item["report_id"] == report["report_id"]
    stored_report = store.read_report(report["report_id"])
    assert stored_report == report
    assert stat.S_IMODE((tmp_path / "watch" / "reports" / f"{report['report_id']}.json").stat().st_mode) == 0o600
    assert item["report_sha256"] == hashlib.sha256(
        (tmp_path / "watch" / "reports" / f"{report['report_id']}.json").read_bytes()
    ).hexdigest()


def test_report_files_are_immutable_and_duplicate_identity_refreshes_only_pending(tmp_path: Path) -> None:
    store = _store(tmp_path / "watch")
    store.initialize()
    identity = _identity()
    first = _report(identity)
    result = _discovery((identity,))
    _commit_discovery(store, result, [first])

    refreshed = _report(identity, now=datetime(2026, 10, 28, 15, 0, tzinfo=timezone.utc))
    _commit_discovery(store, result, [refreshed])
    snapshot = store.read_state()
    assert len(snapshot["outbox"]) == 1
    assert snapshot["outbox"][0]["report_id"] == refreshed["report_id"]
    assert store.read_report(first["report_id"]) == first
    assert store.read_report(refreshed["report_id"]) == refreshed

    collision = _report(identity, report_id=refreshed["report_id"], now=datetime(2026, 10, 28, 16, 0, tzinfo=timezone.utc))
    with pytest.raises(_state_module().StateError) as error:
        _commit_discovery(store, result, [collision])
    assert error.value.reason_code == "report_id_collision"
    assert store.read_report(refreshed["report_id"]) == refreshed


def test_republished_identity_is_suppressed_and_tag_move_blocks(tmp_path: Path) -> None:
    state = _state_module()
    store = state.StateStore(tmp_path / "watch")
    store.initialize()
    first = _identity(10, "v1.2.3", "b" * 40)
    _commit_discovery(store, _discovery((first,)), [_report(first)])
    republished = _identity(11, "v1.2.3", "b" * 40, tag_sha="d" * 40)
    republished_result = _discovery((first, republished), candidates=(republished,))
    _commit_discovery(store, republished_result, [_report(republished)])
    snapshot = store.read_state()
    assert len(snapshot["outbox"]) == 1
    assert {item["release_id"] for item in snapshot["identities"]} == {10, 11}

    moved = _identity(12, "v1.2.3", "e" * 40)
    moved_result = _discovery((moved,), candidates=(moved,))
    before = store.read_state()
    with pytest.raises(state.StateError) as error:
        _commit_discovery(store, moved_result, [_report(moved)])
    assert error.value.reason_code == "tag_moved"
    assert store.read_state() == before


def test_release_id_rebinding_blocks_and_preserves_prior_state(tmp_path: Path) -> None:
    state = _state_module()
    store = state.StateStore(tmp_path / "watch")
    store.initialize()
    first = _identity(10)
    _commit_discovery(store, _discovery((first,)), [_report(first)])
    changed = _identity(10, "v9.9.9", "e" * 40)
    changed_result = _discovery((changed,), candidates=(changed,))
    before = store.read_state()
    with pytest.raises(state.StateError) as error:
        _commit_discovery(store, changed_result, [_report(changed)])
    assert error.value.reason_code in {"identity_changed", "tag_moved"}
    assert store.read_state() == before


def test_send_intent_persists_before_receipt_and_confirmation_is_typed(tmp_path: Path) -> None:
    state = _state_module()
    store = state.StateStore(tmp_path / "watch")
    store.initialize()
    identity = _identity()
    report = _report(identity)
    _commit_discovery(store, _discovery((identity,)), [report])
    message_hash = hashlib.sha256(b"fixed alert").hexdigest()
    with store.transaction() as tx:
        intent = tx.begin_send(identity, "123456789012345678", message_hash)
        current = tx.state["outbox"][0]
        assert current["state"] == "sending"
        assert current["attempt_id"] == intent.attempt_id
        assert current["message_sha256"] == message_hash
        assert current["report_sha256"] == intent.report_sha256
        receipt = state.PostReceipt(
            destination_id="123456789012345678", attempt_id=intent.attempt_id,
            message_id="223456789012345678", timestamp="2026-10-28T14:01:00Z",
            attachment_filename=f"{report['report_id']}.json",
            attachment_size=intent.attachment_size, report_sha256=intent.report_sha256,
            message_sha256=message_hash,
        )
        bad_receipt = state.PostReceipt(
            destination_id=receipt.destination_id, attempt_id=receipt.attempt_id,
            message_id=receipt.message_id, timestamp=receipt.timestamp,
            attachment_filename=receipt.attachment_filename, attachment_size=receipt.attachment_size,
            report_sha256=receipt.report_sha256, message_sha256="f" * 64,
        )
        with pytest.raises(state.StateError) as error:
            tx.confirm_send(identity, "123456789012345678", bad_receipt)
        assert error.value.reason_code == "invalid_receipt"
        assert tx.state["outbox"][0]["state"] == "sending"
        tx.confirm_send(identity, "123456789012345678", receipt)
    snapshot = store.read_state()
    assert snapshot["outbox"][0]["state"] == "confirmed"
    assert snapshot["outbox"][0]["receipt_id"] == "223456789012345678"


def _replace_root_with_conflicting_report(root: Path, report_id: str) -> Path:
    detached = root.with_name(f"{root.name}-detached")
    root.rename(detached)
    replacement_reports = root / "reports"
    replacement_reports.mkdir(parents=True, mode=0o700)
    replacement_path = replacement_reports / f"{report_id}.json"
    replacement_path.write_bytes(b"replacement content")
    replacement_path.chmod(0o600)
    return detached


def test_send_intent_uses_snapshot_anchored_before_root_namespace_replacement(tmp_path: Path) -> None:
    state = _state_module()
    root = tmp_path / "watch"
    store = _store(root)
    store.initialize()
    identity = _identity()
    result = _discovery((identity,))
    report = _report(identity)
    _commit_discovery(store, result, [report])
    expected_payload = state.report_module.serialize_report(report)
    expected_hash = hashlib.sha256(expected_payload).hexdigest()

    with store.transaction() as tx:
        detached = _replace_root_with_conflicting_report(root, report["report_id"])
        with pytest.raises(state.StateError) as error:
            tx.begin_send(identity, "123456789012345678", hashlib.sha256(b"alert").hexdigest())
        assert error.value.reason_code == "store_namespace_changed"
        assert tx.state["outbox"][0]["state"] == "pending"

    assert _store(detached).read_state()["outbox"][0]["state"] == "pending"
    assert hashlib.sha256(expected_payload).hexdigest() == expected_hash


def test_send_intent_snapshot_remains_stable_after_root_namespace_replacement(tmp_path: Path) -> None:
    state = _state_module()
    root = tmp_path / "watch"
    store = _store(root)
    store.initialize()
    identity = _identity()
    report = _report(identity)
    _commit_discovery(store, _discovery((identity,)), [report])
    expected_payload = state.report_module.serialize_report(report)

    with store.transaction() as tx:
        intent = tx.begin_send(
            identity,
            "123456789012345678",
            hashlib.sha256(b"alert").hexdigest(),
        )
        detached = _replace_root_with_conflicting_report(root, report["report_id"])
        assert hashlib.sha256(intent.attachment_bytes).hexdigest() == intent.report_sha256
        assert intent.attachment_bytes == expected_payload
        assert intent.attachment_filename == f"{report['report_id']}.json"
        receipt = state.PostReceipt(
            destination_id=intent.destination_id,
            attempt_id=intent.attempt_id,
            message_id="223456789012345678",
            timestamp="2026-10-28T14:01:00Z",
            attachment_filename=intent.attachment_filename,
            attachment_size=intent.attachment_size,
            report_sha256=intent.report_sha256,
            message_sha256=intent.message_sha256,
        )
        with pytest.raises(state.StateError) as error:
            tx.confirm_send(identity, intent.destination_id, receipt)
        assert error.value.reason_code == "store_namespace_changed"

    assert hashlib.sha256(intent.attachment_bytes).hexdigest() == intent.report_sha256
    assert _store(detached).read_state()["outbox"][0]["state"] == "sending"


def test_existing_report_directory_sync_is_required_before_state_advances_after_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = _state_module()
    root = tmp_path / "watch"
    store = _store(root)
    store.initialize()
    identity = _identity()
    result = _discovery((identity,))
    report = _report(identity)
    destination = "123456789012345678"
    before_retry = store.read_state()
    report_directory = (root / "reports").stat()
    store_directory = root.stat()
    real_fsync = state.os.fsync

    def fail_reports_directory(fd: int) -> None:
        info = os.fstat(fd)
        if (info.st_dev, info.st_ino) == (report_directory.st_dev, report_directory.st_ino):
            raise OSError("simulated report-directory fsync failure")
        real_fsync(fd)

    monkeypatch.setattr(state.os, "fsync", fail_reports_directory)
    retry_time = datetime(2026, 10, 28, 15, 0, tzinfo=timezone.utc)
    for _attempt in range(2):
        with pytest.raises(state.StateError) as error:
            with store.transaction() as tx:
                tx.commit_discovery(result, [report], destination_id=destination, now=retry_time)
        assert error.value.reason_code == "state_unavailable"
        assert store.read_state() == before_retry
    assert (root / "reports" / f"{report['report_id']}.json").is_file()

    events: list[str] = []

    def record_fsync_order(fd: int) -> None:
        info = os.fstat(fd)
        if (info.st_dev, info.st_ino) == (report_directory.st_dev, report_directory.st_ino):
            events.append("reports")
        elif (info.st_dev, info.st_ino) == (store_directory.st_dev, store_directory.st_ino):
            events.append("state_directory")
        real_fsync(fd)

    monkeypatch.setattr(state.os, "fsync", record_fsync_order)
    with store.transaction() as tx:
        tx.commit_discovery(result, [report], destination_id=destination, now=retry_time)
    assert events.index("reports") < events.index("state_directory")
    assert store.read_state()["last_complete_scan"] == "2026-10-28T15:00:00Z"


def test_failed_or_ambiguous_sends_never_auto_replay_and_stale_sending_becomes_ambiguous(tmp_path: Path) -> None:
    state = _state_module()
    store = state.StateStore(tmp_path / "watch")
    store.initialize()
    identity = _identity()
    report = _report(identity)
    _commit_discovery(store, _discovery((identity,)), [report])
    with store.transaction() as tx:
        intent = tx.begin_send(identity, "123456789012345678", hashlib.sha256(b"msg").hexdigest())
    recovered = store.read_state()
    assert recovered["outbox"][0]["state"] == "sending"
    with store.transaction() as tx:
        recovered = tx.state["outbox"][0]
        assert recovered["state"] == "ambiguous"
        assert recovered["reason_code"] == "send_outcome_unknown_after_restart"
        with pytest.raises(state.StateError) as error:
            tx.begin_send(identity, "123456789012345678", hashlib.sha256(b"msg").hexdigest())
        assert error.value.reason_code == "invalid_delivery_transition"


def test_expired_report_is_rejected_before_sending(tmp_path: Path) -> None:
    state = _state_module()
    store = state.StateStore(tmp_path / "watch")
    store.initialize()
    identity = _identity()
    report = _report(identity)
    _commit_discovery(store, _discovery((identity,)), [report])
    with store.transaction() as tx:
        with pytest.raises(state.StateError) as error:
            tx.begin_send(
                identity, "123456789012345678", hashlib.sha256(b"msg").hexdigest(),
                now=datetime(2026, 10, 30, tzinfo=timezone.utc),
            )
        assert error.value.reason_code == "report_expired"
        assert tx.state["outbox"][0]["state"] == "pending"


def test_lock_is_nonblocking_across_processes(tmp_path: Path) -> None:
    state = _state_module()
    root = tmp_path / "watch"
    store = state.StateStore(root)
    store.initialize()
    context = multiprocessing.get_context("fork")
    parent, child = context.Pipe(duplex=False)
    release = context.Event()
    process = context.Process(target=_hold_lock, args=(str(root), child, release))
    process.start()
    try:
        assert parent.poll(3) and parent.recv() == "held"
        with pytest.raises(state.StateError) as error:
            with store.transaction():
                pass
        assert error.value.reason_code == "lock_busy"
    finally:
        release.set()
        process.join(5)
        parent.close()
        child.close()
    assert process.exitcode == 0


def test_atomic_replace_failure_preserves_last_confirmed_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    state = _state_module()
    store = state.StateStore(tmp_path / "watch")
    store.initialize()
    first = _identity(10)
    first_report = _report(first)
    _commit_discovery(store, _discovery((first,)), [first_report])
    with store.transaction() as tx:
        intent = tx.begin_send(first, "123456789012345678", hashlib.sha256(b"first").hexdigest())
        tx.confirm_send(first, "123456789012345678", state.PostReceipt(
            destination_id="123456789012345678", attempt_id=intent.attempt_id,
            message_id="223456789012345678", timestamp="2026-10-28T14:01:00Z",
            attachment_filename=f"{first_report['report_id']}.json", attachment_size=intent.attachment_size,
            report_sha256=intent.report_sha256, message_sha256=hashlib.sha256(b"first").hexdigest(),
        ))
    before = store.read_state()
    second = _identity(11, "v1.2.4", "d" * 40, "e" * 40)
    result = _discovery((first, second), candidates=(second,))
    monkeypatch.setattr(state.os, "replace", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("disk")))
    with pytest.raises(state.StateError) as error:
        _commit_discovery(store, result, [_report(second)])
    assert error.value.reason_code == "state_unavailable"
    assert store.read_state() == before
    assert store.read_state()["outbox"][0]["state"] == "confirmed"


def test_fsync_failure_before_state_commit_preserves_confirmed_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    state = _state_module()
    store = state.StateStore(tmp_path / "watch")
    store.initialize()
    first = _identity()
    _commit_discovery(store, _discovery((first,)), [_report(first)])
    before = store.read_state()
    second = _identity(11, "v1.2.4", "d" * 40, "e" * 40)
    result = _discovery((first, second), candidates=(second,))
    monkeypatch.setattr(state.os, "fsync", lambda _fd: (_ for _ in ()).throw(OSError("disk")))
    with pytest.raises(state.StateError) as error:
        _commit_discovery(store, result, [_report(second)])
    assert error.value.reason_code == "state_unavailable"
    assert store.read_state() == before


def test_corrupt_or_unknown_state_fails_closed_without_reset(tmp_path: Path) -> None:
    state = _state_module()
    store = state.StateStore(tmp_path / "watch")
    store.initialize()
    path = tmp_path / "watch" / "state.json"
    original = path.read_bytes()
    malformed = original[:-1] + b",\"unknown\":true}"
    path.write_bytes(malformed)
    with pytest.raises(state.StateError) as error:
        store.read_state()
    assert error.value.reason_code == "state_corrupt"
    assert path.read_bytes() == malformed


def test_missing_symlinked_hardlinked_and_wrong_mode_report_files_fail_closed(tmp_path: Path) -> None:
    state = _state_module()
    store = state.StateStore(tmp_path / "watch")
    store.initialize()
    identity = _identity()
    report = _report(identity)
    _commit_discovery(store, _discovery((identity,)), [report])
    reports = tmp_path / "watch" / "reports"
    path = reports / f"{report['report_id']}.json"
    state_before = (tmp_path / "watch" / "state.json").read_bytes()

    path.chmod(0o644)
    with pytest.raises(state.StateError) as error:
        store.read_state()
    assert error.value.reason_code == "report_mode_invalid"
    assert stat.S_IMODE(path.stat().st_mode) == 0o644
    path.chmod(0o600)

    linked = reports / "unrelated-name"
    os.link(path, linked)
    try:
        with pytest.raises(state.StateError) as error:
            store.read_state()
        assert error.value.reason_code == "report_file_invalid"
    finally:
        linked.unlink()

    backup = reports / "local-backup.json"
    path.rename(backup)
    path.symlink_to(backup.name)
    with pytest.raises(state.StateError) as error:
        store.read_state()
    assert error.value.reason_code == "report_file_invalid"
    assert (tmp_path / "watch" / "state.json").read_bytes() == state_before

    path.unlink()
    with pytest.raises(state.StateError) as error:
        store.read_state()
    assert error.value.reason_code == "report_missing"


def test_send_lock_covers_intent_and_nonpending_report_is_not_refreshed(tmp_path: Path) -> None:
    state = _state_module()
    root = tmp_path / "watch"
    store = state.StateStore(root)
    store.initialize()
    second_store = state.StateStore(root)
    identity = _identity()
    first = _report(identity)
    _commit_discovery(store, _discovery((identity,)), [first])
    refreshed = _report(identity, now=datetime(2026, 10, 28, 15, 0, tzinfo=timezone.utc))
    with store.transaction() as tx:
        intent = tx.begin_send(identity, "123456789012345678", hashlib.sha256(b"alert").hexdigest())
        with pytest.raises(state.StateError) as error:
            with second_store.transaction():
                pass
        assert error.value.reason_code == "lock_busy"
        assert tx.commit_discovery(_discovery((identity,)), [refreshed], destination_id="123456789012345678") == ()
        assert tx.state["outbox"][0]["state"] == "sending"
        assert tx.state["outbox"][0]["report_id"] == first["report_id"]
        assert not (root / "reports" / f"{refreshed['report_id']}.json").exists()
    with store.transaction() as tx:
        assert tx.state["outbox"][0]["state"] == "ambiguous"
        assert tx.state["outbox"][0]["attempt_id"] == intent.attempt_id


def test_failed_no_send_is_terminal_and_never_confirmed_implicitly(tmp_path: Path) -> None:
    state = _state_module()
    store = state.StateStore(tmp_path / "watch")
    store.initialize()
    identity = _identity()
    report = _report(identity)
    _commit_discovery(store, _discovery((identity,)), [report])
    with store.transaction() as tx:
        tx.fail_before_send(identity, "123456789012345678", "alert_validation_failed")
    record = store.read_state()["outbox"][0]
    assert record["state"] == "failed_no_send"
    assert record["receipt_id"] is None
    assert record["reason_code"] == "alert_validation_failed"
    with store.transaction() as tx:
        with pytest.raises(state.StateError) as error:
            tx.begin_send(identity, "123456789012345678", hashlib.sha256(b"alert").hexdigest())
        assert error.value.reason_code == "invalid_delivery_transition"


def test_existing_empty_directory_is_not_silently_initialized(tmp_path: Path) -> None:
    state = _state_module()
    root = tmp_path / "watch"
    root.mkdir(mode=0o700)
    with pytest.raises(state.StateError) as error:
        state.StateStore(root).initialize()
    assert error.value.reason_code == "state_missing"
    assert list(root.iterdir()) == []


def test_state_file_and_reports_directory_modes_are_rejected_without_repair(tmp_path: Path) -> None:
    state = _state_module()
    root = tmp_path / "watch"
    store = state.StateStore(root)
    store.initialize()
    path = root / "state.json"
    path.chmod(0o644)
    with pytest.raises(state.StateError) as error:
        store.read_state()
    assert error.value.reason_code == "state_mode_invalid"
    assert stat.S_IMODE(path.stat().st_mode) == 0o644
    path.chmod(0o600)

    reports = root / "reports"
    reports.chmod(0o750)
    with pytest.raises(state.StateError) as error:
        store.read_state()
    assert error.value.reason_code == "store_mode_invalid"
    assert stat.S_IMODE(reports.stat().st_mode) == 0o750
    reports.chmod(0o700)

    if os.geteuid() != 0:
        pytest.skip("wrong-owner fixture requires temporary-file chown privilege")
    original_uid = path.stat().st_uid
    os.chown(path, original_uid + 1, -1)
    try:
        with pytest.raises(state.StateError) as error:
            store.read_state()
        assert error.value.reason_code == "state_owner_invalid"
    finally:
        os.chown(path, original_uid, -1)


def test_nested_unknown_state_fields_and_state_symlink_fail_closed(tmp_path: Path) -> None:
    state = _state_module()
    root = tmp_path / "watch"
    store = state.StateStore(root)
    store.initialize()
    state_path = root / "state.json"
    original = state_path.read_bytes()
    nested = json.loads(original)
    nested["identities"].append({"repository": model.REPOSITORY, "release_id": 1, "tag": "v1.0.0", "commit_sha": "a" * 40, "raw_path": "/secret"})
    state_path.write_text(json.dumps(nested, sort_keys=True, separators=(",", ":")))
    with pytest.raises(state.StateError) as error:
        store.read_state()
    assert error.value.reason_code == "state_corrupt"
    nested_bytes = state_path.read_bytes()

    backup = root / "state-copy"
    state_path.rename(backup)
    state_path.symlink_to(backup.name)
    with pytest.raises(state.StateError) as error:
        store.read_state()
    assert error.value.reason_code == "state_corrupt"
    assert state_path.is_symlink()
    assert backup.read_bytes() == nested_bytes


def test_destination_is_part_of_unique_outbox_identity(tmp_path: Path) -> None:
    store = _store(tmp_path / "watch")
    store.initialize()
    identity = _identity()
    first = _report(identity)
    _commit_discovery(store, _discovery((identity,)), [first], destination="123456789012345678")
    second = _report(identity, now=datetime(2026, 10, 28, 15, 0, tzinfo=timezone.utc))
    _commit_discovery(store, _discovery((identity,)), [second], destination="223456789012345678")
    outbox = store.read_state()["outbox"]
    assert len(outbox) == 2
    assert {record["destination_id"] for record in outbox} == {
        "123456789012345678", "223456789012345678",
    }
