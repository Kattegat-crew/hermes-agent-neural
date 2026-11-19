#!/bin/bash
# install.sh — publica el helper y los runners en la ruta operativa de crons.
#
# Copia (no symlink: el scheduler rechaza scripts que escapan del directorio por traversal)
# y verifica byte a byte. Uso:
#   ./install.sh            # instala/actualiza
#   ./install.sh --check    # solo verifica, no escribe (para cron de deriva)
set -euo pipefail

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST="${DEST_DIR:-/opt/hermes-agent-data/scripts}"
MODE="${1:-install}"
# `--check` está documentado como solo-verificación: no debe crear nada en disco. Y un flag
# desconocido (`--help`) caía antes en el ramo de instalación, sobreescribiendo archivos.
case "$MODE" in
  install|--install) MODE=install ;;
  --check|-c)        MODE=--check ;;
  *) echo "uso: $0 [install|--check]" >&2; exit 2 ;;
esac
[ "$MODE" = "--check" ] || mkdir -p "$DEST"

copy_one() {
  local src="$1" rel="$2"
  local dst="$DEST/$(basename "$rel")"
  if [ "$MODE" = "--check" ]; then
    if [ -L "$dst" ]; then
      echo "DRIFT $dst (es un symlink; el scheduler lo rechaza)"
      return 1
    elif cmp -s "$src" "$dst"; then
      echo "ok   $dst"
    else
      echo "DRIFT $dst"
      return 1
    fi
  else
    rm -f "$dst"
    install -m 0755 "$src" "$dst"
    cmp -s "$src" "$dst" && echo "ok   $dst" || { echo "FALLO $dst"; return 1; }
  fi
}

rc=0
copy_one "$SRC_DIR/scripts/ncl_embed.py" "ncl_embed.py" || rc=1
copy_one "$SRC_DIR/scripts/ncl_cron_embed.py" "ncl_cron_embed.py" || rc=1
for f in "$SRC_DIR"/crons/*.sh; do
  [ -e "$f" ] || continue
  copy_one "$f" "$(basename "$f")" || rc=1
done
exit $rc
