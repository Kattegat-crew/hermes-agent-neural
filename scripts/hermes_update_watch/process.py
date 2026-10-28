"""Bounded, shell-free subprocess execution for the update watcher."""

from __future__ import annotations

import math
import os
import selectors
import subprocess
import time
from dataclasses import dataclass
from typing import Mapping, Sequence


@dataclass(frozen=True, slots=True)
class BoundedProcessResult:
    """A bounded child result with a stable failure code and no exception text."""

    returncode: int | None
    stdout: bytes
    stderr: bytes
    reason_code: str | None = None


def run_bounded_process(
    argv: Sequence[str],
    *,
    env: Mapping[str, str],
    timeout_seconds: float,
    stdout_limit: int,
    stderr_limit: int,
) -> BoundedProcessResult:
    """Run a process with bounded pipe reads, no shell, and an absolute deadline."""
    if (
        not isinstance(argv, (tuple, list))
        or not argv
        or any(not isinstance(arg, str) or not arg or "\x00" in arg for arg in argv)
        or not isinstance(env, Mapping)
        or any(
            not isinstance(key, str)
            or not key
            or "=" in key
            or "\x00" in key
            or not isinstance(value, str)
            or "\x00" in value
            for key, value in env.items()
        )
        or isinstance(timeout_seconds, bool)
        or not isinstance(timeout_seconds, (int, float))
        or not math.isfinite(timeout_seconds)
        or timeout_seconds <= 0
        or type(stdout_limit) is not int
        or type(stderr_limit) is not int
        or stdout_limit < 0
        or stderr_limit < 0
    ):
        return BoundedProcessResult(None, b"", b"", "invalid_process_request")

    try:
        child = subprocess.Popen(
            tuple(argv),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            close_fds=True,
            env=dict(env),
            bufsize=0,
        )
    except (OSError, ValueError):
        return BoundedProcessResult(None, b"", b"", "process_unavailable")

    assert child.stdout is not None and child.stderr is not None
    streams = {
        child.stdout.fileno(): (child.stdout, bytearray(), stdout_limit, "stdout_limit_exceeded"),
        child.stderr.fileno(): (child.stderr, bytearray(), stderr_limit, "stderr_limit_exceeded"),
    }
    selector = selectors.DefaultSelector()
    for fd, (stream, _buffer, _limit, _reason) in streams.items():
        os.set_blocking(fd, False)
        selector.register(stream, selectors.EVENT_READ, fd)

    deadline = time.monotonic() + float(timeout_seconds)
    failure: str | None = None
    try:
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                failure = "timeout"
                break
            events = selector.select(remaining)
            if not events:
                failure = "timeout"
                break
            for key, _mask in events:
                fd = key.data
                _stream, buffer, limit, cap_reason = streams[fd]
                try:
                    chunk = os.read(fd, min(65_536, max(1, limit + 1 - len(buffer))))
                except BlockingIOError:
                    continue
                except OSError:
                    failure = "process_unavailable"
                    break
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                if len(buffer) + len(chunk) > limit:
                    failure = cap_reason
                    break
                buffer.extend(chunk)
            if failure is not None:
                break

        if failure is not None:
            _terminate_and_reap(child)
            return BoundedProcessResult(None, b"", b"", failure)

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            _terminate_and_reap(child)
            return BoundedProcessResult(None, b"", b"", "timeout")
        try:
            returncode = child.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            _terminate_and_reap(child)
            return BoundedProcessResult(None, b"", b"", "timeout")
        return BoundedProcessResult(
            returncode,
            bytes(streams[child.stdout.fileno()][1]),
            bytes(streams[child.stderr.fileno()][1]),
            None,
        )
    finally:
        selector.close()
        child.stdout.close()
        child.stderr.close()


def _terminate_and_reap(child: subprocess.Popen[bytes]) -> None:
    """Stop a child promptly, escalating only if graceful termination stalls."""
    if child.poll() is not None:
        return
    try:
        child.terminate()
        child.wait(timeout=0.25)
    except subprocess.TimeoutExpired:
        child.kill()
        child.wait()
    except OSError:
        try:
            child.kill()
        except OSError:
            pass
        child.wait()
