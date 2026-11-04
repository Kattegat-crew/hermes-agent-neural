#!/usr/bin/env bash
# ============================================================================
# F3 · activación del gate de autoskills
# ----------------------------------------------------------------------------
# Los hooks declarativos se registran al ARRANCAR el gateway, así que el gate
# no está operativo hasta reiniciar los servicios. Este script reinicia
# únicamente los servicios de gateway que están UP (no arranca los inactivos,
# para no cambiar la línea base de la flota) y deja la evidencia en un log.
# ============================================================================
set -uo pipefail
LOG=/root/hermes-agent-legacy-docker/data/state/f3_restart.log
S6=/package/admin/s6/command/s6-svc
S6STAT=/package/admin/s6/command/s6-svstat

{
  echo "=== F3 · activacion del gate de autoskills: reinicio de gateways $(date) ==="
  echo "--- servicios declarados ---"
  docker exec hermes-agent sh -c 'ls -d /run/service/gateway-*/ | wc -l'
  echo "--- reinicio de los que estan UP ---"
  docker exec hermes-agent sh -c "
    for s in /run/service/gateway-*/; do
      st=\$($S6STAT \"\$s\" 2>/dev/null || echo down)
      case \"\$st\" in
        up*) echo \"  restart \$s  [\$st]\"; $S6 -r \"\$s\" ;;
        *)   echo \"  skip    \$s  [\$st]\" ;;
      esac
    done"
  echo "--- esperando arranque (30s) ---"
  sleep 30
  echo "--- procesos 'gateway run' vivos ---"
  docker exec hermes-agent sh -c 'ps -ef 2>/dev/null | grep -c "[g]ateway run"'
  echo "--- logs de gateway frescos ---"
  for d in /opt/data/logs/gateways/*/; do
    n=$(basename "$d")
    printf "  %-12s %s B\n" "$n" "$(stat -c %s "$d/current" 2>/dev/null || echo 0)"
  done
  echo "--- hooks list (perfil default) ---"
  docker exec -u 10000 -e HERMES_HOME=/opt/data hermes-agent \
    /opt/hermes/.venv/bin/hermes hooks list 2>&1 | tail -4
  echo "--- hooks doctor (perfil default) ---"
  docker exec -u 10000 -e HERMES_HOME=/opt/data hermes-agent \
    /opt/hermes/.venv/bin/hermes hooks doctor 2>&1 | tail -8
  echo "--- hooks doctor (perfil roshi) ---"
  docker exec -u 10000 -e HERMES_HOME=/opt/data/profiles/roshi hermes-agent \
    /opt/hermes/.venv/bin/hermes hooks doctor 2>&1 | tail -6
  echo "=== fin $(date) ==="
} >> "$LOG" 2>&1
