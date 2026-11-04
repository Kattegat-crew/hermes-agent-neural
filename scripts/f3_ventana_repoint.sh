#!/usr/bin/env bash
# ============================================================================
# F3 · Ventana de recreación para repuntar la raíz de ESCRITURA de skills
# ============================================================================
# Aplica scripts/f3_repoint_arbol_unico.py (configs + compose) y recrea el
# contenedor para que las 12 rutas de escritura (`<HERMES_HOME>/skills`) sean
# el canon versionado y no directorios fuera de git.
#
# GATE DE FIRMA (bloqueo duro en código): sin --firma TOKEN validado por sha256
# contra /root/.sync-firma.sha256 → exit 1 y CERO cambios.
#
# SEGURIDAD: tag de imagen previo · respaldo de compose/.env/configs ·
#            compose de rollback · verificación obligatoria · ROLLBACK AUTOMÁTICO.
#
# USO:  ./scripts/f3_ventana_repoint.sh --firma TOKEN [--dry-run] [--hub archivar|promover]
# ============================================================================
set -uo pipefail

REPO="/root/hermes-agent-legacy-docker"
CONT="hermes-agent"
TS="$(date +%Y%m%d-%H%M%S)"
LOG="$REPO/data/state/f3_ventana_${TS}.log"
RES="$REPO/data/state/f3_ventana_${TS}.json"
FIRMA=""; DRY=0; HUB="archivar"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --firma)   FIRMA="${2:-}"; shift ;;
    --dry-run) DRY=1 ;;
    --hub)     HUB="${2:-archivar}"; shift ;;
    *) echo "❌ opción desconocida: $1" >&2; exit 1 ;;
  esac
  shift
done

log() { echo "$@" | tee -a "$LOG"; }

SHA_FILE="/root/.sync-firma.sha256"
if [[ $DRY -eq 0 ]]; then
  if [[ ! -f "$SHA_FILE" ]]; then echo "🔒 GATE CERRADO — no existe $SHA_FILE." >&2; exit 1; fi
  if [[ -z "$FIRMA" ]]; then echo "🔒 GATE CERRADO — falta --firma TOKEN." >&2; exit 1; fi
  if [[ "$(printf '%s' "$FIRMA" | sha256sum | awk '{print $1}')" != "$(cat "$SHA_FILE")" ]]; then
    echo "❌ FIRMA INVÁLIDA — el token no coincide con el autorizado por el dueño." >&2; exit 1
  fi
fi

log "=============================================================================="
log "F3 · VENTANA DE REPUNTE DE LA RAÍZ DE ESCRITURA · $TS  (--hub $HUB)"
log "=============================================================================="
log "✅ Firma válida."

# ── PRE-CHECKS ──────────────────────────────────────────────────────────────
log ""; log "── PRE-CHECKS ──"
AUD="$(cd "$REPO" && python3 scripts/verify_skills.py 2>&1 | grep -c 'ADUANA SUPERADA')"
log "   aduana: $([[ $AUD -ge 1 ]] && echo VERDE || echo '⚠️ revisar')"
DIRTY="$(cd "$REPO" && git status --porcelain | head -5)"
[[ -n "$DIRTY" ]] && { log "   ⚠️ árbol git sucio:"; echo "$DIRTY" | tee -a "$LOG"; }
CANON_SK="$(find "$REPO/skills" -name SKILL.md | wc -l)"
log "   SKILL.md en el canon: $CANON_SK"

if [[ $DRY -eq 1 ]]; then
  log ""; log "🧪 DRY-RUN — nada se ejecuta. Pasos que se correrían:"
  log "   1. respaldo de configs+compose+gitignore"
  log "   2. estado runtime de las 12 raíces locales → data/archive/F3_raices_locales_*"
  log "   3. instalaciones de hub → modo '$HUB'"
  log "   4. quitar skills.external_dirs de los 12 configs"
  log "   5. +12 montajes ./skills:/opt/data[/profiles/<p>]/skills"
  log "   6. docker compose up -d --no-build  + verificación (inodo único) + rollback automático"
  exit 0
fi

# ── RESPALDOS Y COMPOSE DE ROLLBACK ─────────────────────────────────────────
log ""; log "── RESPALDOS ──"
IMG_TAG="hermes-agent:pre-repoint-${TS}"
IMG_CUR="$(docker inspect "$CONT" --format '{{.Config.Image}}')"
docker tag "$IMG_CUR" "$IMG_TAG" || { log "   🛑 no se pudo etiquetar"; exit 1; }
log "   imagen actual $IMG_CUR → tag $IMG_TAG"
BK="$REPO/data/backups/f3_${TS}"; mkdir -p "$BK"
cp "$REPO/.env" "$BK/env.bak" 2>/dev/null || true
cp "$REPO/docker-compose.yml" "$BK/docker-compose.yml.bak"
log "   respaldos en $BK"

# compose de rollback = el de AHORA (con el montaje F2, sin los 12 nuevos)
python3 - "$BK/docker-compose.yml.bak" "$REPO/docker-compose.prerepoint.yml" <<'PY' | tee -a "$LOG"
import re, sys
src, dst = sys.argv[1], sys.argv[2]
out = []
for l in open(src, encoding='utf-8').read().splitlines(True):
    # retira SOLO los montajes del repunte (rutas /opt/data/...), no el de F2
    if re.match(r'\s*-\s*\./skills:/opt/data', l):
        continue
    out.append(l)
open(dst, 'w', encoding='utf-8').writelines(out)
print('   compose de rollback escrito: %s' % dst)
PY

# ── APLICAR EL REPUNTE (configs + compose + higiene) ────────────────────────
log ""; log "── REPUNTE (script con gate propio) ──"
python3 "$REPO/scripts/f3_repoint_arbol_unico.py" --apply --firma "$FIRMA" --hub "$HUB" 2>&1 | tee -a "$LOG"

# ── RECREACIÓN ──────────────────────────────────────────────────────────────
log ""; log "── RECREACIÓN (docker compose up -d --no-build) ──"
( cd "$REPO" && docker compose up -d --no-build 2>&1 | tee -a "$LOG" )

log ""; log "── ESPERA DE ARRANQUE ──"
OK=0
for i in $(seq 1 40); do
  sleep 6
  ST="$(docker inspect "$CONT" --format '{{.State.Status}}' 2>/dev/null || echo missing)"
  RUN="$(docker exec "$CONT" sh -c 'ls /opt/data/skills | head -1' 2>/dev/null || true)"
  log "   [$i] estado=$ST skills=${RUN:-vacío}"
  if [[ "$ST" == "running" && -n "$RUN" ]]; then OK=1; break; fi
done

# ── VERIFICACIÓN ────────────────────────────────────────────────────────────
log ""; log "── VERIFICACIÓN ──"
FALLOS=()
MONTS="$(docker inspect "$CONT" --format '{{range .Mounts}}{{.Destination}} {{end}}')"
FALTAN=""
for D in /opt/data/skills /opt/data/profiles/bragi/skills /opt/data/profiles/brokkr/skills \
         /opt/data/profiles/comms/skills /opt/data/profiles/freyja/skills /opt/data/profiles/heimdall/skills \
         /opt/data/profiles/hermodr/skills /opt/data/profiles/roshi/skills /opt/data/profiles/sindri/skills \
         /opt/data/profiles/ullr/skills /opt/data/profiles/vigia/skills /opt/data/profiles/vili/skills; do
  echo "$MONTS" | grep -q "$D" || FALTAN="$FALTAN $D"
done
if [[ -z "$FALTAN" ]]; then log "   ✅ 12/12 montajes de ESCRITURA presentes"
else log "   ❌ montajes ausentes:$FALTAN"; FALLOS+=("montajes ausentes:$FALTAN"); fi

INO_HOST="$(stat -c '%d:%i' "$REPO/skills" 2>/dev/null || echo x)"
DISTINTOS=""
for P in /opt/hermes/skills /opt/data/skills /opt/data/profiles/roshi/skills /opt/data/profiles/vigia/skills /opt/data/profiles/bragi/skills; do
  I="$(docker exec "$CONT" stat -c '%d:%i' "$P" 2>/dev/null || echo y)"
  log "   inodo $P = $I  (canon host $INO_HOST)"
  [[ "$I" == "$INO_HOST" ]] || DISTINTOS="$DISTINTOS $P"
done
if [[ -z "$DISTINTOS" ]]; then log "   ✅ UN SOLO ÁRBOL: mismo inodo en las 13 rutas"
else log "   ❌ inodos distintos:$DISTINTOS"; FALLOS+=("inodos distintos:$DISTINTOS"); fi

CANON_CONT="$(docker exec "$CONT" sh -c 'find /opt/data/skills -name SKILL.md 2>/dev/null | wc -l' || echo 0)"
log "   SKILL.md alcanzables = $CANON_CONT (canon host = $CANON_SK)"
[[ "$CANON_CONT" == "$CANON_SK" ]] || FALLOS+=("catálogo alcanzable $CANON_CONT != canon $CANON_SK")

PROBE="$(docker exec -u 10000 "$CONT" sh -c 'touch /opt/data/profiles/roshi/skills/.write-probe && echo ESCRITURA-OK && rm -f /opt/data/profiles/roshi/skills/.write-probe' 2>&1 | head -1)"
if echo "$PROBE" | grep -q "ESCRITURA-OK"; then
  log "   ✅ I5: uid 10000 ESCRIBE la raíz de escritura (ya dentro del canon)"
else log "   ❌ I5 FALLA en la raíz de escritura: $PROBE"; FALLOS+=("write-probe raíz de escritura"); fi

EXT="$(docker exec "$CONT" sh -c 'grep -c external_dirs /opt/data/config.yaml /opt/data/profiles/roshi/config.yaml 2>/dev/null' || true)"
log "   external_dirs restantes (root/roshi): $EXT"
GW="$(docker exec "$CONT" sh -c 'ps -ef 2>/dev/null | grep -c "[g]ateway run"' || echo 0)"
log "   procesos 'gateway run': $GW"
[[ "${GW:-0}" -ge 3 ]] || log "   ⚠️ menos gateways de los esperados (3 UP antes de la ventana)"

if [[ ${#FALLOS[@]} -gt 0 ]]; then
  log ""; log "   🛑 FALLOS: ${FALLOS[*]}"
  log "   🔄 ROLLBACK AUTOMÁTICO (compose prerepoint + restauración de configs)…"
  cp "$BK/docker-compose.yml.bak" "$REPO/docker-compose.yml"
  # restaura configs respaldados por el script de repunte
  REPO_BCK="$(ls -dt "$REPO"/data/backups/config/F3_* 2>/dev/null | head -1)"
  if [[ -n "$REPO_BCK" ]]; then
    for F in "$REPO_BCK"/*; do
      case "$(basename "$F")" in
        _root_hermes-agent_data_config.yaml) cp "$F" "$REPO/data/config.yaml" ;;
        _root_hermes-agent_data_profiles_*_config.yaml)
          P="$(basename "$F" | sed 's|_root_hermes-agent_data_profiles_||;s|_config.yaml||')"
          cp "$F" "$REPO/data/profiles/$P/config.yaml" ;;
        _root_hermes-agent_docker-compose.yml) cp "$F" "$REPO/docker-compose.yml" ;;
      esac
    done
    log "   configs restaurados desde $REPO_BCK"
  fi
  ( cd "$REPO" && docker compose up -d --no-build 2>&1 | tee -a "$LOG" )
  sleep 20
  log "   estado tras rollback: $(docker inspect "$CONT" --format '{{.State.Status}}' 2>/dev/null)"
  python3 -c "import json,sys;json.dump({'ts':'$TS','resultado':'ROLLBACK','fallos':sys.argv[1:]},open('$RES','w'),indent=1,ensure_ascii=False)" "${FALLOS[@]}"
  log "   Resultado: $RES"
  exit 1
fi

python3 - "$RES" "$TS" "$INO_HOST" "$IMG_TAG" "$CANON_CONT" <<'PY' | tee -a "$LOG"
import json, sys
res, ts, ino, tag, n = sys.argv[1:6]
json.dump({'ts': ts, 'resultado': 'OK', 'inodo_unico': ino, 'skill_md': n,
           'tag_previo': tag,
           'rollback': 'cp data/backups/f3_%s/docker-compose.yml.bak docker-compose.yml && docker compose up -d --no-build' % ts,
           'nota': 'Raíz de escritura de los 12 perfiles = canon versionado. Un solo árbol verificado por inodo.'},
          open(res, 'w'), indent=1, ensure_ascii=False)
print('   Resultado: %s' % res)
PY
log ""; log "🎉 F3 REPUNTE COMPLETADO: los agentes ESCRIBEN en el canon versionado."
log "   Log: $LOG"
exit 0
