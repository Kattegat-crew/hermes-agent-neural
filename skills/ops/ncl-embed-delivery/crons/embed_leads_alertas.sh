#!/bin/bash
# embed_leads_alertas.sh — entrega embed (ncl-embed/1) del cron leads-alertas.
# Es un informe en markdown: --no-fields evita que sus líneas se conviertan en fields.
set -u
exec /usr/bin/python3 /opt/hermes-agent-data/scripts/ncl_cron_embed.py \
  --job "leads-alertas" \
  --channel "1567587925548335355" \
  --title "Leads · alertas nuevas — $(TZ=America/Bogota date '+%d %b %H:%M')" \
  --footer "NeuralCrew Labs · Leads" \
  --timeout 300 --no-fields \
  --run "/usr/bin/python3 /opt/hermes-agent-data/scripts/leads_alertas.py"
