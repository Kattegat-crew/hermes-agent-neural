#!/bin/bash
# embed_heimdall_semanal.sh — entrega embed (ncl-embed/1) del cron heimdall-dashboard-semanal.
# Es un informe en markdown: --no-fields evita que sus líneas se conviertan en fields.
set -u
exec /usr/bin/python3 /opt/hermes-agent-data/scripts/ncl_cron_embed.py \
  --job "heimdall-dashboard-semanal" \
  --channel "1567587887757926501" \
  --title "Heimdall · dashboard semanal — $(TZ=America/Bogota date '+%d %b %H:%M')" \
  --footer "NeuralCrew Labs · Analytics" \
  --timeout 600 --no-fields \
  --run "/usr/bin/python3 /opt/hermes-agent-data/scripts/heimdall_semanal.py"
