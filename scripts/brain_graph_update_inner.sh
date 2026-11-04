#!/bin/bash
# brain_graph_update_inner.sh — se ejecuta EN EL HOST NATIVO (F6)
# (el wrapper del cron lo lanza con runuser/directo como hermes).
#
# Estrategia 2026-09-11: incremental POR ARCHIVO + respaldo al modo completo.
#   * `--force` re-procesa TODO el brain (~479 archivos) contra el modelo de pago:
#     una noche de las 377 notas ≈ dólares. Medido: 3 notas = $0.021 (28 nodos).
#   * El incremental nativo de graphify (extract sin --force) NO sirve aquí: aborta con
#     "deduplicate_entities: nodes span multiple repos ['data_brain','data_brain-2']".
#   * Via elegida: manifest de hashes → extraer SOLO lo cambiado a /tmp → merge-graphs.
#   * GUARDA: si el número de nodos baja, se RESTAURA el backup y se reporta ERROR
#     (nunca dejar el grafo encogido en silencio — pasó el 11-sep al probar).
#   * Domingo (o FULL=1) se fuerza el completo, que además limpia notas borradas.

set -u
cd /opt/hermes-agent-data

G=/opt/hermes-agent-data/brain/graphify-out-v2/graph.json
BAK=/opt/hermes-agent-data/brain/graphify-out-v2/graph.json.bak-last
PRE=/opt/hermes-agent-data/brain/graphify-out-v2/graph.json.pre-run
MANIFEST=/opt/hermes-agent-data/brain/graphify-out-v2/.brain_manifest.json
WORK=/tmp/brain-inc
LOG=/opt/hermes-agent-data/brain/graphify_update.log
# OJO: `grep -c .` sobre un archivo VACÍO imprime "0" Y devuelve exit 1 → con `|| echo 0`
# la variable quedaba "0\n0" y `[ ... -eq 0 ]` reventaba ("integer expression expected"),
# disparando el modo completo. Se usa awk+wc, que no falla en vacío.
CHANGED=$(mktemp /tmp/brain_changed.XXXXXX.txt)
FULL="${FULL:-0}"
DOW=$(date +%u)   # 7 = domingo

nodes() { python3 -c "import json;print(len(json.load(open('$1')).get('nodes',[])))" 2>/dev/null || echo 0; }
WEB=""
if [ -f /opt/hermes-agent-data/config.yaml ]; then WEB=https://api.nan.builders/v1; fi
KEY=""
# El PATH del cron resuelve `python3` al intérprete gestionado por Hermes, que NO
# trae PyYAML (fallo del 15-oct al 19-oct: KEY vacía → EXTRACT_ERROR). Se usa
# explícitamente un intérprete con yaml y se conserva `python3` como respaldo.
PY_YAML=""
for _py in /usr/bin/python3 /usr/bin/python3.12 python3; do
  if "$_py" -c "import yaml" >/dev/null 2>&1; then PY_YAML="$_py"; break; fi
done
if [ -n "$PY_YAML" ]; then
  KEY=$("$PY_YAML" -c "import yaml;print(yaml.safe_load(open('/opt/hermes-agent-data/config.yaml'))['providers']['NaN-Builders']['api_key'])" 2>/dev/null || echo "")
fi
# v0.22.x: config.yaml usa placeholders ${VAR} -> expandir desde la fuente de
# secretos de Hermes (Bitwarden). Sin esto el placeholder literal se envía como
# API key y el backend responde 401 (fallo del 27-oct, extract_error inner_rc=1).
if [[ "$KEY" == '${'* ]]; then
  _VARNAME="${KEY#\$\{}"
  _VARNAME="${_VARNAME%\}}"
  KEY="$(/opt/hermes-agent/.venv/bin/python3 -c "
import sys
sys.path.insert(0, '/opt/hermes-agent')
from hermes_cli.env_loader import hydrate_profile_secret_sources
print(hydrate_profile_secret_sources('/opt/hermes-agent-data').get('$_VARNAME', ''))
" 2>/dev/null || true)"
fi
# Sin clave legible no se intenta nada: graphify reporta "0 docs" y produce un grafo
# vacío, que era el fallo silencioso del 11-sep (config.yaml quedó en root:root).
if [ -z "$KEY" ]; then
  echo "EXTRACT_ERROR: no se pudo leer la API key en /opt/hermes-agent-data/config.yaml (interprete_con_yaml='${PY_YAML:-ninguno}'; ¿permisos? esperado hermes:10000 0640)"
  exit 1
fi

N0=$(nodes "$G")
cp "$G" "$PRE" 2>/dev/null || true

# Higiene: si este script corre como root (p.ej. manual), deja el árbol en
# manos de hermes para que el gateway pueda escribirlo después. Si ya corre como
# hermes, el chown falla y no pasa nada (2>/dev/null).
chown -R hermes:hermes /opt/hermes-agent-data/brain/graphify-out-v2 2>/dev/null || true
chown -R hermes:hermes /opt/hermes-agent-data/brain 2>/dev/null || true

# ── 1. Diff por hash (solo notas .md; respeta .graphifyignore del brain) ─────
python3 - "$MANIFEST" "$CHANGED" <<'PY'
import hashlib, json, os, sys
man_path, out_path = sys.argv[1], sys.argv[2]
ROOT = '/opt/hermes-agent-data/brain'
# Debe coincidir con /opt/hermes-agent-data/brain/.graphifyignore: lo que no se indexa tampoco
# se vigila, si no cada cambio en material crudo dispararía una corrida inútil.
SKIP_DIRS = {'graphify-out', 'graphify-out-v2', 'archive', 'raw'}
cur = {}
for dp, dn, fn in os.walk(ROOT):
    dn[:] = [d for d in dn if d not in SKIP_DIRS]
    for f in fn:
        if not f.endswith('.md'):
            continue
        p = os.path.join(dp, f)
        try:
            cur[os.path.relpath(p, ROOT)] = hashlib.sha1(open(p, 'rb').read()).hexdigest()
        except OSError:
            pass
try:
    old = json.load(open(man_path))
except Exception:
    old = {}
changed = sorted(k for k, v in cur.items() if old.get(k) != v)
# OJO: hay que terminar con \n. Sin salto final, `while read` devuelve error en la
# última línea y NO ejecuta el cuerpo del bucle (con 1 sola nota, no copiaba nada).
open(out_path, 'w').write('\n'.join(changed) + ('\n' if changed else ''))
# F6-fix 02-oct-2026: NO commitear el manifiesto aqui. Se escribe a MANIFEST.new y
# solo se mueve al oficial DESPUES de que la extraccion+merge+guardas tengan exito.
# (El dump directo aca era un bug de update optimista: toda corrida fallida marcaba
# las notas pendientes como procesadas y el grafo se quedaba congelado en silencio.)
json.dump(cur, open(man_path + '.new', 'w'), indent=0)
print(f"[brain-graph] notas indexables: {len(cur)} · nuevas/cambiadas: {len(changed)}")
PY

NCH=$(awk 'NF' "$CHANGED" 2>/dev/null | wc -l | tr -d ' ')
[ -z "$NCH" ] && NCH=0

# ── 2. Nada nuevo y no toca limpieza → coste CERO ────────────────────────────
if [ "$NCH" -eq 0 ] && [ "$FULL" != "1" ] && [ "$DOW" != "7" ]; then
  echo "[brain-graph] sin cambios: 0 notas nuevas → no se llamó a la API (coste 0)"
  echo "nodes before=$N0 after=$N0"
  mv -f "$MANIFEST.new" "$MANIFEST" 2>/dev/null || true
  exit 0
fi

cp "$G" "$BAK" 2>/dev/null || true

extract() {  # $1 = origen, $2 = destino
  # F6-fix 02-oct-2026: qwen3.6 respondia pero NO extraia (chunk truncado en
  # max_completion_tokens, 0 nodos). deepseek-v4-flash verificado: 50 nodos/79 edges.
  OPENAI_API_KEY="$KEY" OPENAI_BASE_URL="$WEB" OPENAI_MODEL="${GRAPHIFY_MODEL:-deepseek-v4-flash}" \
  /usr/local/bin/graphify extract "$1" --backend openai --out "$2" \
    --max-concurrency 2 --api-timeout 90 "$3"
}

OK=0
if [ "$NCH" -gt 0 ] && [ "$FULL" != "1" ] && [ "$DOW" != "7" ]; then
  # ── 3a. Vía barata: extraer solo lo cambiado y fusionar ───────────────────
  # Directorio de trabajo ÚNICO por corrida: un /tmp/brain-inc persistente quedó
  # de una prueba anterior y el `cp` falló → la extracción escaneaba un dir vacío.
  WORK=$(mktemp -d /tmp/brain-inc.XXXXXX)
  mkdir -p "$WORK/brain"
  COPIED=0
  while IFS= read -r rel; do
    [ -z "$rel" ] && continue
    mkdir -p "$WORK/brain/$(dirname "$rel")"
    if cp "/opt/hermes-agent-data/brain/$rel" "$WORK/brain/$rel" 2>/dev/null; then
      COPIED=$((COPIED + 1))
    else
      echo "AVISO: no se pudo copiar $rel"
    fi
  done < "$CHANGED"
  if [ "$COPIED" -eq 0 ]; then
    echo "EXTRACT_ERROR: 0 de $NCH notas se pudieron copiar al temporal $WORK; no se extrae nada"
    exit 1
  fi
  echo "[brain-graph] incremental: $COPIED/$NCH nota(s) copiadas a $WORK"
  extract "$WORK/brain" "$WORK" "" > /opt/hermes-agent-data/brain/graphify_inc.log 2>&1
  if [ -f "$WORK/graphify-out/graph.json" ]; then
    # merge a un TERCER archivo y luego mover: nunca leer y escribir el mismo path
    if /usr/local/bin/graphify merge-graphs "$G" "$WORK/graphify-out/graph.json" \
         --out /tmp/brain_merged.json >> /opt/hermes-agent-data/brain/graphify_inc.log 2>&1; then
      mv /tmp/brain_merged.json "$G" && OK=1 && MODE=inc
    fi
  fi
  # Si la vía barata falla NO se dispara el modo completo (caro) por sorpresa:
  # se reporta y se sale; el completo queda para el domingo o FULL=1.
  if [ "$OK" != "1" ]; then
    echo "EXTRACT_ERROR: la extracción incremental no produjo grafo (ver /opt/hermes-agent-data/brain/graphify_inc.log)"
    exit 1
  fi
else

# ── 3b. Respaldo: modo completo (fallback, o limpieza dominical) ─────────────
# CLAVE: la extracción completa va a un directorio TEMPORAL y luego REEMPLAZA el grafo.
#   `extract --out /opt/hermes-agent-data/brain` sobre un brain que YA tiene graphify-out/graph.json
#   hace que graphify FUSIONE la extracción nueva con la existente → duplica todo
#   (40.956 → 81.912 nodos, exactamente 2×; pasó dos veces el 11-sep).
if [ "$OK" != "1" ]; then
  echo "[brain-graph] modo completo (--force, out temporal + reemplazo)"
  rm -rf /tmp/brain-full
  extract /opt/hermes-agent-data/brain /tmp/brain-full "--force" > /opt/hermes-agent-data/brain/graphify_full.log 2>&1
  if [ -s /tmp/brain-full/graphify-out/graph.json ]; then
    mv /tmp/brain-full/graphify-out/graph.json "$G" && OK=1
  fi
fi
fi   # cierra el if/else del modo (incremental | completo)

N1=$(nodes "$G")
MODE="${MODE:-full}"

# ── 4. GUARDAS ──────────────────────────────────────────────────────────────
# Vía incremental: el grafo debe CRECER un poco. Si baja, o si más que se duplica
# (>1,3x), se RESTAURA y se reporta: nunca dejar el grafo dañado en silencio.
# El tope fijo de 1,3× solo vale para incrementos pequeños: con un atraso de N notas
# legítimas (p.ej. 16 notas tras 5 días caído) el grafo crece mucho más y la guarda
# lo confundía con duplicación (19-oct: 449→777 rechazado y grafo restaurado).
# El techo correcto es "lo que la propia extracción produjo" + margen: una
# duplicación real suma además el grafo viejo completo y lo supera.
XN=0
if [ -n "${WORK:-}" ] && [ -f "${WORK}/graphify-out/graph.json" ]; then
  XN=$("${PY_YAML:-python3}" -c "import json;print(len(json.load(open('${WORK}/graphify-out/graph.json')).get('nodes',[])))" 2>/dev/null || echo 0)
fi
case "$XN" in ''|*[!0-9]*) XN=0 ;; esac
LIM=$((N0 + XN + (N0 * 10 / 100) + 10))
if [ "$MODE" = "inc" ] && { [ "$N1" -lt "$N0" ] || [ "$N1" -gt "$LIM" ]; }; then
  cp "$PRE" "$G" 2>/dev/null || cp "$BAK" "$G" 2>/dev/null || true
  echo "EXTRACT_ERROR: incremento anómalo ($N0 -> $N1 nodos; extracción produjo $XN; tope $LIM); grafo restaurado a $N0"
  tail -3 "$LOG" 2>/dev/null
  exit 1
fi
if [ "$MODE" = "full" ] && [ "$N1" -lt "$((N0 / 2))" ]; then
  echo "AVISO: el modo completo dejó $N0 -> $N1 nodos (caída >50%): revisar antes de confiar en el grafo"
fi

COST=$(grep -hoE 'est\. cost \(~[a-z]+\): \$[0-9.]+' \
        /opt/hermes-agent-data/brain/graphify_inc.log /opt/hermes-agent-data/brain/graphify_full.log 2>/dev/null | tail -1)

# ── 5. Reflect: LESSONS.md determinista (sin LLM) desde los resultados guardados ─
# Alimentado por `graphify save-result` (lo usa el agente al consultar el grafo).
if [ -d /opt/hermes-agent-data/brain/graphify-out-v2/memory ]; then
  /usr/local/bin/graphify reflect \
    --memory-dir /opt/hermes-agent-data/brain/graphify-out-v2/memory \
    --out /opt/hermes-agent-data/brain/graphify-out-v2/reflections/LESSONS.md \
    --graph "$G" >> "$LOG" 2>&1 || true
fi

mv -f "$MANIFEST.new" "$MANIFEST" 2>/dev/null || true

# ── 6. Capa semántica: indexar embeddings (nan qwen3-embedding) ──────────────
# No-fatal: si falla, el grafo y la búsqueda literal siguen intactos. Coste de
# embeddings ínfimo y solo incremental (por sha1 del texto).
echo "[brain-graph] embeddings (capa semántica)..."
/usr/bin/python3 /opt/data/tools/embed_brain.py index >> "$LOG" 2>&1 || \
  echo "[brain-graph] AVISO: indexado de embeddings falló (no crítico)"

echo "[brain-graph] OK — $NCH nota(s) procesada(s) ${COST:+· $COST}"
echo "nodes before=$N0 after=$N1 ${COST:+| $COST}"
rm -f "$BAK" 2>/dev/null
exit 0
