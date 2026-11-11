#!/bin/bash
# vigia_quota_digest.sh — informe 2x/día de cuotas de suscripciones (perfil vigia).
#
# Genera el informe (OpenCode Go, Codex, Antigravity, NaN) y lo publica en el hilo
# de Discord con vigia_post_thread.sh: el perfil vigia NO tiene la plataforma
# discord configurada, así que `deliver discord:<id>` en el cron falla.
#
# El home canónico es /opt/hermes-agent-data (config.yaml con la key de NaN, el
# secret de sesión y los scripts compartidos), NO el home del perfil vigia.
#
# Regla de honestidad: si el informe se genera pero NO se publica, el script sale
# con código 3 para que el cron marque la corrida como fallida. Antes salía 0 y el
# aviso se perdía en silencio (falso verde).
set -u

CANON="/opt/hermes-agent-data"
PY="${PYTHON:-/usr/bin/python3}"
THREAD="${VIGIA_QUOTA_THREAD_ID:-1555646851330478200}"

OUT=$(HERMES_HOME="$CANON" "$PY" "$CANON/scripts/quota_digest.py" 2>&1)
RC=$?

if [ "$RC" -ne 0 ]; then
  MSG=$(printf '**Cuotas de suscripciones** — fallo generando el informe (rc=%s)\n\n%s\n' \
    "$RC" "$(printf '%s' "$OUT" | tail -15)")
elif [ -z "$OUT" ]; then
  MSG='**Cuotas de suscripciones** — el informe salió vacío'
else
  MSG="$OUT"
fi

printf '%s\n' "$MSG"

# Publicación (el cron corre con deliver=local: el stdout solo va al log).
POST=$(printf '%s' "$MSG" | "$CANON/scripts/vigia_post_thread.sh" "$THREAD" 2>&1)

if [ "${POST##*:}" != "200" ]; then
  printf '**Cuotas de suscripciones** — el informe no se publicó en el hilo (%s)\n' "${POST:-sin salida}" >&2
  exit 3
fi

exit 0
