#!/usr/bin/env bash
# Reapunta el cron diario de vigilancia de skills al job de higiene del árbol único.
# Respalda la crontab ANTES de tocarla (R12/plan F5) y verifica el resultado.
set -uo pipefail
R=/root/hermes-agent-legacy-docker
TS=$(date +%Y%m%d-%H%M%S)
BK="$R/data/backups/crontab_${TS}.txt"

crontab -l > "$BK" 2>/dev/null && echo "respaldo de crontab: $BK" || { echo "no hay crontab"; exit 1; }

if grep -q "f3_higiene_diaria.py" "$BK"; then
  echo "ya estaba reapuntado; nada que hacer"
  exit 0
fi

NUEVA=$(mktemp)
# retira la línea vieja del vigilante canon<->copia y añade el job nuevo
grep -v "skills_sync_daily.sh" "$BK" > "$NUEVA"
printf '20 5 * * * /root/hermes-agent-legacy-docker/scripts/f3_higiene_diaria.py >> /var/log/skills-higiene.log 2>&1\n' >> "$NUEVA"
crontab "$NUEVA" && echo "crontab actualizada"
rm -f "$NUEVA"

echo
echo "=== crontab resultante (líneas de skills) ==="
crontab -l | grep -iE "skill|higiene" || echo "  (ninguna)"
echo
echo "=== diff con el respaldo ==="
diff "$BK" <(crontab -l) || true
