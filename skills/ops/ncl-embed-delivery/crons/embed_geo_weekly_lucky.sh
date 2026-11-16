#!/bin/bash
# embed_geo_weekly_lucky.sh — entrega embed (ncl-embed/1) del digest GEO semanal de Lucky Brothers.
set -u
exec /usr/bin/python3 /opt/hermes-agent-data/scripts/ncl_cron_embed.py \
  --job "geo-weekly-lucky-deliver" \
  --channel "1568745613955432540" \
  --title "GEO · Lucky Brothers · semana $(TZ=America/Bogota date '+%d %b')" \
  --footer "NeuralCrew Labs · GEO" \
  --timeout 300 --no-fields \
  --run "bash /opt/hermes-agent-data/scripts/geo_weekly_deliver_lucky.sh"
