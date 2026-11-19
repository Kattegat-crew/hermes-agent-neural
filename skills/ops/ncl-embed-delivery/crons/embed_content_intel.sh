#!/bin/bash
# embed_content_intel.sh — entrega embed (ncl-embed/1) del cron content-intel-daily.
# Es un informe en markdown: --no-fields evita que sus líneas se conviertan en fields.
set -u
exec /usr/bin/python3 /opt/hermes-agent-data/scripts/ncl_cron_embed.py \
  --job "content-intel-daily" \
  --channel "1567587777120313376" \
  --title "Contenido · inteligencia diaria — $(TZ=America/Bogota date '+%d %b %H:%M')" \
  --footer "NeuralCrew Labs · Contenido" \
  --timeout 600 --no-fields \
  --run "bash /opt/hermes-agent-data/scripts/content_intel_cron.sh"
