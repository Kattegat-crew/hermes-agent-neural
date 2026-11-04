#!/usr/bin/env bash
# Reinicia el slot vigia (quedó arrancado con el config por defecto tras el
# incidente del YAML) y reporta el estado de la flota de slots.
set -uo pipefail
S6STAT=/package/admin/s6/command/s6-svstat
S6=/package/admin/s6/command/s6-svc

echo "=== antes ==="
for d in /run/service/gateway-*/; do
  n=$(basename "$d")
  printf '  %-18s %s\n' "$n" "$($S6STAT "$d" 2>/dev/null)"
done

echo
echo "=== reinicio del slot vigia ==="
if $S6 -r /run/service/gateway-vigia; then echo "  reinicio enviado"; else echo "  fallo el reinicio"; fi

sleep 30

echo
echo "=== despues ==="
for d in /run/service/gateway-*/; do
  n=$(basename "$d")
  printf '  %-18s %s\n' "$n" "$($S6STAT "$d" 2>/dev/null)"
done

echo
echo "=== procesos 'gateway run' ==="
ps -ef 2>/dev/null | grep -c '[g]ateway run'

echo
echo "=== vigia carga su config (sin fallback)? ==="
tail -40 /opt/data/logs/gateways/vigia/current 2>/dev/null | grep -iE 'falling back|failed to parse|config' | tail -5 || echo "  (sin lineas de fallback)"
