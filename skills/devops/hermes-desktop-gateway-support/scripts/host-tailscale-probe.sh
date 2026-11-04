#!/usr/bin/env bash
# Estado del tailnet del HOST visto desde dentro del contenedor de un perfil Hermes.
# Uso: bash host-tailscale-probe.sh [peer-ip ...]
#   (sin args: prueba los peers Windows conocidos del tailnet de NeuralCrew)
# Vars: TAILSCALE_BIN, TAILSCALE_SOCK, GATEWAY_URL
set -uo pipefail

SOCK="${TAILSCALE_SOCK:-/host/run/tailscale/tailscaled.sock}"
TS="${TAILSCALE_BIN:-/host/usr/bin/tailscale}"
GATEWAY="${GATEWAY_URL:-http://100.86.8.81:9112}"

PEERS=("$@")
if [ ${#PEERS[@]} -eq 0 ]; then
  PEERS=(100.102.79.4 100.116.169.91 100.112.161.72)
fi

[ -x "$TS" ] || { echo "FALTA binario tailscale del host en $TS"; exit 1; }
[ -S "$SOCK" ] || { echo "FALTA socket tailscaled en $SOCK"; exit 1; }

echo "== estado tailnet (host) =="
"$TS" --socket="$SOCK" status || true

echo
echo "== peers: online / lastseen / expiry / ips =="
"$TS" --socket="$SOCK" status --json | python3 -c '
import json, sys
d = json.load(sys.stdin)
s = d.get("Self", {})
print("self: %s %s online=%s keyExpiry=%s" % (s.get("HostName"), s.get("TailscaleIPs"), s.get("Online"), s.get("KeyExpiry")))
rows = sorted((d.get("Peer") or {}).values(), key=lambda p: str(p.get("HostName")))
for p in rows:
    print("%-22s os=%-8s online=%-5s lastseen=%-25s keyExpiry=%-21s ips=%s" % (
        p.get("HostName"), p.get("OS"), p.get("Online"), p.get("LastSeen"), p.get("KeyExpiry"), p.get("TailscaleIPs")))
'

echo
echo "== ping a peers (3s c/u) =="
for ip in "${PEERS[@]}"; do
  printf -- "--- %s: " "$ip"
  timeout 8 "$TS" --socket="$SOCK" ping --c 1 --timeout 3s "$ip" 2>&1 | tail -1
done

echo
echo "== gateway $GATEWAY =="
curl -s -o /dev/null -w "login=%{http_code} (%{time_total}s)\n" "$GATEWAY/login" || echo "login: sin respuesta"
curl -s -o /dev/null -w "ws-ticket sin sesion=%{http_code} (401 = vivo)\n" -X POST "$GATEWAY/api/auth/ws-ticket" || echo "ws-ticket: sin respuesta"
