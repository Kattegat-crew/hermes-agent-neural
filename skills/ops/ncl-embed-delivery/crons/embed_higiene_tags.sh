#!/bin/bash
# embed_higiene_tags.sh — entrega embed (ncl-embed/1) del cron higiene-tags-tickets-semanal.
# Es un informe en markdown: --no-fields evita que sus líneas se conviertan en fields.
set -u
exec /usr/bin/python3 /opt/hermes-agent-data/scripts/ncl_cron_embed.py \
  --job "higiene-tags-tickets-semanal" \
  --channel "1564308156044279938" \
  --title "Tickets · higiene de etiquetas — $(TZ=America/Bogota date '+%d %b %H:%M')" \
  --footer "NeuralCrew Labs · Tickets" \
  --timeout 300 --no-fields \
  --run "/usr/bin/python3 /opt/hermes-agent-data/scripts/higiene_tags_tickets.py"
