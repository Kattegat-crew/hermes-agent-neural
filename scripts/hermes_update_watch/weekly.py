"""Fixed-target weekly runner for complete discovery and pending delivery recovery."""

from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
from io import StringIO
from pathlib import Path
from typing import Any, Sequence, TextIO

from . import model

AUTHORIZED_TARGET = "1493432785245962250"
AUTHORIZED_PROFILE = "roshi"
MAX_WEEKLY_DELIVERIES = model.MAX_CANDIDATES
_CLI_OUTPUT_LIMIT = 8 * 1024
_REASON_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


class _InvalidArguments(Exception):
    """Argparse rejected input without retaining user text."""


class _ParserExit(Exception):
    def __init__(self, status: int) -> None:
        self.status = status


class _SafeParser(argparse.ArgumentParser):
    """Parser that writes help to the selected stream and sanitizes errors."""

    def __init__(self, *args: Any, output: TextIO, **kwargs: Any) -> None:
        self._output = output
        super().__init__(*args, **kwargs)

    def error(self, _message: str) -> None:
        raise _InvalidArguments

    def print_help(self, file: TextIO | None = None) -> None:
        (self._output if file is None else file).write(self.format_help())

    def print_usage(self, file: TextIO | None = None) -> None:
        (self._output if file is None else file).write(self.format_usage())

    def exit(self, status: int = 0, message: str | None = None) -> None:
        if message:
            self._output.write(message)
        raise _ParserExit(status)


def run_weekly(
    argv: Sequence[str] | None = None,
    *,
    dependencies: Any | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """Run one fixed-target weekly watch and bounded pending-delivery batch."""
    del stderr  # All user-facing output is one bounded JSON line on stdout.
    output = sys.stdout if stdout is None else stdout
    parser = _SafeParser(
        prog="hermes-update-watch-weekly",
        description="Run one bounded weekly Hermes release watch and notification batch.",
        output=output,
    )
    parser.add_argument("--state-root", required=True, help="Explicit private state root outside the checkout.")
    parser.add_argument("--target", required=True, help="Authorized numeric Discord DM destination.")
    parser.add_argument("--profile", required=True, help="Authorized ncl-discord sender profile.")
    try:
        args = parser.parse_args(list(sys.argv[1:] if argv is None else argv))
    except _ParserExit as exit_request:
        return exit_request.status
    except _InvalidArguments:
        return _emit(output, "blocked", "invalid_invocation", exit_code=2)

    if args.target != AUTHORIZED_TARGET or args.profile != AUTHORIZED_PROFILE:
        return _emit(output, "blocked", "target_profile_not_authorized", exit_code=2)

    from . import cli, state

    watch_output = StringIO()
    try:
        watch_code = cli.run_cli(
            ["watch", "--state-root", args.state_root, "--target", AUTHORIZED_TARGET],
            dependencies=dependencies,
            stdout=watch_output,
            stderr=StringIO(),
        )
        watch_result = _parse_cli_output(watch_output.getvalue())
    except Exception:
        return _emit(output, "blocked", "weekly_watch_failed", exit_code=3)
    if watch_result is None:
        return _emit(output, "blocked", "weekly_watch_output_invalid", exit_code=4)
    if watch_code != 0:
        return _emit(
            output,
            "blocked",
            _safe_reason(watch_result.get("reason_code"), "weekly_watch_failed"),
            exit_code=watch_code,
        )
    if watch_result.get("status") not in {"available", "no_change"}:
        return _emit(output, "blocked", "weekly_watch_incomplete", exit_code=4)

    try:
        pending_ids = state.StateStore(Path(args.state_root)).pending_report_ids(
            AUTHORIZED_TARGET,
            now=dependencies.now() if dependencies is not None else None,
            limit=MAX_WEEKLY_DELIVERIES,
        )
    except state.StateError as error:
        return _emit(output, "blocked", error.reason_code, exit_code=5)
    except Exception:
        return _emit(output, "blocked", "state_unavailable", exit_code=5)

    delivered = 0
    for report_id in pending_ids:
        if not _valid_report_id(report_id):
            return _emit(output, "blocked", "pending_state_invalid", report_id=report_id, exit_code=5)
        confirmation = f"SEND {report_id} TO {AUTHORIZED_TARGET} AS {AUTHORIZED_PROFILE}"
        delivery_output = StringIO()
        try:
            delivery_code = cli.run_cli(
                [
                    "deliver",
                    report_id,
                    "--state-root",
                    args.state_root,
                    "--target",
                    AUTHORIZED_TARGET,
                    "--profile",
                    AUTHORIZED_PROFILE,
                    "--confirm-send",
                    confirmation,
                ],
                dependencies=dependencies,
                stdout=delivery_output,
                stderr=StringIO(),
            )
            delivery_result = _parse_cli_output(delivery_output.getvalue())
        except Exception:
            delivery_code = 6
            delivery_result = None
        if delivery_result is None:
            return _emit(
                output,
                "partial" if delivered else "ambiguous",
                "weekly_delivery_output_invalid",
                delivered_count=delivered,
                remaining_count=len(pending_ids) - delivered,
                exit_code=delivery_code if delivery_code else 6,
            )
        if delivery_code != 0 or delivery_result.get("status") != "confirmed":
            reason_code = _safe_reason(delivery_result.get("reason_code"), "weekly_delivery_failed")
            status = "partial" if delivered else _safe_delivery_status(delivery_result.get("status"))
            return _emit(
                output,
                status,
                reason_code,
                delivered_count=delivered,
                remaining_count=len(pending_ids) - delivered,
                exit_code=delivery_code if delivery_code else 6,
            )
        delivered += 1

    return _emit(
        output,
        "completed",
        delivered_count=delivered,
        batch_limit=MAX_WEEKLY_DELIVERIES,
        exit_code=0,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Console entrypoint for the scheduled weekly driver."""
    return run_weekly(argv)


def _parse_cli_output(value: str) -> dict[str, Any] | None:
    if len(value.encode("utf-8", errors="replace")) > _CLI_OUTPUT_LIMIT:
        return None
    try:
        result = json.loads(value)
    except (TypeError, ValueError, RecursionError):
        return None
    return result if type(result) is dict else None


def _valid_report_id(value: Any) -> bool:
    if type(value) is not str:
        return False
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError):
        return False
    return str(parsed) == value and parsed.version == 4 and parsed.variant == uuid.RFC_4122


def _safe_reason(value: Any, fallback: str) -> str:
    return value if type(value) is str and _REASON_RE.fullmatch(value) else fallback


def _safe_delivery_status(value: Any) -> str:
    if value in {"ambiguous", "failed_no_send", "blocked", "partial"}:
        return value
    return "blocked"


def _emit(
    output: TextIO,
    status: str,
    reason_code: str | None = None,
    *,
    exit_code: int,
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
