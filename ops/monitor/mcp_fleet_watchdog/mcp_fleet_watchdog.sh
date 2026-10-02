#!/bin/bash
# mcp_fleet_watchdog.sh — envoltorio del watchdog de la flota MCP.
# Elegimos el primer intérprete que tenga mcp+yaml (el runtime root del Desktop no los
# ve, así que no basta con `python3`). Silencioso si todo está sano.
set -u
PY=""
for c in /opt/hermes-agent/.venv/bin/python3 python3 /usr/bin/python3; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c "import mcp, yaml" 2>/dev/null; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then
  echo "mcp-fleet-watchdog: ningún intérprete con 'mcp'+'yaml' — revisar el runtime (el watchdog no pudo correr)"
  exit 0
fi
[ -d /opt/hermes-agent-data/state ] || mkdir -p /opt/hermes-agent-data/state 2>/dev/null
exec "$PY" /opt/hermes-agent-data/scripts/mcp_fleet_probe.py "$@"
