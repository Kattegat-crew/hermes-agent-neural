"""Thin monitoring-only command line over the typed watcher components."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Sequence, TextIO

from . import model

_COMMANDS = frozenset({"inspect", "watch", "deliver"})
_DESTINATION_RE = re.compile(r"^[1-9][0-9]{5,19}$")
_PROFILES = ("default", "ragnar", "roshi")


@dataclass(frozen=True, slots=True)
class Dependencies:
    """Lazy factories and deterministic seams for CLI behavior tests."""

    reader_factory: Callable[[], Any]
    evidence_collector: Callable[[], Any]
    store_factory: Callable[[Path], Any]
    transport_factory: Callable[[], Any]
    now: Callable[[], datetime]


class _ArgumentFailure(Exception):
    """Argparse rejected the invocation without retaining user-supplied text."""


class _ParserExit(Exception):
    def __init__(self, status: int) -> None:
        self.status = status


class _SafeParser(argparse.ArgumentParser):
    """Argument parser that returns stable errors instead of echoing raw input."""

    def __init__(self, *args: Any, output: TextIO | None = None, **kwargs: Any) -> None:
        self._output = sys.stdout if output is None else output
        super().__init__(*args, **kwargs)

    def error(self, _message: str) -> None:
        raise _ArgumentFailure

    def print_help(self, file: TextIO | None = None) -> None:
        target = self._output if file is None else file
        target.write(self.format_help())

    def print_usage(self, file: TextIO | None = None) -> None:
        target = self._output if file is None else file
        target.write(self.format_usage())

    def exit(self, status: int = 0, message: str | None = None) -> None:
        if message:
            self._print_message(message)
        raise _ParserExit(status)

    def _print_message(self, message: str, file: TextIO | None = None) -> None:
        target = file or self._output
        if target is not None:
            target.write(message)


def _build_parser(output: TextIO) -> _SafeParser:
    parser = _SafeParser(
        prog="hermes-update-watch",
        description="Observe official stable Hermes releases and manage local notification state.",
        output=output,
    )
    subparsers = parser.add_subparsers(dest="command", required=True, parser_class=_SafeParser)

    inspect_parser = subparsers.add_parser("inspect", help="Read current release metadata without local writes or sends.")
    inspect_parser.add_argument("--state-root", help="Optional existing local state root to read.")

    watch_parser = subparsers.add_parser("watch", help="Record complete discovery results; never sends messages.")
    watch_parser.add_argument("--state-root", required=True, help="Explicit private state root outside the checkout.")
    watch_parser.add_argument("--target", required=True, help="Explicit numeric destination ID for outbox identity.")

    deliver_parser = subparsers.add_parser("deliver", help="Post one existing report after exact operation confirmation.")
    deliver_parser.add_argument("report_id", help="Existing immutable report UUID.")
    deliver_parser.add_argument("--state-root", required=True, help="Existing private state root.")
    deliver_parser.add_argument("--target", required=True, help="Explicit numeric destination ID.")
    deliver_parser.add_argument("--profile", required=True, choices=_PROFILES, help="Explicit ncl-discord profile.")
    deliver_parser.add_argument(
        "--confirm-send",
        help="Exact confirmation: SEND <report-id> TO <target> AS <profile>.",
    )
    return parser


def _default_dependencies() -> Dependencies:
    from .process import run_bounded_process
    from .releases import GitHubReleaseReader
    from .report import collect_environment_evidence
    from .state import StateStore
    from .transport import DiscordTransport

    return Dependencies(
        reader_factory=GitHubReleaseReader,
        evidence_collector=collect_environment_evidence,
        store_factory=StateStore,
        transport_factory=lambda: DiscordTransport(runner=run_bounded_process),
        now=lambda: datetime.now(timezone.utc),
    )


def run_cli(
    argv: Sequence[str] | None = None,
    *,
    dependencies: Dependencies | Any | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """Run one command and emit one bounded JSON result, or offline help."""
    output = sys.stdout if stdout is None else stdout
    args_list = list(sys.argv[1:] if argv is None else argv)
    if args_list and args_list[0] not in _COMMANDS and args_list[0] not in ("-h", "--help"):
        _emit(output, "blocked", "unsupported_operation")
        return 2
    parser = _build_parser(output)
    try:
        args = parser.parse_args(args_list)
    except _ParserExit as exit_request:
        return exit_request.status
    except _ArgumentFailure:
        _emit(output, "blocked", "invalid_invocation")
        return 2
    if dependencies is None:
        dependencies = _default_dependencies()

    if args.command == "inspect":
        return _inspect(args, dependencies, output)
    if args.command == "watch":
        return _watch(args, dependencies, output)
    if args.command == "deliver":
        return _deliver(args, dependencies, output)
    _emit(output, "blocked", "unsupported_operation")
    return 2


def main(argv: Sequence[str] | None = None) -> int:
    """Console entrypoint; no runtime starts unless a command is selected."""
    return run_cli(argv)


def _inspect(args: argparse.Namespace, dependencies: Any, output: TextIO) -> int:
    from . import state
    from .releases import ReleaseError, discover_releases

    try:
        previous = model.DiscoveryState()
        if args.state_root:
            store = dependencies.store_factory(Path(args.state_root))
            try:
                previous = _discovery_state(store.read_state())
            except state.StateError as error:
                if error.reason_code != "store_not_initialized":
                    raise
        result = discover_releases(dependencies.reader_factory(), previous)
    except ReleaseError as error:
        return _emit(output, error.status, error.reason_code, exit_code=3)
    except state.StateError as error:
        return _emit(output, "blocked", error.reason_code, exit_code=5)
    except Exception:
        return _emit(output, "blocked", "release_source_unavailable", exit_code=3)
    candidates = [_release_summary(item) for item in result.candidates]
    return _emit(
        output,
        result.status,
        result.reason_code,
        candidates=candidates,
        candidate_count=len(candidates),
        exit_code=0 if result.status in ("available", "no_change") else _release_failure_exit(result.reason_code),
    )


def _watch(args: argparse.Namespace, dependencies: Any, output: TextIO) -> int:
    from . import report, state
    from .releases import ReleaseError, discover_releases

    if not _valid_destination(args.target):
        return _emit(output, "blocked", "destination_invalid", exit_code=2)
    scan_now = dependencies.now()
    try:
        store = dependencies.store_factory(Path(args.state_root))
        try:
            previous_record = store.read_state()
            previous = _discovery_state(previous_record)
            refresh_ids = _expired_pending_release_ids(previous_record, args.target, scan_now)
            if refresh_ids:
                previous = replace(
                    previous,
                    pending_release_ids=tuple(sorted(set(previous.pending_release_ids) | set(refresh_ids))),
                )
        except state.StateError as error:
            if error.reason_code != "store_not_initialized":
                raise
            previous_record = None
            previous = model.DiscoveryState()
        result = discover_releases(dependencies.reader_factory(), previous)
    except ReleaseError as error:
        return _emit(output, error.status, error.reason_code, exit_code=3)
    except state.StateError as error:
        return _emit(output, "blocked", error.reason_code, exit_code=5)
    except Exception:
        return _emit(output, "blocked", "release_source_unavailable", exit_code=3)

    if result.status not in ("available", "no_change"):
        return _emit(output, result.status, result.reason_code, exit_code=_release_failure_exit(result.reason_code))

    reports: list[dict[str, Any]] = []
    if result.candidates:
        try:
            evidence = dependencies.evidence_collector()
            reports = [
                report.build_report(candidate, evidence, now=scan_now)
                for candidate in result.candidates
            ]
        except (report.ReportValidationError, TypeError, ValueError, OverflowError, RecursionError):
            return _emit(output, "blocked", "report_validation_failed", exit_code=4)
        except Exception:
            return _emit(output, "blocked", "evidence_unavailable", exit_code=4)

    try:
        if previous_record is None:
            previous_record = store.initialize()
        with store.transaction() as transaction:
            if transaction.state != previous_record:
                return _emit(output, "blocked", "state_changed_during_scan", exit_code=5)
            report_ids = transaction.commit_discovery(
                result,
                reports,
                destination_id=args.target,
                now=scan_now,
            )
    except state.StateError as error:
        return _emit(output, "blocked", error.reason_code, exit_code=5)
    return _emit(
        output,
        result.status,
        result.reason_code,
        report_ids=list(report_ids),
        candidate_count=len(result.candidates),
        exit_code=0,
    )


def _deliver(args: argparse.Namespace, dependencies: Any, output: TextIO) -> int:
    from . import report, state, transport

    if not _valid_destination(args.target):
        return _emit(output, "blocked", "destination_invalid", exit_code=2)
    expected_confirmation = f"SEND {args.report_id} TO {args.target} AS {args.profile}"
    if args.confirm_send != expected_confirmation:
        return _emit(output, "blocked", "send_confirmation_required", exit_code=2)

    try:
        store = dependencies.store_factory(Path(args.state_root))
        report_value = store.read_report(args.report_id)
        message = report.render_alert(report_value)
        identity = _release_identity(report_value)
        message_sha256 = hashlib.sha256(message.encode("utf-8")).hexdigest()
    except state.StateError as error:
        return _emit(output, "blocked", error.reason_code, exit_code=5)
    except report.ReportValidationError:
        return _emit(output, "blocked", "report_validation_failed", exit_code=5)
    except (TypeError, ValueError, OverflowError, RecursionError, UnicodeError):
        return _emit(output, "blocked", "report_validation_failed", exit_code=5)

    try:
        with store.transaction() as transaction:
            expected_identity = {
                "repository": identity.repository,
                "release_id": identity.release_id,
                "tag": identity.tag,
                "commit_sha": identity.commit_sha.lower(),
            }
            current_reference = next(
                (
                    record
                    for record in transaction.state["outbox"]
                    if record["destination_id"] == args.target
                    and record["release_identity"] == expected_identity
                ),
                None,
            )
            if current_reference is None or current_reference["report_id"] != args.report_id:
                return _emit(output, "blocked", "report_reference_changed", report_id=args.report_id, exit_code=5)
            intent = transaction.begin_send(identity, args.target, message_sha256, now=dependencies.now())
            try:
                client = dependencies.transport_factory()
            except Exception:
                transaction.abort_send_before_invocation(
                    identity,
                    args.target,
                    intent.attempt_id,
                    "transport_unavailable_before_invocation",
                )
                return _emit(
                    output,
                    "failed_no_send",
                    "transport_unavailable_before_invocation",
                    report_id=args.report_id,
                    exit_code=6,
                )
            try:
                receipt = client.post(intent, message, args.target, args.profile)
            except transport.TransportError as error:
                if error.invoked:
                    transaction.mark_ambiguous(identity, args.target, intent.attempt_id, error.reason_code)
                    return _emit(output, "ambiguous", error.reason_code, report_id=args.report_id, exit_code=6)
                transaction.abort_send_before_invocation(
                    identity,
                    args.target,
                    intent.attempt_id,
                    "transport_unavailable_before_invocation",
                )
                return _emit(
                    output,
                    "failed_no_send",
                    "transport_unavailable_before_invocation",
                    report_id=args.report_id,
                    exit_code=6,
                )
            except Exception:
                transaction.mark_ambiguous(
                    identity,
                    args.target,
                    intent.attempt_id,
                    "transport_output_invalid",
                )
                return _emit(output, "ambiguous", "transport_output_invalid", report_id=args.report_id, exit_code=6)
            transaction.confirm_send(identity, args.target, receipt)
    except state.StateError as error:
        return _emit(output, "blocked", error.reason_code, report_id=args.report_id, exit_code=5)
    return _emit(output, "confirmed", None, report_id=args.report_id, exit_code=0)


def _discovery_state(value: dict[str, Any]) -> model.DiscoveryState:
    identities = tuple(
        (item["release_id"], item["tag"], item["commit_sha"])
        for item in value["identities"]
    )
    bindings = tuple((item["tag"], item["commit_sha"]) for item in value["tag_bindings"])
    return model.DiscoveryState(
        has_completed_scan=value["last_complete_scan"] is not None,
        identities_by_release_id=identities,
        tag_commit_shas=bindings,
        seen_not_notified=tuple(value["seen_not_notified"]),
        pending_release_ids=tuple(value["pending_release_ids"]),
    )


def _release_summary(value: model.ReleaseIdentity) -> dict[str, Any]:
    return {
        "release_id": value.release_id,
        "tag": value.tag,
        "tag_sha": value.tag_sha,
        "commit_sha": value.commit_sha,
        "published_at": value.published_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


def _release_identity(value: dict[str, Any]) -> model.ReleaseIdentity:
    source = value["source"]
    timestamp = datetime.fromisoformat(source["published_at"].replace("Z", "+00:00"))
    if timestamp.tzinfo is None:
        raise ValueError
    return model.ReleaseIdentity(
        release_id=source["release_id"],
        tag=source["tag"],
        published_at=timestamp.astimezone(timezone.utc),
        tag_sha=source["tag_sha"],
        commit_sha=source["commit_sha"],
        repository=source["repository"],
    )


def _valid_destination(value: Any) -> bool:
    return type(value) is str and _DESTINATION_RE.fullmatch(value) is not None


def _expired_pending_release_ids(state_value: dict[str, Any], destination_id: str, now: datetime) -> tuple[int, ...]:
    """Select only expired, never-attempted pending identities for bounded revalidation."""
    from .state import StateError

    if (
        not isinstance(now, datetime)
        or now.tzinfo is None
        or now.utcoffset() != timezone.utc.utcoffset(now)
    ):
        raise StateError("invalid_timestamp")
    now_text = now.astimezone(timezone.utc).replace(microsecond=0).isoformat(timespec="seconds").replace("+00:00", "Z")
    return tuple(
        record["release_identity"]["release_id"]
        for record in state_value["outbox"]
        if record["destination_id"] == destination_id
        and record["state"] == "pending"
        and record["attempt_id"] is None
        and record["expires_at"] <= now_text
    )


def _release_failure_exit(reason_code: str | None) -> int:
    if reason_code in {
        "timeout",
        "rate_limited",
        "http_error",
        "network_unavailable",
        "request_failed",
        "upstream_unavailable",
        "upstream_rate_limited",
    }:
        return 3
    return 4


def _emit(
    output: TextIO,
    status: str,
    reason_code: str | None = None,
    *,
    exit_code: int = 2,
    **fields: Any,
) -> int:
    result: dict[str, Any] = {"status": status}
    if reason_code is not None:
        result["reason_code"] = reason_code
    result.update(fields)
    try:
        encoded = json.dumps(result, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError, OverflowError, RecursionError):
        encoded = '{"reason_code":"output_invalid","status":"blocked"}'
        exit_code = 5
    output.write(encoded + "\n")
    return exit_code
