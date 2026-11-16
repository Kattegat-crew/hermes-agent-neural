#!/bin/bash
# embed_upstream_review.sh — entrega embed (ncl-embed/1) del cron hermes-upstream-review.
# Es un informe en markdown: --no-fields evita que sus líneas se conviertan en fields.
set -u
exec /usr/bin/python3 /opt/hermes-agent-data/scripts/ncl_cron_embed.py \
  --job "hermes-upstream-review" \
  --channel "1570900605973700731" \
  --title "Plataforma · revisión upstream — $(TZ=America/Bogota date '+%d %b %H:%M')" \
  --footer "NeuralCrew Labs · Plataforma" \
  --timeout 600 --no-fields \
  --run "/usr/bin/python3 /opt/hermes-agent-data/scripts/hermes_upstream_review.py"
