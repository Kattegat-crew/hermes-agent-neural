#!/bin/bash
# embed_geo_monthly_golden.sh — entrega embed (ncl-embed/1) del digest GEO mensual de Golden Game.
set -u
exec /usr/bin/python3 /opt/hermes-agent-data/scripts/ncl_cron_embed.py \
  --job "geo-monthly-golden-deliver" \
  --channel "1568745608561565737" \
  --title "GEO · Golden Game · mes $(TZ=America/Bogota date '+%b %Y')" \
  --footer "NeuralCrew Labs · GEO" \
  --timeout 600 --no-fields \
  --run "bash /opt/hermes-agent-data/scripts/geo_monthly_deliver_golden.sh"
