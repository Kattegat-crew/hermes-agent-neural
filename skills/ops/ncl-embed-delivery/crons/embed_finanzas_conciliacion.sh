#!/bin/bash
# embed_finanzas_conciliacion.sh — entrega embed (ncl-embed/1) del cron finanzas-conciliacion-semanal.
# conciliacion.py calla si todo está conciliado; el runner respeta ese silencio.
set -u
exec /usr/bin/python3 /opt/hermes-agent-data/scripts/ncl_cron_embed.py \
  --job "finanzas-conciliacion-semanal" \
  --channel "1567587939783806996" \
  --title "Finanzas · conciliación semanal — $(TZ=America/Bogota date '+%d %b')" \
  --footer "NeuralCrew Labs · Finanzas" \
  --timeout 900 \
  --run "bash /opt/hermes-agent-data/scripts/finanzas_conciliacion.sh"
