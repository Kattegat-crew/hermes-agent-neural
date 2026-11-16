#!/bin/bash
# embed_guardar_diario.sh — entrega embed (ncl-embed/1) del cron guardar-diario-confirmar.
# Es un informe en markdown: --no-fields evita que sus líneas se conviertan en fields.
set -u
exec /usr/bin/python3 /opt/hermes-agent-data/scripts/ncl_cron_embed.py \
  --job "guardar-diario-confirmar" \
  --channel "1570900607227793428" \
  --title "Higiene · confirmación diaria — $(TZ=America/Bogota date '+%d %b %H:%M')" \
  --footer "NeuralCrew Labs · Higiene" \
  --timeout 300 --no-fields \
  --run "/usr/bin/python3 /opt/hermes-agent-data/scripts/guardar_diario_confirmar.py"
