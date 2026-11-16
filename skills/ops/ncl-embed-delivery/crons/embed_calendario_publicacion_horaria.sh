#!/bin/bash
# embed_calendario_publicacion_horaria.sh — entrega embed (ncl-embed/1) del publicador horario.
# El filtro del publicador ya decide qué líneas son reportables; aquí solo cambia el sobre.
set -u
exec /usr/bin/python3 /opt/hermes-agent-data/scripts/ncl_cron_embed.py \
  --job "calendario-publicacion-horaria" \
  --channel "1567587946373062667" \
  --title "Calendario · publicación horaria — $(TZ=America/Bogota date '+%d %b %H:%M')" \
  --footer "NeuralCrew Labs · Calendario" \
  --timeout 600 \
  --run "bash /opt/hermes-agent-data/scripts/calendario_publish_due_filtered.sh"
