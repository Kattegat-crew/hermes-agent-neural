#!/usr/bin/env bash
# Probe read-only de disponibilidad del backend image_gen de Hermes, por perfil.
# NUNCA genera una imagen (cero costo): imprime provider/model/fal_key/available.
# Uso:  bash image_gen_probe.sh [slug ...]      (sin args = solo el perfil default)
set -u
PY=/opt/hermes/.venv/bin/python
BASE=/opt/data

probe() {
  local home="$1" label="$2"
  LABEL="$label" HERMES_HOME="$home" "$PY" - <<'PY' 2>/dev/null || echo "$label: PROBE FAILED (¿existe /opt/hermes/.venv?)"
import os, sys
sys.path.insert(0, "/opt/hermes")
from tools.image_generation_tool import (check_image_generation_requirements as c,
    _read_configured_image_provider as p, _read_configured_image_model as m,
    check_fal_api_key as f)
print(f"{os.environ['LABEL']:<14} provider={p()}  model={m()}  fal_key={f()}  available={c()}")
PY
}

cd /opt/hermes || exit 1
probe "$BASE" default
for slug in "$@"; do
  probe "$BASE/profiles/$slug" "$slug"
done
