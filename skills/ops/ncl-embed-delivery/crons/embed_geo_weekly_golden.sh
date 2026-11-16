#!/bin/bash
# embed_geo_weekly_golden.sh — entrega embed (ncl-embed/1) del digest GEO semanal de Golden Game.
# El digest ya viene en markdown: --no-fields evita que sus líneas se conviertan en fields.
set -u
exec /usr/bin/python3 /opt/hermes-agent-data/scripts/ncl_cron_embed.py \
  --job "geo-weekly-golden-deliver" \
  --channel "1568745608561565737" \
  --title "GEO · Golden Game · semana $(TZ=America/Bogota date '+%d %b')" \
  --footer "NeuralCrew Labs · GEO" \
  --timeout 300 --no-fields \
  --run "bash /opt/hermes-agent-data/scripts/geo_weekly_deliver_golden.sh"
