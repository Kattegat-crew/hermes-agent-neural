#!/bin/bash
# Reinicio del gateway de Hermes detectando el servicio s6 REAL (no hardcodear).
# Lección 26/08: el layout s6 cambió (19/08 main-hermes real -> 26/08 gateway-default real);
# reiniciar el wrapper (main-hermes) NO toca el proceso python del gateway.
# Uso: programar vía cron one-shot no_agent 3-4 min en el futuro (nunca dentro del turno actual).
LOG=/opt/data/logs/gateway-restart.log
mkdir -p /opt/data/logs

GW_PID=$(pgrep -f "hermes gateway run" | head -1)
if [ -z "$GW_PID" ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') ERROR: no hay proceso 'hermes gateway run' vivo" >> "$LOG"
    exit 1
fi
SUP_PID=$(ps -o ppid= -p "$GW_PID" | tr -d ' ')
SVC=$(ps -o cmd= -p "$SUP_PID" | awk '{print $2}')   # p.ej. gateway-default (supervisor s6)
if [ -z "$SVC" ] || [ ! -e "/run/service/$SVC" ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') ERROR: supervisor $SVC no resuelto (PPID $SUP_PID)" >> "$LOG"
    exit 1
fi

echo "$(date '+%Y-%m-%d %H:%M:%S') restarting $SVC (supervisor de gw PID $GW_PID)" >> "$LOG"
/package/admin/s6/command/s6-svc -r "/run/service/$SVC" >> "$LOG" 2>&1
echo "$(date '+%Y-%m-%d %H:%M:%S') s6-svc exit=$?" >> "$LOG"
sleep 25
echo "$(date '+%Y-%m-%d %H:%M:%S') post-check: $(pgrep -af 'hermes gateway run' | grep -v grep | head -1)" >> "$LOG"
exit 0