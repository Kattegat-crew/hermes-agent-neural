#!/usr/bin/env bash
# Sonda F3 dentro del contenedor: lectura del catálogo + resolución de destino + M4.
set -uo pipefail
export HOME=/opt/data
cd /opt/data
H=/opt/hermes/.venv/bin/hermes

echo "=== 1) lectura del catálogo (skills canónicas presentes) ==="
for s in skill-library-ops meta-ads-ops colombia-legal-ops hermes-fleet-operations; do
  n=$($H skills list 2>/dev/null | grep -c "$s")
  echo "   $s -> $n coincidencia(s)"
done
echo "   --- archivos del archivo (no deben aparecer) ---"
for s in caveman diagram-design ponytail; do
  n=$($H skills list 2>/dev/null | grep -c "$s")
  echo "   $s -> $n coincidencia(s)"
done

echo
echo "=== 2) destino real de escritura del runtime (get_skills_dir) ==="
for P in "" roshi vigia bragi; do
  if [ -z "$P" ]; then
    HERMES_HOME=/opt/data python3 -c "
import sys; sys.path.insert(0,'/opt/hermes')
from hermes_constants import get_hermes_home, get_skills_dir
print('   default  ->', get_skills_dir())"
  else
    HERMES_HOME=/opt/data/profiles/$P python3 -c "
import sys; sys.path.insert(0,'/opt/hermes')
from hermes_constants import get_hermes_home, get_skills_dir
print('   $P ->', get_skills_dir())"
  fi
done

echo
echo "=== 3) M4: escritura de sonda como uid 10000 en el canon ==="
S=/opt/data/profiles/roshi/skills/.probe_f3_m4
if touch "$S" 2>/dev/null; then echo "   ✅ escritura OK: $(ls -l "$S")"; rm -f "$S"; else echo "   ❌ sin permiso de escritura"; fi

echo
echo "=== 4) M4: edición real de una skill canónica (patch de agente) ==="
F=/opt/data/skills/core/skill-library-ops/SKILL.md
if [ -w "$F" ]; then
  cp "$F" /tmp/skill_library_ops.bak
  printf '\n<!-- probe F3 M4: linea de prueba de escritura del runtime -->\n' >> "$F"
  echo "   ✅ edición aplicada por uid $(id -u) sobre $F"
  echo "   (la reversión la hace el script del host)"
else
  echo "   ❌ el runtime no puede escribir la skill canónica"
fi
