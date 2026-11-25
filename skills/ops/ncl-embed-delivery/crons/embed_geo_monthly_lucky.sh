#!/bin/bash
# embed_geo_monthly_lucky.sh — entrega embed (ncl-embed/1) del digest GEO mensual de Lucky Brothers.
set -u
exec /usr/bin/python3 /opt/hermes-agent-data/scripts/ncl_cron_embed.py \
  --job "geo-monthly-lucky-deliver" \
  --channel "1568745613955432540" \
  --title "GEO · Lucky Brothers · mes $(TZ=America/Bogota date '+%b %Y')" \
  --footer "NeuralCrew Labs · GEO" \
  --timeout 600 --no-fields \
  --run "bash /opt/hermes-agent-data/scripts/geo_monthly_deliver_lucky.sh"
