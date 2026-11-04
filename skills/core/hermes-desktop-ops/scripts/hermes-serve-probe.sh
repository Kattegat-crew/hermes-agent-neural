#!/bin/bash
# hermes-serve-probe.sh — liveness + state.db probe for a Hermes serve (9112) backend.
# Run from INSIDE the Hermes container with host nsenter access (see devops/vps-host-access).
# Adjust PID/service name if the serve process differs.
#
# Usage: bash hermes-serve-probe.sh [host-ip-or-127.0.0.1]
# Exits 0 if the backend is up and serving; non-zero otherwise.
set -e
HOSTIP="${1:-127.0.0.1}"
SERVE_PORT="${SERVE_PORT:-9112}"

echo "=== who is serving :$SERVE_PORT ==="
nsenter_cmd() {
  docker run --rm --pid=host --privileged alpine sh -c "nsenter -t 1 -m -u -n -i sh -c \"$1\""
}

nsenter_cmd "systemctl is-active hermes-serve 2>/dev/null; netstat -tlnp 2>/dev/null | grep $SERVE_PORT" || true

echo ""
echo "=== serve HERMES_HOME (verify it matches the gateway -> shared state.db) ==="
for pid in $(nsenter_cmd "ps -eo pid,cmd | grep 'hermes serve' | head -1" 2>/dev/null | awk '{print $1}'); do
  nsenter_cmd "cat /proc/${pid}/environ 2>/dev/null | tr '\\0' '\\n' | grep -iE 'HERMES_HOME'"
done

echo ""
echo "=== unauthenticated healthy-signature probes ==="
curl -s -o /dev/null -w "/health        -> %{http_code}\n" "http://${HOSTIP}:${SERVE_PORT}/health"
curl -s "http://${HOSTIP}:${SERVE_PORT}/api/sessions" | head -c 160
echo " <- 401 no_cookie is HEALTHY"

echo ""
echo "=== state.db on shared home ==="
HERMES_HOME_VAL="$(nsenter_cmd "cat /proc/\$(nsenter_cmd 'ps -eo pid,cmd | grep hermes serve | head -1' 2>/dev/null | awk '{print \$1}')/environ 2>/dev/null | tr '\\0' '\\n' | grep '^HERMES_HOME=' | cut -d= -f2" 2>/dev/null)"
if [ -n "$HERMES_HOME_VAL" ]; then
  nsenter_cmd "ls -la ${HERMES_HOME_VAL}/state.db; sqlite3 ${HERMES_HOME_VAL}/state.db \"select count(*) from sessions;\" 2>/dev/null || echo 'sqlite3 not on host'"
fi
echo ""
echo "If you see 200 + 401(no_cookie) + a populated state.db, the backend IS healthy:"
echo "the next step is client-side (Desktop >> Sign out & sign in), not a server fix."