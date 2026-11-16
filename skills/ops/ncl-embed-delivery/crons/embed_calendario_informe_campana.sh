#!/bin/bash
# embed_calendario_informe_campana.sh — entrega embed (ncl-embed/1) del cron calendario-informe-campana.
# Sustituye la entrega de texto plano del gateway. Silencioso si el script no tiene nada que contar.
set -u
exec /usr/bin/python3 /opt/hermes-agent-data/scripts/ncl_cron_embed.py \
  --job "calendario-informe-campana" \
  --channel "1567587946373062667" \
  --title "Calendario · informe de campaña — $(TZ=America/Bogota date '+%d %b')" \
  --footer "NeuralCrew Labs · Calendario" \
  --timeout 600 \
  --run "bash /opt/hermes-agent-data/scripts/calendario_campaign_report.sh"
