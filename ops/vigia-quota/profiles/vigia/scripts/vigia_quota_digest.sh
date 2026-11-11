#!/bin/bash
# vigia_quota_digest.sh — informe 2x/día de cuotas de suscripciones (perfil vigia).
#
# Genera el informe (OpenCode Go, Codex, Antigravity, NaN) y lo imprime tal cual:
# la entrega al hilo de Discord la hace el cron (deliver discord:<channel>), así
# el token del bot lo resuelve el gateway y no hay que duplicarlo en un curl.
#
# El home canónico es /opt/hermes-agent-data (config.yaml con la key de NaN y los
# scripts compartidos), NO el home del perfil vigia.
#
# Siempre exit 0: un fallo del informe no debe romper el cron. Si no se puede
# generar, imprime el error (mejor un aviso roto que un silencio falso).
set -u

CANON="/opt/hermes-agent-data"
PY="${PYTHON:-/usr/bin/python3}"

OUT=$(HERMES_HOME="$CANON" "$PY" "$CANON/scripts/quota_digest.py" 2>&1)
RC=$?

if [ "$RC" -ne 0 ]; then
  printf '**Cuotas de suscripciones** — fallo generando el informe (rc=%s)\n\n%s\n' \
    "$RC" "$(printf '%s' "$OUT" | tail -15)"
  exit 0
fi

if [ -z "$OUT" ]; then
  printf '**Cuotas de suscripciones** — el informe salió vacío\n'
  exit 0
fi

printf '%s\n' "$OUT"
exit 0
