"""Receipt-validating, shell-free adapter for the approved ncl-discord CLI."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from typing import Any, Callable, Mapping

from . import model, process, report, state

DISCORD_CLI = "/usr/local/bin/ncl-discord"
PROCESS_TIMEOUT_SECONDS = 40.0
STDOUT_LIMIT = 16 * 1024
STDERR_LIMIT = 4 * 1024
_DESTINATION_RE = re.compile(r"^[1-9][0-9]{5,19}$")
_MESSAGE_ID_RE = _DESTINATION_RE
_PROFILES = frozenset({"default", "ragnar", "roshi"})
_PROCESS_ENV = {
    "PATH": "/usr/local/bin:/usr/bin:/bin",
    "HOME": os.path.expanduser("~"),
    "LANG": "C.UTF-8",
    "LC_ALL": "C.UTF-8",
}


class TransportError(RuntimeError):
    """Sanitized transport failure with whether a child may have been invoked."""

    def __init__(self, reason_code: str, *, invoked: bool) -> None:
        self.reason_code = reason_code
        self.invoked = invoked
        super().__init__(reason_code)


class DiscordTransport:
    """Post one already-authorized alert and accept only its typed receipt."""

    def __init__(self, *, runner: Callable[..., Any] | None = None) -> None:
        self._runner = runner or process.run_bounded_process

    def post(
        self,
        intent: state.SendIntent,
        message: str,
        target: str,
        profile: str,
    ) -> state.PostReceipt:
        """Send a sealed byte snapshot; never reopen a state-root report path."""
        payload = _validate_request(intent, message, target, profile)
        descriptor = _create_sealed_snapshot(payload)
        invoked = False
        try:
            descriptor_path = f"/proc/self/fd/{descriptor}"
            argv = (
                DISCORD_CLI,
                "post",
                target,
                message,
                "--attach",
                descriptor_path,
                "--as",
                profile,
            )
            try:
                result = self._runner(
                    argv,
                    env=dict(_PROCESS_ENV),
                    timeout_seconds=PROCESS_TIMEOUT_SECONDS,
                    stdout_limit=STDOUT_LIMIT,
                    stderr_limit=STDERR_LIMIT,
                    pass_fds=(descriptor,),
                )
            except Exception:
                # Once the runner is entered, a custom or broken runner cannot
                # prove that no child was started, so classify the outcome safe.
                invoked = True
                raise TransportError("transport_output_invalid", invoked=True) from None
            if type(result) is not process.BoundedProcessResult:
                invoked = True
                raise TransportError("transport_output_invalid", invoked=True)
            invoked = result.started
            if not result.started:
                raise TransportError("process_unavailable", invoked=False)
            if result.reason_code == "timeout":
                raise TransportError("transport_timeout", invoked=True)
            if result.reason_code is not None:
                raise TransportError("transport_output_invalid", invoked=True)
            if result.returncode != 0:
                raise TransportError("transport_nonzero", invoked=True)
            if (
                type(result.stdout) is not bytes
                or len(result.stdout) > STDOUT_LIMIT
                or type(result.stderr) is not bytes
                or len(result.stderr) > STDERR_LIMIT
            ):
                raise TransportError("transport_output_invalid", invoked=True)
            return _parse_receipt(result.stdout, intent, target, descriptor)
        finally:
            try:
                os.close(descriptor)
            except OSError:
                if sys.exc_info()[0] is None:
                    raise TransportError("transport_output_invalid", invoked=invoked) from None


def _validate_request(intent: state.SendIntent, message: str, target: str, profile: str) -> bytes:
    if (
        type(intent) is not state.SendIntent
        or type(target) is not str
        or _DESTINATION_RE.fullmatch(target) is None
        or type(profile) is not str
        or profile not in _PROFILES
        or type(message) is not str
    ):
        raise TransportError("invalid_transport_request", invoked=False)
    try:
        if report.utf16_code_units(message) > model.ALERT_MAX_UTF16_UNITS:
            raise TransportError("invalid_transport_request", invoked=False)
        payload = intent.attachment_bytes
        if type(payload) is not bytes or len(payload) > model.REPORT_MAX_BYTES:
            raise TransportError("invalid_transport_request", invoked=False)
        parsed = report.load_report(payload)
        canonical = report.serialize_report(parsed)
        expected_message = report.render_alert(parsed)
    except (report.ReportValidationError, TypeError, ValueError, OverflowError, RecursionError, UnicodeError):
        raise TransportError("invalid_transport_request", invoked=False) from None
    if (
        canonical != payload
        or parsed["report_id"] != intent.report_id
        or intent.attachment_filename != f"{intent.report_id}.json"
        or hashlib.sha256(payload).hexdigest() != intent.report_sha256
        or type(intent.attachment_size) is not int
        or intent.attachment_size != len(payload)
        or parsed["expires_at"] != intent.expires_at
        or expected_message != message
        or hashlib.sha256(message.encode("utf-8")).hexdigest() != intent.message_sha256
        or intent.destination_id != target
    ):
        raise TransportError("invalid_transport_request", invoked=False)
    return payload


def _create_sealed_snapshot(payload: bytes) -> int:
    """Create a sealed Linux memfd or fail before any external process starts."""
    required = fcntl.F_SEAL_WRITE | fcntl.F_SEAL_GROW | fcntl.F_SEAL_SHRINK | fcntl.F_SEAL_SEAL
    creator = getattr(os, "memfd_create", None)
    flags = getattr(os, "MFD_CLOEXEC", None)
    allow_sealing = getattr(os, "MFD_ALLOW_SEALING", None)
    if creator is None or flags is None or allow_sealing is None or not hasattr(fcntl, "F_ADD_SEALS"):
        raise TransportError("snapshot_unavailable", invoked=False)
    descriptor: int | None = None
    try:
        descriptor = creator("hermes-update-report", flags | allow_sealing)
        if descriptor < 3:
            replacement = fcntl.fcntl(descriptor, fcntl.F_DUPFD_CLOEXEC, 3)
            os.close(descriptor)
            descriptor = replacement
        _write_all(descriptor, payload)
        fcntl.fcntl(descriptor, fcntl.F_ADD_SEALS, required)
        seals = fcntl.fcntl(descriptor, fcntl.F_GET_SEALS)
        if seals & required != required:
            raise OSError
        # ncl-discord reopens the provided path in a child process. Prove the
        # procfs descriptor path exists before invoking that external process;
        # there is deliberately no mutable-file fallback.
        proc_path = f"/proc/self/fd/{descriptor}"
        if not os.path.isfile(proc_path):
            raise OSError
        return descriptor
    except (OSError, ValueError, TypeError):
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass
        raise TransportError("snapshot_unavailable", invoked=False) from None


def _write_all(descriptor: int, payload: bytes) -> None:
    view = memoryview(payload)
    while view:
        written = os.write(descriptor, view)
        if written <= 0:
            raise OSError
        view = view[written:]


def _parse_receipt(
    payload: bytes,
    intent: state.SendIntent,
    target: str,
    descriptor: int,
) -> state.PostReceipt:
    try:
        value = json.loads(
            payload.decode("utf-8", errors="strict"),
            object_pairs_hook=_unique_object,
            parse_constant=lambda _value: (_ for _ in ()).throw(ValueError()),
        )
        if type(value) is not dict:
            raise ValueError
        message_ids = value.get("message_ids")
        message_id = value.get("message_id")
        attachments = value.get("attachments")
        timestamp = _normalize_timestamp(value.get("timestamp"))
        if (
            value.get("status") != "ok"
            or value.get("channel_id") != target
            or type(message_ids) is not list
            or len(message_ids) != 1
            or message_ids[0] != message_id
            or type(message_id) is not str
            or _MESSAGE_ID_RE.fullmatch(message_id) is None
            or type(attachments) is not list
            or len(attachments) != 1
            or type(attachments[0]) is not dict
            or attachments[0].get("filename") != str(descriptor)
            or type(attachments[0].get("size")) is not int
            or attachments[0]["size"] != len(intent.attachment_bytes)
            or timestamp is None
        ):
            raise ValueError
    except (AttributeError, KeyError, TypeError, ValueError, OverflowError, RecursionError, UnicodeError):
        raise TransportError("transport_output_invalid", invoked=True) from None
    return state.PostReceipt(
        destination_id=target,
        attempt_id=intent.attempt_id,
        message_id=message_id,
        timestamp=timestamp,
        attachment_filename=intent.attachment_filename,
        attachment_size=len(intent.attachment_bytes),
        report_sha256=intent.report_sha256,
        message_sha256=intent.message_sha256,
    )


def _normalize_timestamp(value: Any) -> str | None:
    if type(value) is not str or len(value) > 64:
        return None
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return None
        if parsed.utcoffset() != timezone.utc.utcoffset(parsed):
            return None
        utc = parsed.astimezone(timezone.utc).replace(microsecond=0)
        return utc.isoformat(timespec="seconds").replace("+00:00", "Z")
    except (OverflowError, ValueError):
        return None


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError
        result[key] = value
    return result
