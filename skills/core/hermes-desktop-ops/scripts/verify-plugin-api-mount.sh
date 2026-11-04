#!/bin/bash
# Verifica el montaje de la mitad Python de un plugin de Hermes Desktop SIN tocar
# los servicios vivos: levanta un dashboard DESECHABLE (puerto aparte, token
# propio), prueba /api/plugins/<id>/…, corre los controles negativos y lo mata.
#
#   bash verify-plugin-api-mount.sh <id> [puerto] [ruta_endpoint]
# Ej.: bash verify-plugin-api-mount.sh nan-usage 9123 /summary
#
# Nunca usar el puerto ni el token de los servicios en uso (9112 / gateway del
# Desktop). Este script crea su propia instancia y la termina al salir.
set -u
export HERMES_HOME="${HERMES_HOME:-/root/hermes-agent-legacy-docker/data}"
export HERMES_DASHBOARD=1                       # dashboard: no arranca el ticker de cron
export HERMES_DASHBOARD_SESSION_TOKEN="verify-$$
"
ID="${1:?falta el id del plugin}"
PORT="${2:-9123}"
EP="${3:-/summary}"
LOG="/tmp/verify-plugin-${ID}.log"
BIN="${HERMES_BIN:-/opt/hermes-venv/bin/hermes}"

"$BIN" dashboard --host 127.0.0.1 --port "$PORT" --skip-build --no-open >"$LOG" 2>&1 &
PID=$!
echo "instancia de prueba PID=$PID puerto=$PORT (log: $LOG)"

code=000
for i in $(seq 1 40); do
  code=$(curl -s -o /dev/null -m 3 -w '%{http_code}' "http://127.0.0.1:$PORT/" 2>/dev/null || true)
  [ "$code" != "000" ] && [ -n "$code" ] && break
  sleep 1
done
echo "readiness: $code tras ${i}s   (la línea HERMES_DASHBOARD_READY del log es la prueba)"

T="X-Hermes-Session-Token: ${HERMES_DASHBOARD_SESSION_TOKEN%$'\n'}"
B="http://127.0.0.1:$PORT/api/plugins/$ID"
echo "--- GET $EP (con token) ---"
curl -s -m 40 -H "$T" "$B$EP" | head -c 900; echo
echo "--- controles negativos ---"
printf 'plugin inexistente -> '; curl -s -o /dev/null -m 10 -w '%{http_code}\n' -H "$T" "http://127.0.0.1:$PORT/api/plugins/no-existe$EP"
printf 'sin token            -> '; curl -s -o /dev/null -m 10 -w '%{http_code}\n' "$B$EP"

echo "--- líneas de montaje en el log ---"
grep -iE "Mounted plugin API routes|Failed to load plugin|declares api=" "$LOG" | head -5

kill "$PID" 2>/dev/null; sleep 1; kill -9 "$PID" 2>/dev/null
echo "instancia de prueba terminada"
