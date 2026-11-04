#!/bin/bash
# Diagnóstico rápido del backend SSH de Hermes Desktop en un VPS.
# Uso: ./hermes-desktop-ssh-diagnose.sh [host]  (host por defecto: primer argumento del listado hence)
# Provee las 4 capas de diagnóstico; redacta secretos en la salida.
set -euo pipefail

HOST="${1:-}"
[ -n "$HOST" ] || HOST="$(grep -m1 -A1 'Host 147.93\|HostName 147.93' ~/.ssh/config 2>/dev/null | awk '{print $NF}' | head -1)"
[ -n "$HOST" ] || { echo "Uso: $0 <host>"; exit 1; }

echo "== 1) Binario remoto y flags SSH =="
ssh -o ConnectTimeout=15 "$HOST" '
  BIN=$(command -v hermes)
  echo "binario: $BIN"
  echo -n "flags_ssh_soportados: "
  help="$($BIN serve --help 2>&1)"
  { printf "%s" "$help" | grep -q ssh-session-token-file && printf "%s" "$help" | grep -q ssh-owner-nonce; } && echo YES || echo NO
  "$BIN" --version 2>&1 | head -1
'

echo ""
echo "== 2) HERMES_HOME efectivo + dónde viven los datos =="
ssh "$HOST" '
  echo "HERMES_HOME_efectivo: ${HERMES_HOME:-$HOME/.hermes}"
  for h in "$HOME/.hermes" /root/hermes-agent-legacy-docker/data; do
    if [ -f "$h/state.db" ]; then printf "%s state.db = %s bytes, profiles=%s\n" "$h" "$(stat -c %s "$h/state.db")" "$(ls "$h/profiles" 2>/dev/null | tr "\n" " ")"; else echo "$h: sin state.db"; fi
  done
'

echo ""
echo "== 3) Inferencia (provider/key) del home activo =="
ssh "$HOST" '
  H="${HERMES_HOME:-$HOME/.hermes}"
  if [ -f "$H/config.yaml" ]; then
    grep -E "base_url|default:|provider:" "$H/config.yaml" | head -6
  fi
'

echo ""
echo "== 4) Dashboards SSH stale + locks =="
ssh "$HOST" '
  ps aux | grep "serve --isolated.*ssh-session-token-file" | grep -v grep | awk "{print \$2, \$11, \$12}" || echo "  ninguno"
  [ -d "$HOME/.hermes/desktop-ssh" ] && ls "$HOME/.hermes/desktop-ssh" 2>/dev/null || echo "  sin directorio desktop-ssh"
'