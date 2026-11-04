#!/usr/bin/env bash
# Versioned, offline-testable wrapper for the native brain-graph cron job.
# BRAIN_GRAPH_INNER is an operator/test seam; production defaults to the existing
# runtime inner script. This wrapper reports process outcome, not artifact freshness
# or downstream delivery.
set -um
set -m
umask 077

INNER="${BRAIN_GRAPH_INNER:-/opt/hermes-agent-data/scripts/brain_graph_update_inner.sh}"
FULL="${FULL:-0}"
export FULL
TMP_ROOT="${TMPDIR:-/tmp}"
export TMPDIR="${TMPDIR:-/tmp}"
RUN_DIR=''
INNER_PID=''

stop_inner_group() {
    local pid="$INNER_PID"
    [[ -n "$pid" ]] || return 0

    kill -TERM -- "-$pid" >/dev/null 2>&1 || true
    local deadline=$((SECONDS + 1))
    while kill -0 -- "-$pid" >/dev/null 2>&1; do
        if (( SECONDS >= deadline )); then
            kill -KILL -- "-$pid" >/dev/null 2>&1 || true
            break
        fi
        sleep 0.05 || true
    done
    wait "$pid" >/dev/null 2>&1 || true
    INNER_PID=''
}

cleanup() {
    local exit_status=$?
    trap - EXIT HUP INT TERM
    stop_inner_group
    if [[ -n "$RUN_DIR" && -d "$RUN_DIR" ]]; then
        rm -rf -- "$RUN_DIR" >/dev/null 2>&1 || true
    fi
    return "$exit_status"
}

handle_signal() {
    local exit_status="$1"
    stop_inner_group
    exit "$exit_status"
}

trap cleanup EXIT
trap 'handle_signal 129' HUP
trap 'handle_signal 130' INT
trap 'handle_signal 143' TERM

if [[ ! -f "$INNER" || ! -r "$INNER" ]]; then
    printf '%s\n' '[brain-graph] failed reason=inner_unavailable' >&2
    exit 127
fi
if ! command -v timeout >/dev/null 2>&1; then
    printf '%s\n' '[brain-graph] failed reason=timeout_unavailable' >&2
    exit 127
fi

if ! RUN_DIR="$(mktemp -d -- "${TMP_ROOT%/}/brain-graph-cron.XXXXXX" 2>/dev/null)"; then
    printf '%s\n' '[brain-graph] failed reason=private_log_unavailable' >&2
    exit 1
fi
RUN_LOG="$RUN_DIR/inner.log"
if ! : > "$RUN_LOG" 2>/dev/null; then
    printf '%s\n' '[brain-graph] failed reason=private_log_unavailable' >&2
    exit 1
fi

# Keep the 55-minute guard and run as the current caller. The deployment identity
# is managed separately; this script never changes ownership, mode, or user.
timeout --kill-after=5s 3300 bash "$INNER" > "$RUN_LOG" 2>&1 &
INNER_PID=$!
wait "$INNER_PID"
INNER_RC=$?
INNER_PID=''

# Consume only bounded status markers; never echo the inner log or its error payload.
if grep -qF 'EXTRACT_ERROR' "$RUN_LOG"; then
    printf '[brain-graph] failed reason=extract_error inner_rc=%s\n' "$INNER_RC" >&2
    if [[ "$INNER_RC" -eq 0 ]]; then
        exit 1
    fi
    exit "$INNER_RC"
fi
if [[ "$INNER_RC" -ne 0 ]]; then
    printf '[brain-graph] failed reason=inner_exit inner_rc=%s\n' "$INNER_RC" >&2
    exit "$INNER_RC"
fi
if grep -qF 'sin cambios:' "$RUN_LOG"; then
    printf '%s\n' '[brain-graph] complete status=no_changes inner_rc=0'
else
    printf '%s\n' '[brain-graph] complete status=process_complete inner_rc=0'
fi
