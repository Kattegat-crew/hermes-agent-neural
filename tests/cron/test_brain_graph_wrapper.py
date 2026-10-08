"""Offline contract tests for the versioned brain-graph cron wrapper."""

from __future__ import annotations

import os
import signal
import subprocess
import time
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
WRAPPER = REPO_ROOT / "scripts" / "brain_graph_update_wrapper.sh"


def _write_inner(path: Path, body: str) -> Path:
    path.write_text("#!/usr/bin/env bash\n" + body)
    return path


def _env(tmp_path: Path, inner: Path, **values: str) -> dict[str, str]:
    env = os.environ.copy()
    env.update({"BRAIN_GRAPH_INNER": str(inner), "TMPDIR": str(tmp_path)})
    env.update(values)
    return env


def _run(tmp_path: Path, inner: Path, **values: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(WRAPPER)],
        env=_env(tmp_path, inner, **values),
        capture_output=True,
        text=True,
        check=False,
        timeout=5,
    )


def _combined(result: subprocess.CompletedProcess[str]) -> str:
    return result.stdout + result.stderr


def _pid_is_running(pid: int) -> bool:
    stat_path = Path(f"/proc/{pid}/stat")
    try:
        state = stat_path.read_text().rsplit(")", 1)[1].split()[0]
    except FileNotFoundError:
        return False
    return state != "Z"


def test_preserves_nonzero_inner_exit_without_leaking_payload(tmp_path: Path) -> None:
    secretish = "private-graph-error-payload-7f2c"
    inner = _write_inner(tmp_path / "inner.sh", f"printf '%s\\n' '{secretish}' >&2\nexit 7\n")

    result = _run(tmp_path, inner)

    assert result.returncode == 7
    assert "inner_rc=7" in _combined(result)
    assert secretish not in _combined(result)
    assert list(tmp_path.glob("brain-graph-cron.*")) == []


def test_extract_error_fails_even_when_inner_returns_zero_and_hides_payload(tmp_path: Path) -> None:
    secretish = "EXTRACT_ERROR: private api key details must not be printed"
    inner = _write_inner(tmp_path / "inner.sh", f"printf '%s\\n' '{secretish}'\nexit 0\n")

    result = _run(tmp_path, inner)

    assert result.returncode != 0
    assert "reason=extract_error" in _combined(result)
    assert secretish not in _combined(result)
    assert list(tmp_path.glob("brain-graph-cron.*")) == []


def test_success_reports_only_process_completion_and_no_change_summary(tmp_path: Path) -> None:
    inner = _write_inner(
        tmp_path / "inner.sh",
        "printf '%s\\n' '[brain-graph] sin cambios: 0 notas nuevas' 'nodes before=6 after=6'\nexit 0\n",
    )

    result = _run(tmp_path, inner)

    assert result.returncode == 0
    assert "status=no_changes" in _combined(result)
    assert "delivery" not in _combined(result).lower()
    assert "nodes before" not in _combined(result)
    assert list(tmp_path.glob("brain-graph-cron.*")) == []


def test_empty_success_output_is_not_claimed_as_freshness_or_delivery(tmp_path: Path) -> None:
    inner = _write_inner(tmp_path / "inner.sh", "exit 0\n")

    result = _run(tmp_path, inner)

    assert result.returncode == 0
    assert "status=process_complete" in _combined(result)
    assert "fresh" not in _combined(result).lower()
    assert "delivery" not in _combined(result).lower()


def test_missing_inner_fails_with_bounded_status_without_path_leak(tmp_path: Path) -> None:
    missing = tmp_path / "sensitive-parent-name" / "missing-inner.sh"

    result = _run(tmp_path, missing)

    assert result.returncode != 0
    assert "reason=inner_unavailable" in _combined(result)
    assert str(missing) not in _combined(result)


def test_preserves_caller_home_full_and_tmpdir(tmp_path: Path) -> None:
    capture = tmp_path / "environment.txt"
    caller_home = tmp_path / "caller-home"
    inner = _write_inner(
        tmp_path / "inner.sh",
        'printf "%s\\n%s\\n%s\\n" "$HOME" "$FULL" "$TMPDIR" > "$ENV_CAPTURE"\nexit 0\n',
    )

    result = _run(tmp_path, inner, HOME=str(caller_home), FULL="1", ENV_CAPTURE=str(capture))

    assert result.returncode == 0
    assert capture.read_text().splitlines() == [str(caller_home), "1", str(tmp_path)]


def test_concurrent_runs_use_distinct_private_directories_and_cleanup(tmp_path: Path) -> None:
    observations = tmp_path / "run-observations.txt"
    ready = tmp_path / "run-ready.txt"
    inner = _write_inner(
        tmp_path / "inner.sh",
        r'''
shopt -s nullglob
deadline=$((SECONDS + 3))
while :; do
  runs=("$TMPDIR"/brain-graph-cron.*)
  [ "${#runs[@]}" -ge 2 ] && break
  (( SECONDS < deadline )) || exit 11
  sleep 0.02
done
for run_dir in "${runs[@]}"; do
  printf "%s %s %s\n" "${#runs[@]}" "$(stat -c '%a' "$run_dir")" "$(stat -c '%a' "$run_dir/inner.log")" >> "$OBSERVATIONS"
done
printf "%s\n" "$BASHPID" >> "$READY_FILE"
deadline=$((SECONDS + 3))
while :; do
  mapfile -t ready_runs < "$READY_FILE"
  [ "${#ready_runs[@]}" -ge 2 ] && break
  (( SECONDS < deadline )) || exit 12
  sleep 0.02
done
exit 0
''' ,
    )
    env = _env(tmp_path, inner, OBSERVATIONS=str(observations), READY_FILE=str(ready))
    first = subprocess.Popen(["bash", str(WRAPPER)], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    second = subprocess.Popen(["bash", str(WRAPPER)], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    first_output = first.communicate(timeout=6)
    second_output = second.communicate(timeout=6)

    assert first.returncode == 0, first_output
    assert second.returncode == 0, second_output
    observed = [line.split() for line in observations.read_text().splitlines()]
    assert len(observed) == 4
    assert all(int(count) == 2 for count, _dir_mode, _log_mode in observed)
    assert all(dir_mode == "700" for _count, dir_mode, _log_mode in observed)
    assert all(log_mode == "600" for _count, _dir_mode, log_mode in observed)
    assert len(ready.read_text().splitlines()) == 2
    assert list(tmp_path.glob("brain-graph-cron.*")) == []

def _kill_fixture_process_group(pid_file: Path) -> None:
    if not pid_file.exists():
        return
    for value in pid_file.read_text().splitlines():
        try:
            os.killpg(os.getpgid(int(value)), signal.SIGKILL)
        except ProcessLookupError:
            pass


def test_signal_stops_term_resistant_child_tree_and_cleans_private_log_dir(
    tmp_path: Path,
) -> None:
    pid_file = tmp_path / "inner-pids"
    inner = _write_inner(
        tmp_path / "inner.sh",
        r'''
trap '' TERM
printf "%s\n" "$BASHPID" >> "$INNER_PIDS"
(
  trap '' TERM
  printf "%s\n" "$BASHPID" >> "$INNER_PIDS"
  exec sleep 30
) &
wait "$!"
''' ,
    )
    proc = subprocess.Popen(
        ["bash", str(WRAPPER)],
        env=_env(tmp_path, inner, INNER_PIDS=str(pid_file)),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    deadline = time.monotonic() + 3
    while (not pid_file.exists() or len(pid_file.read_text().splitlines()) < 2) and proc.poll() is None:
        if time.monotonic() >= deadline:
            proc.kill()
            _kill_fixture_process_group(pid_file)
            pytest.fail("wrapper did not start the TERM-resistant inner tree")
        time.sleep(0.02)

    try:
        assert proc.poll() is None, "wrapper exited before signal handling"
        child_pids = [int(value) for value in pid_file.read_text().splitlines()]
        started = time.monotonic()
        proc.terminate()
        try:
            output = proc.communicate(timeout=4)
        except subprocess.TimeoutExpired:
            _kill_fixture_process_group(pid_file)
            proc.kill()
            proc.communicate(timeout=2)
            pytest.fail("wrapper signal cleanup exceeded the bounded grace")
        elapsed = time.monotonic() - started

        assert proc.returncode == 143, output
        assert elapsed < 4
        deadline = time.monotonic() + 2
        while any(_pid_is_running(pid) for pid in child_pids) and time.monotonic() < deadline:
            time.sleep(0.02)
        assert all(not _pid_is_running(pid) for pid in child_pids)
        assert list(tmp_path.glob("brain-graph-cron.*")) == []
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=2)
        _kill_fixture_process_group(pid_file)
