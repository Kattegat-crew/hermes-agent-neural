#!/bin/bash
# embed_gbp_quota.sh — entrega embed (ncl-embed/1) del cron gbp-quota-watch.
# Es un informe en markdown: --no-fields evita que sus líneas se conviertan en fields.
set -u
exec /usr/bin/python3 /opt/hermes-agent-data/scripts/ncl_cron_embed.py \
  --job "gbp-quota-watch" \
  --channel "1570900605973700731" \
  --title "Plataforma · cuota GBP — $(TZ=America/Bogota date '+%d %b %H:%M')" \
  --footer "NeuralCrew Labs · Plataforma" \
  --timeout 300 --no-fields \
  --run "/usr/bin/python3 /opt/hermes-agent-data/scripts/gbp_quota_probe.py"
