#!/bin/bash
# embed_finanzas_captura.sh — entrega embed (ncl-embed/1) del cron finanzas-captura-diaria.
# captura.py ya calla cuando no hay nada nuevo; aquí solo se cambia el sobre del mensaje.
set -u
exec /usr/bin/python3 /opt/hermes-agent-data/scripts/ncl_cron_embed.py \
  --job "finanzas-captura-diaria" \
  --channel "1567587939783806996" \
  --title "Finanzas · captura diaria — $(TZ=America/Bogota date '+%d %b')" \
  --footer "NeuralCrew Labs · Finanzas" \
  --timeout 900 \
  --run "bash /opt/hermes-agent-data/scripts/finanzas_captura.sh"
