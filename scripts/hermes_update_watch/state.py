"""Atomic, fail-closed local state and report storage for the update watcher."""

from __future__ import annotations

import copy
import fcntl
import hashlib
import json
import os
import re
import secrets
import stat
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

from . import model
from . import report as report_module

STATE_SCHEMA = "hermes.update-watch-state/v1"
STATE_FILENAME = "state.json"
LOCK_FILENAME = "state.lock"
REPORT_DIRECTORY = "reports"
MAX_STATE_BYTES = 8 * 1024 * 1024
MAX_REPORT_BYTES = model.REPORT_MAX_BYTES
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_DESTINATION_RE = re.compile(r"^[1-9][0-9]{5,19}$")
_REASON_CODES = frozenset(
    {
        "send_outcome_unknown_after_restart",
        "transport_timeout",
        "transport_nonzero",
        "transport_output_invalid",
        "process_unavailable",
        "receipt_invalid",
        "operator_reconciliation_required",
    }
)
_FAILED_NO_SEND_REASONS = frozenset(
    {
        "report_expired",
        "destination_invalid",
        "alert_validation_failed",
        "report_validation_failed",
        "transport_unavailable_before_invocation",
    }
)
_FORBIDDEN_CHECKOUTS = (
    Path("/opt/hermes-agent"),
    Path("/opt/hermes-agent-worktrees/hermes-update-watch"),
)
_DIRECTORY_FLAGS = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_CLOEXEC", 0)
_FILE_FLAGS = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
_WRITE_FLAGS = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)


class StateError(RuntimeError):
    """Sanitized state/storage failure carrying only a stable reason code."""

    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        super().__init__(reason_code)


@dataclass(frozen=True, slots=True)
class SendIntent:
    """Durable send intent plus immutable report bytes for snapshot-based transport."""

    attempt_id: str
    destination_id: str
    report_id: str
    attachment_filename: str
    attachment_bytes: bytes
    report_sha256: str
    message_sha256: str
    expires_at: str
    attachment_size: int


@dataclass(frozen=True, slots=True)
class PostReceipt:
    """Fully parsed success receipt required to transition sending to confirmed."""

    destination_id: str
    attempt_id: str
    message_id: str
    timestamp: str
    attachment_filename: str
    attachment_size: int
    report_sha256: str
    message_sha256: str


class StateStore:
    """Explicit root-scoped store; construction and read methods never create files."""

    def __init__(self, root: str | os.PathLike[str]) -> None:
        raw = os.fspath(root)
        if not isinstance(raw, str):
            raise StateError("unsafe_store_path")
        path = Path(raw)
        if not path.is_absolute() or ".." in path.parts or len(path.parts) < 2:
            raise StateError("unsafe_store_path")
        normalized = Path(os.path.normpath(raw))
        if _inside_checkout(normalized):
            raise StateError("unsafe_store_path")
        self.root = normalized

    def initialize(self) -> dict[str, Any]:
        """Create a new empty private store only when explicitly requested."""
        root_fd, created = _open_root(self.root, create_last=True)
        try:
            _check_directory(root_fd, "store")
            if not created:
                state_fd = _open_state_file(root_fd)
                try:
                    data = _read_fd(state_fd, MAX_STATE_BYTES, "state")
                finally:
                    os.close(state_fd)
                reports_fd = _open_reports_dir(root_fd)
                try:
                    return _load_state_data(data, reports_fd)
                finally:
                    os.close(reports_fd)

            _create_subdirectory(root_fd, REPORT_DIRECTORY)
            lock_fd = _open_lock(root_fd, create=True)
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                initial = _empty_state()
                _write_state(root_fd, initial, allow_missing=True)
            except StateError:
                raise
            except OSError:
                raise StateError("state_unavailable") from None
            finally:
                try:
                    fcntl.flock(lock_fd, fcntl.LOCK_UN)
                except OSError:
                    pass
                os.close(lock_fd)
            reports_fd = _open_reports_dir(root_fd)
            try:
                return _load_state_data(_read_state_bytes(root_fd), reports_fd)
            finally:
                os.close(reports_fd)
        finally:
            os.close(root_fd)

    def read_state(self) -> dict[str, Any]:
        """Read a bounded snapshot without creating, repairing, or locking files."""
        root_fd = _open_root_existing(self.root)
        try:
            _check_directory(root_fd, "store")
            reports_fd = _open_reports_dir(root_fd)
            try:
                return _load_state_data(_read_state_bytes(root_fd), reports_fd)
            finally:
                os.close(reports_fd)
        finally:
            os.close(root_fd)

    def read_report(self, report_id: str) -> dict[str, Any]:
        """Read one validated immutable report by UUID, never by arbitrary path."""
        if not _valid_uuid4(report_id):
            raise StateError("invalid_report_id")
        root_fd = _open_root_existing(self.root)
        try:
            _check_directory(root_fd, "store")
            reports_fd = _open_reports_dir(root_fd)
            try:
                payload = _read_report_bytes(reports_fd, report_id)
                return _load_report(payload, report_id)
            finally:
                os.close(reports_fd)
        finally:
            os.close(root_fd)

    @contextmanager
    def transaction(self) -> Iterator["StateTransaction"]:
        """Hold a nonblocking process lock through all mutations and any send."""
        root_fd = _open_root_existing(self.root)
        lock_fd: int | None = None
        reports_fd: int | None = None
        try:
            _check_directory(root_fd, "store")
            reports_fd = _open_reports_dir(root_fd)
            lock_fd = _open_lock(root_fd, create=False)
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise StateError("lock_busy") from None
            except OSError:
                raise StateError("state_unavailable") from None
            state = _load_state_data(_read_state_bytes(root_fd), reports_fd)
            tx = StateTransaction(self, root_fd, reports_fd, state)
            if tx._recover_stale_sends():
                tx._persist()
            yield tx
        finally:
            if lock_fd is not None:
                try:
                    fcntl.flock(lock_fd, fcntl.LOCK_UN)
                except OSError:
                    pass
                os.close(lock_fd)
            if reports_fd is not None:
                os.close(reports_fd)
            os.close(root_fd)


class StateTransaction:
    """Small transaction facade; every mutator durably writes before returning."""

    def __init__(self, store: StateStore, root_fd: int, reports_fd: int, state: dict[str, Any]) -> None:
        self._store = store
        self._root_fd = root_fd
        self._reports_fd = reports_fd
        self._state = state

    @property
    def state(self) -> dict[str, Any]:
        """Return a detached snapshot so callers cannot bypass validated mutators."""
        return copy.deepcopy(self._state)

    def commit_discovery(
        self,
        result: model.DiscoveryResult,
        reports: Sequence[dict[str, Any]],
        *,
        destination_id: str,
        now: datetime | None = None,
    ) -> tuple[str, ...]:
        """Persist validated reports first, then one complete discovery snapshot."""
        identity_rows, tag_rows = _validate_discovery(result)
        if not _valid_destination(destination_id):
            raise StateError("destination_invalid")
        if not isinstance(reports, (list, tuple)) or len(reports) != len(result.candidates):
            raise StateError("report_set_invalid")
        reports_by_release: dict[int, tuple[dict[str, Any], bytes]] = {}
        for candidate, report_value in zip(result.candidates, reports, strict=True):
            try:
                report = report_module.validate_report(report_value)
                payload = report_module.serialize_report(report)
            except report_module.ReportValidationError:
                raise StateError("report_validation_failed") from None
            source = report["source"]
            if (
                source["repository"] != candidate.repository
                or source["release_id"] != candidate.release_id
                or source["tag"] != candidate.tag
                or source["tag_sha"] != candidate.tag_sha.lower()
                or source["commit_sha"] != candidate.commit_sha.lower()
            ):
                raise StateError("report_identity_mismatch")
            if candidate.release_id in reports_by_release:
                raise StateError("report_set_invalid")
            reports_by_release[candidate.release_id] = (report, payload)

        old_identities = {item["release_id"]: (item["tag"], item["commit_sha"]) for item in self._state["identities"]}
        old_tags = {item["tag"]: item["commit_sha"] for item in self._state["tag_bindings"]}
        new_identities = dict(old_identities)
        new_tags = dict(old_tags)
        for release_id, tag, commit_sha in identity_rows:
            previous = new_identities.get(release_id)
            if previous is not None and previous != (tag, commit_sha):
                raise StateError("identity_changed")
            bound_sha = new_tags.get(tag)
            if bound_sha is not None and bound_sha != commit_sha:
                raise StateError("tag_moved")
            new_identities[release_id] = (tag, commit_sha)
            new_tags[tag] = commit_sha

        outbox = copy.deepcopy(self._state["outbox"])
        accepted_report_ids: list[str] = []
        existing_identity_rows = tuple(self._state["identities"])
        for candidate in result.candidates:
            report, payload = reports_by_release[candidate.release_id]
            key = _identity_key(_identity_record(candidate))
            record_index = next(
                (
                    index
                    for index, record in enumerate(outbox)
                    if _record_identity_key(record) == key and record["destination_id"] == destination_id
                ),
                None,
            )
            previously_known_same_tag = any(
                identity["release_id"] != candidate.release_id
                and identity["tag"] == candidate.tag
                and identity["commit_sha"] == candidate.commit_sha.lower()
                for identity in existing_identity_rows
            )
            if record_index is None and previously_known_same_tag:
                continue
            if record_index is not None:
                previous_record = outbox[record_index]
                if previous_record["state"] != "pending" or previous_record["attempt_id"] is not None:
                    continue
            _write_immutable_report(self._reports_fd, report["report_id"], payload)
            accepted_report_ids.append(report["report_id"])
            report_sha256 = hashlib.sha256(payload).hexdigest()
            replacement = {
                "release_identity": _identity_record(candidate),
                "destination_id": destination_id,
                "state": "pending",
                "attempt_id": None,
                "prompt_template_version": report["prompt_template_version"],
                "message_sha256": None,
                "report_sha256": report_sha256,
                "report_id": report["report_id"],
                "expires_at": report["expires_at"],
                "receipt_id": None,
                "reason_code": None,
            }
            if record_index is None:
                outbox.append(replacement)
            else:
                outbox[record_index] = replacement

        timestamp = _format_timestamp(now if now is not None else datetime.now(timezone.utc))
        next_state = {
            "schema": STATE_SCHEMA,
            "last_complete_scan": timestamp,
            "seen_not_notified": sorted(set(self._state["seen_not_notified"]) | set(result.state.seen_not_notified)),
            "identities": [
                {"repository": model.REPOSITORY, "release_id": release_id, "tag": tag, "commit_sha": commit_sha}
                for release_id, (tag, commit_sha) in sorted(new_identities.items())
            ],
            "tag_bindings": [
                {"repository": model.REPOSITORY, "tag": tag, "commit_sha": commit_sha}
                for tag, commit_sha in sorted(new_tags.items())
            ],
            "pending_release_ids": sorted(set(result.state.pending_release_ids)),
            "outbox": sorted(outbox, key=_record_sort_key),
        }
        _validate_state(next_state, self._reports_fd)
        _write_state(self._root_fd, next_state)
        self._state = next_state
        return tuple(accepted_report_ids)

    def begin_send(
        self,
        identity: model.ReleaseIdentity,
        destination_id: str,
        message_sha256: str,
        *,
        now: datetime | None = None,
    ) -> SendIntent:
        """Persist the exact attempt and hashes before transport invocation."""
        self._assert_namespace_binding()
        identity_record = _identity_record(identity)
        if not _valid_destination(destination_id) or not _valid_sha256(message_sha256):
            raise StateError("invalid_send_intent")
        record = self._find_outbox(identity_record, destination_id)
        if record["state"] != "pending" or record["attempt_id"] is not None:
            raise StateError("invalid_delivery_transition")
        payload = _read_report_bytes(self._reports_fd, record["report_id"])
        report = _load_report(payload, record["report_id"])
        if hashlib.sha256(payload).hexdigest() != record["report_sha256"]:
            raise StateError("report_corrupt")
        now_text = _format_timestamp(now if now is not None else datetime.now(timezone.utc))
        if now_text >= record["expires_at"]:
            raise StateError("report_expired")
        attempt_id = str(uuid.uuid4())
        record["state"] = "sending"
        record["attempt_id"] = attempt_id
        record["prompt_template_version"] = report["prompt_template_version"]
        record["message_sha256"] = message_sha256
        record["reason_code"] = None
        self._persist()
        return SendIntent(
            attempt_id=attempt_id,
            destination_id=destination_id,
            report_id=record["report_id"],
            attachment_filename=f"{record['report_id']}.json",
            attachment_bytes=payload,
            report_sha256=record["report_sha256"],
            message_sha256=message_sha256,
            expires_at=record["expires_at"],
            attachment_size=len(payload),
        )

    def confirm_send(self, identity: model.ReleaseIdentity, destination_id: str, receipt: PostReceipt) -> None:
        """Confirm only from a complete typed receipt matching the persisted intent."""
        record = self._find_outbox(_identity_record(identity), destination_id)
        if type(receipt) is not PostReceipt or record["state"] != "sending":
            raise StateError("invalid_receipt")
        payload = _read_report_bytes(self._reports_fd, record["report_id"])
        expected_filename = f"{record['report_id']}.json"
        if (
            receipt.destination_id != destination_id
            or receipt.attempt_id != record["attempt_id"]
            or not _valid_numeric_id(receipt.message_id)
            or not _valid_timestamp(receipt.timestamp)
            or receipt.attachment_filename != expected_filename
            or type(receipt.attachment_size) is not int
            or receipt.attachment_size != len(payload)
            or receipt.report_sha256 != record["report_sha256"]
            or receipt.message_sha256 != record["message_sha256"]
        ):
            raise StateError("invalid_receipt")
        record["state"] = "confirmed"
        record["receipt_id"] = receipt.message_id
        record["reason_code"] = None
        self._persist()

    def mark_ambiguous(
        self,
        identity: model.ReleaseIdentity,
        destination_id: str,
        attempt_id: str,
        reason_code: str,
    ) -> None:
        """Retain uncertain send outcomes without permitting automatic replay."""
        record = self._find_outbox(_identity_record(identity), destination_id)
        if (
            record["state"] != "sending"
            or attempt_id != record["attempt_id"]
            or reason_code not in _REASON_CODES - {"send_outcome_unknown_after_restart"}
        ):
            raise StateError("invalid_delivery_transition")
        record["state"] = "ambiguous"
        record["reason_code"] = reason_code
        self._persist()

    def fail_before_send(
        self, identity: model.ReleaseIdentity, destination_id: str, reason_code: str
    ) -> None:
        """Record a proven pre-invocation failure; no attempted send is inferred."""
        record = self._find_outbox(_identity_record(identity), destination_id)
        if record["state"] != "pending" or reason_code not in _FAILED_NO_SEND_REASONS:
            raise StateError("invalid_delivery_transition")
        record["state"] = "failed_no_send"
        record["reason_code"] = reason_code
        self._persist()

    def abort_send_before_invocation(
        self,
        identity: model.ReleaseIdentity,
        destination_id: str,
        attempt_id: str,
        reason_code: str,
    ) -> None:
        """Close a persisted attempt only when transport proves no child started."""
        record = self._find_outbox(_identity_record(identity), destination_id)
        if (
            record["state"] != "sending"
            or record["attempt_id"] != attempt_id
            or reason_code not in _FAILED_NO_SEND_REASONS
        ):
            raise StateError("invalid_delivery_transition")
        record["state"] = "failed_no_send"
        record["attempt_id"] = None
        record["message_sha256"] = None
        record["receipt_id"] = None
        record["reason_code"] = reason_code
        self._persist()

    def _find_outbox(self, identity: dict[str, Any], destination_id: str) -> dict[str, Any]:
        if not _valid_destination(destination_id):
            raise StateError("destination_invalid")
        for record in self._state["outbox"]:
            if _record_identity_key(record) == _identity_key(identity) and record["destination_id"] == destination_id:
                return record
        raise StateError("outbox_item_missing")

    def _recover_stale_sends(self) -> bool:
        changed = False
        for record in self._state["outbox"]:
            if record["state"] == "sending":
                record["state"] = "ambiguous"
                record["reason_code"] = "send_outcome_unknown_after_restart"
                changed = True
        return changed

    def _persist(self) -> None:
        self._assert_namespace_binding()
        _validate_state(self._state, self._reports_fd)
        _write_state(self._root_fd, self._state)

    def _assert_namespace_binding(self) -> None:
        """Reject a renamed store namespace instead of acting on a detached root."""
        current_root: int | None = None
        current_reports: int | None = None
        try:
            current_root = _open_directory_path(self._store.root)
            _check_directory(current_root, "store")
            original_root_info = os.fstat(self._root_fd)
            current_root_info = os.fstat(current_root)
            if (original_root_info.st_dev, original_root_info.st_ino) != (
                current_root_info.st_dev, current_root_info.st_ino
            ):
                raise StateError("store_namespace_changed")
            current_reports = os.open(
                REPORT_DIRECTORY,
                _DIRECTORY_FLAGS | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=current_root,
            )
            _check_directory(current_reports, "reports")
            original_reports_info = os.fstat(self._reports_fd)
            current_reports_info = os.fstat(current_reports)
            if (original_reports_info.st_dev, original_reports_info.st_ino) != (
                current_reports_info.st_dev, current_reports_info.st_ino
            ):
                raise StateError("store_namespace_changed")
        except StateError as error:
            if error.reason_code == "store_namespace_changed":
                raise
            raise StateError("store_namespace_changed") from None
        except OSError:
            raise StateError("store_namespace_changed") from None
        finally:
            if current_reports is not None:
                os.close(current_reports)
            if current_root is not None:
                os.close(current_root)


def _empty_state() -> dict[str, Any]:
    return {
        "schema": STATE_SCHEMA,
        "last_complete_scan": None,
        "seen_not_notified": [],
        "identities": [],
        "tag_bindings": [],
        "pending_release_ids": [],
        "outbox": [],
    }


def _open_root(path: Path, *, create_last: bool) -> tuple[int, bool]:
    parent = path.parent
    parent_fd = _open_directory_path(parent)
    created = False
    try:
        try:
            fd = os.open(path.name, _DIRECTORY_FLAGS | getattr(os, "O_NOFOLLOW", 0), dir_fd=parent_fd)
        except FileNotFoundError:
            if not create_last:
                raise StateError("store_not_initialized") from None
            os.mkdir(path.name, 0o700, dir_fd=parent_fd)
            created = True
            try:
                fd = os.open(path.name, _DIRECTORY_FLAGS | getattr(os, "O_NOFOLLOW", 0), dir_fd=parent_fd)
                os.fchmod(fd, 0o700)
                os.fsync(parent_fd)
            except OSError:
                raise StateError("state_unavailable") from None
        except OSError as error:
            if error.errno in (getattr(os, "ELOOP", 40), getattr(os, "ENOTDIR", 20)):
                raise StateError("unsafe_store_path") from None
            raise StateError("state_unavailable") from None
    finally:
        os.close(parent_fd)
    return fd, created


def _open_root_existing(path: Path) -> int:
    fd = _open_directory_path(path)
    _check_directory(fd, "store")
    _open_reports_dir(fd, close_after=True)
    return fd


def _open_directory_path(path: Path) -> int:
    flags = _DIRECTORY_FLAGS | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open("/", flags)
    except OSError:
        raise StateError("unsafe_store_path") from None
    try:
        for component in path.parts[1:]:
            if component in ("", ".", ".."):
                raise StateError("unsafe_store_path")
            try:
                next_fd = os.open(component, flags, dir_fd=fd)
            except OSError as error:
                if error.errno in (getattr(os, "ELOOP", 40), getattr(os, "ENOTDIR", 20)):
                    raise StateError("unsafe_store_path") from None
                if error.errno == getattr(os, "ENOENT", 2):
                    raise StateError("store_not_initialized") from None
                raise StateError("state_unavailable") from None
            os.close(fd)
            fd = next_fd
        return fd
    except Exception:
        os.close(fd)
        raise


def _inside_checkout(path: Path) -> bool:
    candidate = str(path)
    for checkout in _FORBIDDEN_CHECKOUTS:
        root = str(checkout)
        try:
            if os.path.commonpath((candidate, root)) == root:
                return True
        except ValueError:
            continue
    return False


def _check_directory(fd: int, label: str) -> None:
    try:
        info = os.fstat(fd)
    except OSError:
        raise StateError("state_unavailable") from None
    if not stat.S_ISDIR(info.st_mode):
        raise StateError("unsafe_store_path")
    if info.st_uid != os.geteuid():
        raise StateError("store_owner_invalid")
    if stat.S_IMODE(info.st_mode) != 0o700:
        raise StateError("store_mode_invalid")


def _create_subdirectory(parent_fd: int, name: str) -> None:
    try:
        os.mkdir(name, 0o700, dir_fd=parent_fd)
        fd = os.open(name, _DIRECTORY_FLAGS | getattr(os, "O_NOFOLLOW", 0), dir_fd=parent_fd)
        try:
            os.fchmod(fd, 0o700)
            os.fsync(parent_fd)
        finally:
            os.close(fd)
    except OSError:
        raise StateError("state_unavailable") from None


def _open_reports_dir(root_fd: int, *, close_after: bool = False) -> int:
    try:
        fd = os.open(REPORT_DIRECTORY, _DIRECTORY_FLAGS | getattr(os, "O_NOFOLLOW", 0), dir_fd=root_fd)
    except OSError as error:
        if error.errno in (getattr(os, "ELOOP", 40), getattr(os, "ENOTDIR", 20)):
            raise StateError("unsafe_store_path") from None
        raise StateError("state_missing") from None
    try:
        _check_directory(fd, "reports")
    except Exception:
        os.close(fd)
        raise
    if close_after:
        os.close(fd)
        return -1
    return fd


def _open_lock(root_fd: int, *, create: bool) -> int:
    flags = os.O_RDWR | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    if create:
        flags |= os.O_CREAT | os.O_EXCL
    try:
        fd = os.open(LOCK_FILENAME, flags, 0o600, dir_fd=root_fd)
    except FileExistsError:
        if create:
            raise StateError("state_corrupt") from None
        raise StateError("lock_busy") from None
    except OSError as error:
        if error.errno in (getattr(os, "ELOOP", 40), getattr(os, "ENOTDIR", 20)):
            raise StateError("unsafe_store_path") from None
        raise StateError("state_unavailable") from None
    try:
        if create:
            # This inode was created exclusively by this call; apply its private
            # mode before validating, independent of the process umask.
            os.fchmod(fd, 0o600)
            os.fsync(fd)
            os.fsync(root_fd)
        _check_regular_file(fd, MAX_STATE_BYTES, "lock")
        return fd
    except Exception:
        os.close(fd)
        raise


def _open_state_file(root_fd: int) -> int:
    try:
        fd = os.open(STATE_FILENAME, _FILE_FLAGS, dir_fd=root_fd)
    except FileNotFoundError:
        raise StateError("state_missing") from None
    except OSError as error:
        if error.errno in (getattr(os, "ELOOP", 40), getattr(os, "ENOTDIR", 20)):
            raise StateError("state_corrupt") from None
        raise StateError("state_unavailable") from None
    try:
        _check_regular_file(fd, MAX_STATE_BYTES, "state")
        return fd
    except Exception:
        os.close(fd)
        raise


def _check_regular_file(fd: int, max_size: int, label: str) -> os.stat_result:
    try:
        info = os.fstat(fd)
    except OSError:
        raise StateError("state_unavailable") from None
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise StateError(f"{label}_file_invalid")
    if info.st_uid != os.geteuid():
        raise StateError(f"{label}_owner_invalid")
    if stat.S_IMODE(info.st_mode) != 0o600:
        raise StateError(f"{label}_mode_invalid")
    if info.st_size < 0 or info.st_size > max_size:
        raise StateError(f"{label}_too_large")
    return info


def _read_fd(fd: int, max_size: int, label: str) -> bytes:
    _check_regular_file(fd, max_size, label)
    chunks = bytearray()
    try:
        while len(chunks) <= max_size:
            chunk = os.read(fd, min(65_536, max_size + 1 - len(chunks)))
            if not chunk:
                break
            chunks.extend(chunk)
    except OSError:
        raise StateError("state_unavailable") from None
    if len(chunks) > max_size:
        raise StateError(f"{label}_too_large")
    return bytes(chunks)


def _read_state_bytes(root_fd: int) -> bytes:
    fd = _open_state_file(root_fd)
    try:
        return _read_fd(fd, MAX_STATE_BYTES, "state")
    finally:
        os.close(fd)


def _read_report_bytes(reports_fd: int, report_id: str) -> bytes:
    if not _valid_uuid4(report_id):
        raise StateError("invalid_report_id")
    name = f"{report_id}.json"
    try:
        fd = os.open(name, _FILE_FLAGS, dir_fd=reports_fd)
    except FileNotFoundError:
        raise StateError("report_missing") from None
    except OSError as error:
        if error.errno in (getattr(os, "ELOOP", 40), getattr(os, "ENOTDIR", 20)):
            raise StateError("report_file_invalid") from None
        raise StateError("state_unavailable") from None
    try:
        return _read_fd(fd, MAX_REPORT_BYTES, "report")
    finally:
        os.close(fd)


def _load_report(payload: bytes, report_id: str) -> dict[str, Any]:
    try:
        parsed = report_module.load_report(payload)
    except report_module.ReportValidationError:
        raise StateError("report_corrupt") from None
    if parsed["report_id"] != report_id:
        raise StateError("report_corrupt")
    return parsed


def _load_state_data(payload: bytes, reports_fd: int) -> dict[str, Any]:
    try:
        value = json.loads(
            payload.decode("utf-8", errors="strict"),
            object_pairs_hook=_unique_object,
            parse_constant=lambda _value: (_ for _ in ()).throw(ValueError()),
        )
        _validate_state(value, reports_fd)
        return value
    except StateError:
        raise
    except (TypeError, ValueError, OverflowError, RecursionError, UnicodeError):
        raise StateError("state_corrupt") from None


def _validate_state(value: Any, reports_fd: int) -> None:
    expected = {
        "schema", "last_complete_scan", "seen_not_notified", "identities",
        "tag_bindings", "pending_release_ids", "outbox",
    }
    if type(value) is not dict or set(value) != expected or value["schema"] != STATE_SCHEMA:
        raise StateError("state_corrupt")
    if value["last_complete_scan"] is not None and not _valid_timestamp(value["last_complete_scan"]):
        raise StateError("state_corrupt")
    seen = _id_list(value["seen_not_notified"])
    pending = _id_list(value["pending_release_ids"])
    if type(value["identities"]) is not list or type(value["tag_bindings"]) is not list or type(value["outbox"]) is not list:
        raise StateError("state_corrupt")
    identity_by_id: dict[int, tuple[str, str]] = {}
    tag_to_sha: dict[str, str] = {}
    for item in value["identities"]:
        if type(item) is not dict or set(item) != {"repository", "release_id", "tag", "commit_sha"}:
            raise StateError("state_corrupt")
        if item["repository"] != model.REPOSITORY or type(item["release_id"]) is not int or item["release_id"] <= 0:
            raise StateError("state_corrupt")
        if type(item["tag"]) is not str or model.parse_stable_tag(item["tag"]) is None:
            raise StateError("state_corrupt")
        if type(item["commit_sha"]) is not str or _FULL_SHA_RE.fullmatch(item["commit_sha"]) is None:
            raise StateError("state_corrupt")
        if item["release_id"] in identity_by_id:
            raise StateError("state_corrupt")
        identity_by_id[item["release_id"]] = (item["tag"], item["commit_sha"])
        prior = tag_to_sha.get(item["tag"])
        if prior is not None and prior != item["commit_sha"]:
            raise StateError("state_corrupt")
        tag_to_sha[item["tag"]] = item["commit_sha"]
    binding_by_tag: dict[str, str] = {}
    for item in value["tag_bindings"]:
        if type(item) is not dict or set(item) != {"repository", "tag", "commit_sha"}:
            raise StateError("state_corrupt")
        if item["repository"] != model.REPOSITORY or type(item["tag"]) is not str or model.parse_stable_tag(item["tag"]) is None:
            raise StateError("state_corrupt")
        if type(item["commit_sha"]) is not str or _FULL_SHA_RE.fullmatch(item["commit_sha"]) is None:
            raise StateError("state_corrupt")
        if item["tag"] in binding_by_tag:
            raise StateError("state_corrupt")
        binding_by_tag[item["tag"]] = item["commit_sha"]
    if binding_by_tag != tag_to_sha:
        raise StateError("state_corrupt")
    if seen != value["seen_not_notified"] or pending != value["pending_release_ids"]:
        raise StateError("state_corrupt")

    outbox_keys: set[tuple[str, int, str, str, str]] = set()
    for record in value["outbox"]:
        _validate_outbox_record(record, identity_by_id, binding_by_tag, reports_fd, outbox_keys)


def _validate_outbox_record(
    record: Any,
    identities: dict[int, tuple[str, str]],
    bindings: dict[str, str],
    reports_fd: int,
    outbox_keys: set[tuple[str, int, str, str, str]],
) -> None:
    required = {
        "release_identity", "destination_id", "state", "attempt_id", "prompt_template_version",
        "message_sha256", "report_sha256", "report_id", "expires_at", "receipt_id", "reason_code",
    }
    if type(record) is not dict or set(record) != required:
        raise StateError("state_corrupt")
    identity = record["release_identity"]
    normalized = _validate_identity_mapping(identity)
    release_id = normalized["release_id"]
    if identities.get(release_id) != (normalized["tag"], normalized["commit_sha"]):
        raise StateError("state_corrupt")
    if bindings.get(normalized["tag"]) != normalized["commit_sha"]:
        raise StateError("state_corrupt")
    destination = record["destination_id"]
    if not _valid_destination(destination):
        raise StateError("state_corrupt")
    key = (normalized["repository"], release_id, normalized["tag"], normalized["commit_sha"], destination)
    if key in outbox_keys:
        raise StateError("state_corrupt")
    outbox_keys.add(key)
    status = record["state"]
    if status not in {"pending", "sending", "confirmed", "failed_no_send", "ambiguous"}:
        raise StateError("state_corrupt")
    attempt = record["attempt_id"]
    report_id = record["report_id"]
    if not _valid_uuid4(report_id) or not _valid_timestamp(record["expires_at"]):
        raise StateError("state_corrupt")
    if type(record["prompt_template_version"]) is not str or not record["prompt_template_version"]:
        raise StateError("state_corrupt")
    if not _valid_sha256(record["report_sha256"]):
        raise StateError("state_corrupt")
    message_sha = record["message_sha256"]
    if message_sha is not None and not _valid_sha256(message_sha):
        raise StateError("state_corrupt")
    receipt = record["receipt_id"]
    reason = record["reason_code"]
    if status == "pending":
        if attempt is not None or message_sha is not None or receipt is not None or reason is not None:
            raise StateError("state_corrupt")
    elif status == "sending":
        if not _valid_uuid4(attempt) or message_sha is None or receipt is not None or reason is not None:
            raise StateError("state_corrupt")
    elif status == "confirmed":
        if not _valid_uuid4(attempt) or message_sha is None or not _valid_numeric_id(receipt) or reason is not None:
            raise StateError("state_corrupt")
    elif status == "ambiguous":
        if not _valid_uuid4(attempt) or message_sha is None or receipt is not None or reason not in _REASON_CODES:
            raise StateError("state_corrupt")
    else:
        if attempt is not None or message_sha is not None or receipt is not None or reason not in _FAILED_NO_SEND_REASONS:
            raise StateError("state_corrupt")
    payload = _read_report_bytes(reports_fd, report_id)
    report = _load_report(payload, report_id)
    if (
        hashlib.sha256(payload).hexdigest() != record["report_sha256"]
        or report["source"]["repository"] != normalized["repository"]
        or report["source"]["release_id"] != release_id
        or report["source"]["tag"] != normalized["tag"]
        or report["source"]["commit_sha"] != normalized["commit_sha"]
        or report["expires_at"] != record["expires_at"]
        or report["prompt_template_version"] != record["prompt_template_version"]
    ):
        raise StateError("state_corrupt")


def _validate_identity_mapping(value: Any) -> dict[str, Any]:
    if type(value) is not dict or set(value) != {"repository", "release_id", "tag", "commit_sha"}:
        raise StateError("state_corrupt")
    if value["repository"] != model.REPOSITORY or type(value["release_id"]) is not int or value["release_id"] <= 0:
        raise StateError("state_corrupt")
    if type(value["tag"]) is not str or model.parse_stable_tag(value["tag"]) is None:
        raise StateError("state_corrupt")
    if type(value["commit_sha"]) is not str or _FULL_SHA_RE.fullmatch(value["commit_sha"]) is None:
        raise StateError("state_corrupt")
    return dict(value)


def _validate_discovery(result: Any) -> tuple[tuple[tuple[int, str, str], ...], tuple[tuple[str, str], ...]]:
    if type(result) is not model.DiscoveryResult or result.status not in ("available", "no_change") or result.reason_code is not None:
        raise StateError("incomplete_discovery")
    if type(result.state) is not model.DiscoveryState or result.state.has_completed_scan is not True:
        raise StateError("incomplete_discovery")
    if not isinstance(result.candidates, tuple) or not isinstance(result.seen_not_notified, tuple) or not isinstance(result.pending_release_ids, tuple):
        raise StateError("incomplete_discovery")
    if result.seen_not_notified != result.state.seen_not_notified or result.pending_release_ids != result.state.pending_release_ids:
        raise StateError("incomplete_discovery")
    if result.status == "available" and not result.candidates:
        raise StateError("incomplete_discovery")
    if result.status == "no_change" and result.candidates:
        raise StateError("incomplete_discovery")
    if not isinstance(result.state.identities_by_release_id, tuple) or not isinstance(result.state.tag_commit_shas, tuple):
        raise StateError("incomplete_discovery")
    identity_rows = result.state.identities_by_release_id
    tag_rows = result.state.tag_commit_shas
    identities: dict[int, tuple[str, str]] = {}
    for row in identity_rows:
        if not isinstance(row, tuple) or len(row) != 3:
            raise StateError("incomplete_discovery")
        release_id, tag, commit_sha = row
        if type(release_id) is not int or release_id <= 0 or type(tag) is not str or model.parse_stable_tag(tag) is None:
            raise StateError("incomplete_discovery")
        if type(commit_sha) is not str or _FULL_SHA_RE.fullmatch(commit_sha.lower()) is None or release_id in identities:
            raise StateError("incomplete_discovery")
        identities[release_id] = (tag, commit_sha.lower())
    tags: dict[str, str] = {}
    for row in tag_rows:
        if not isinstance(row, tuple) or len(row) != 2:
            raise StateError("incomplete_discovery")
        tag, commit_sha = row
        if type(tag) is not str or model.parse_stable_tag(tag) is None or type(commit_sha) is not str or _FULL_SHA_RE.fullmatch(commit_sha.lower()) is None:
            raise StateError("incomplete_discovery")
        if tag in tags and tags[tag] != commit_sha.lower():
            raise StateError("incomplete_discovery")
        tags[tag] = commit_sha.lower()
    if any(tag not in tags or tags[tag] != commit for tag, commit in identities.values()):
        raise StateError("incomplete_discovery")
    if set(tags) != {tag for tag, _commit in identities.values()}:
        raise StateError("incomplete_discovery")
    seen = _id_list(result.seen_not_notified)
    pending = _id_list(result.pending_release_ids)
    if seen != list(result.seen_not_notified) or pending != list(result.pending_release_ids):
        raise StateError("incomplete_discovery")
    if set(seen) & set(pending):
        raise StateError("incomplete_discovery")
    candidate_ids: set[int] = set()
    for candidate in result.candidates:
        normalized = _identity_record(candidate)
        release_id = normalized["release_id"]
        if release_id in candidate_ids or identities.get(release_id) != (normalized["tag"], normalized["commit_sha"]):
            raise StateError("incomplete_discovery")
        candidate_ids.add(release_id)
    if type(result.latest_identity) is not model.ReleaseIdentity:
        raise StateError("incomplete_discovery")
    latest = _identity_record(result.latest_identity)
    if identities.get(latest["release_id"]) != (latest["tag"], latest["commit_sha"]):
        raise StateError("incomplete_discovery")
    return tuple(identity_rows), tuple(tag_rows)


def _identity_record(identity: Any) -> dict[str, Any]:
    if type(identity) is not model.ReleaseIdentity:
        raise StateError("invalid_release_identity")
    if (
        type(identity.release_id) is not int
        or identity.release_id <= 0
        or type(identity.repository) is not str
        or identity.repository != model.REPOSITORY
        or type(identity.tag) is not str
        or model.parse_stable_tag(identity.tag) is None
        or type(identity.commit_sha) is not str
        or _FULL_SHA_RE.fullmatch(identity.commit_sha.lower()) is None
        or type(identity.tag_sha) is not str
        or _FULL_SHA_RE.fullmatch(identity.tag_sha.lower()) is None
    ):
        raise StateError("invalid_release_identity")
    return {
        "repository": model.REPOSITORY,
        "release_id": identity.release_id,
        "tag": identity.tag,
        "commit_sha": identity.commit_sha.lower(),
    }


def _identity_key(identity: Mapping[str, Any]) -> tuple[str, int, str, str]:
    return (identity["repository"], identity["release_id"], identity["tag"], identity["commit_sha"])


def _record_identity_key(record: Mapping[str, Any]) -> tuple[str, int, str, str]:
    return _identity_key(record["release_identity"])


def _record_sort_key(record: Mapping[str, Any]) -> tuple[str, int, str, str, str]:
    return (*_record_identity_key(record), record["destination_id"])


def _id_list(value: Any) -> list[int]:
    if type(value) not in (list, tuple):
        raise StateError("state_corrupt")
    if any(type(item) is not int or item <= 0 for item in value):
        raise StateError("state_corrupt")
    return sorted(set(value))


def _valid_destination(value: Any) -> bool:
    return type(value) is str and _DESTINATION_RE.fullmatch(value) is not None


def _valid_numeric_id(value: Any) -> bool:
    return type(value) is str and _DESTINATION_RE.fullmatch(value) is not None


def _valid_sha256(value: Any) -> bool:
    return type(value) is str and _SHA256_RE.fullmatch(value) is not None


def _valid_uuid4(value: Any) -> bool:
    if type(value) is not str:
        return False
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError):
        return False
    return str(parsed) == value and parsed.version == 4 and parsed.variant == uuid.RFC_4122


def _format_timestamp(value: datetime) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise StateError("invalid_timestamp")
    try:
        if value.utcoffset() != timezone.utc.utcoffset(value):
            raise StateError("invalid_timestamp")
        return value.astimezone(timezone.utc).replace(microsecond=0).isoformat(timespec="seconds").replace("+00:00", "Z")
    except (OverflowError, ValueError):
        raise StateError("invalid_timestamp") from None


def _valid_timestamp(value: Any) -> bool:
    if type(value) is not str or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value):
        return False
    try:
        datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return False
    return True


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError
        result[key] = value
    return result


def _canonical_json(value: Any) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError, RecursionError, UnicodeError):
        raise StateError("state_corrupt") from None


def _read_state_file(fd: int) -> bytes:
    return _read_fd(fd, MAX_STATE_BYTES, "state")


def _write_all(fd: int, payload: bytes) -> None:
    view = memoryview(payload)
    while view:
        written = os.write(fd, view)
        if written <= 0:
            raise OSError
        view = view[written:]


def _write_state(root_fd: int, value: dict[str, Any], *, allow_missing: bool = False) -> None:
    payload = _canonical_json(value)
    if len(payload) > MAX_STATE_BYTES:
        raise StateError("state_too_large")
    if not allow_missing:
        fd = _open_state_file(root_fd)
        os.close(fd)
    temp_name = f".state-{uuid.uuid4()}.tmp"
    fd: int | None = None
    try:
        fd = os.open(temp_name, _WRITE_FLAGS, 0o600, dir_fd=root_fd)
        os.fchmod(fd, 0o600)
        _write_all(fd, payload)
        os.fsync(fd)
        os.close(fd)
        fd = None
        os.replace(temp_name, STATE_FILENAME, src_dir_fd=root_fd, dst_dir_fd=root_fd)
        os.fsync(root_fd)
    except StateError:
        raise
    except OSError:
        raise StateError("state_unavailable") from None
    finally:
        if fd is not None:
            os.close(fd)
        try:
            os.unlink(temp_name, dir_fd=root_fd)
        except FileNotFoundError:
            pass
        except OSError:
            pass


def _write_immutable_report(reports_fd: int, report_id: str, payload: bytes) -> None:
    if not _valid_uuid4(report_id) or len(payload) > MAX_REPORT_BYTES:
        raise StateError("report_invalid")
    name = f"{report_id}.json"
    try:
        existing = _read_report_bytes(reports_fd, report_id)
    except StateError as error:
        if error.reason_code != "report_missing":
            raise
    else:
        if existing != payload:
            raise StateError("report_id_collision")
        _load_report(existing, report_id)
        try:
            os.fsync(reports_fd)
        except OSError:
            raise StateError("state_unavailable") from None
        return

    temp_name = f".report-{uuid.uuid4()}.tmp"
    fd: int | None = None
    try:
        fd = os.open(temp_name, _WRITE_FLAGS, 0o600, dir_fd=reports_fd)
        os.fchmod(fd, 0o600)
        _write_all(fd, payload)
        os.fsync(fd)
        os.close(fd)
        fd = None
        try:
            os.link(temp_name, name, src_dir_fd=reports_fd, dst_dir_fd=reports_fd, follow_symlinks=False)
        except FileExistsError:
            existing = _read_report_bytes(reports_fd, report_id)
            if existing != payload:
                raise StateError("report_id_collision")
        os.unlink(temp_name, dir_fd=reports_fd)
        os.fsync(reports_fd)
        _load_report(_read_report_bytes(reports_fd, report_id), report_id)
    except StateError:
        raise
    except OSError:
        raise StateError("state_unavailable") from None
    finally:
        if fd is not None:
            os.close(fd)
        try:
            os.unlink(temp_name, dir_fd=reports_fd)
        except FileNotFoundError:
            pass
        except OSError:
            pass


def _read_state_bytes(root_fd: int) -> bytes:
    fd = _open_state_file(root_fd)
    try:
        return _read_state_file(fd)
    finally:
        os.close(fd)
