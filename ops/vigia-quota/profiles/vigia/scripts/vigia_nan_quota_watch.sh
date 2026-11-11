#!/bin/bash
# vigia_nan_quota_watch.sh — wrapper del watchdog de cuota nan para el perfil vigia.
# 1) Fija HERMES_HOME canónico (el default del script apunta a ruta legacy muerta).
# 2) Anti-spam: silencio = sin novedad. Con entrega por cron (`no_agent`), stdout
#    vacío no envía nada, así que no hace falta el eco "(sin novedades)".
# 3) La entrega al hilo la hace el cron (deliver discord:1555646851330478200).
#    Antes se publicaba con vigia_post_thread.sh leyendo DISCORD_BOT_TOKEN de
#    /opt/data/.env; ese token ya no vive ahí (lo materializa el gateway desde el
#    vault) y los avisos se perdían en silencio desde el 26-oct.
set -u
CANON="/opt/hermes-agent-data"
mkdir -p "$CANON/state" 2>/dev/null
OUT=$(HERMES_HOME="$CANON" /usr/bin/python3 "$CANON/scripts/nan_quota_watch.py" 2>&1)
RC=$?
if [ -n "$OUT" ]; then
  printf '%s\n' "$OUT"
  printf '%s' "$OUT" | "$CANON/scripts/vigia_post_thread.sh" "${VIGIA_NAN_THREAD_ID:-1555646851330478200}"
elif [ "$RC" -ne 0 ]; then
  printf '**Cuota NaN** — el watchdog falló (rc=%s)\n' "$RC"
fi
exit 0
