#!/usr/bin/env bash
# upload_drive.sh — sube los entregables de staging a
#   <Cliente>/05-informes/rendicion-de-cuentas/YYYY-MM/
# SOLO se ejecuta vía run_rendicion.sh --upload-drive con APPROVED=1 (gate humano).
# Credenciales: /opt/data/secrets/jonathan-drive.json (cuenta de subida).
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
MES=""
STAGING=""
while [ $# -gt 0 ]; do
  case "$1" in
    --mes) MES="$2"; shift 2;;
    --staging) STAGING="$2"; shift 2;;
    *) echo "arg desconocido: $1"; exit 64;;
  esac
done
[ -n "$MES" ] && [ -n "$STAGING" ] || { echo "uso: upload_drive.sh --mes YYYY-MM --staging DIR"; exit 64; }

python3 "$DIR/upload_drive.py" --mes "$MES" --staging "$STAGING"
