#!/usr/bin/env bash
# run_rendicion.sh — orquestador de la rendición de cuentas mensual
# (Golden Game + The Grand Paradise Club · Lucky Brothers).
#
# Modos:
#   --dry-run  (default): consolida facts del mes anterior (fuentes reales; lo que
#              no se obtiene queda {"sin_dato": true}), valida estructura contra el
#              schema de octubre, valida docs y pipeline de videos SIN gastar TTS
#              ni renderizar, copia lo producido a STAGING local y notifica a
#              Discord (canal de ops) para revisión de Plon.
#   --full:    pipeline completo (docs DOCX+PDF + videos V2). Sigue copiando a
#              STAGING y notificando; NO sube nada a Drive ni envía al cliente.
#
# GATE HUMANO DE PUBLICACIÓN: la única vía de subir a Drive es
#   APPROVED=1 run_rendicion.sh --full --upload-drive
# Plon la ejecuta a mano después de revisar el staging de un dry-run/full exitoso.
#
# Salida del mes: /opt/hermes-agent-data/home/proyectos/rendicion-mensual/<YYYY-MM>/
set -euo pipefail
# resolver ruta absoluta real (el cron puede invocar con ruta relativa a /opt/data/scripts)
SELF="$(readlink -f "${BASH_SOURCE[0]:-$0}")"
DIR="$(cd "$(dirname "$SELF")" && pwd)"
# shellcheck source=config.env
source "$DIR/config.env"

MODE="dry"
MES=""
UPLOAD=0
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) MODE="dry"; shift;;
    --full) MODE="full"; shift;;
    --mes) MES="$2"; shift 2;;
    --upload-drive) UPLOAD=1; shift;;
    --facts-golden) OVERRIDE_FG="$2"; shift 2;;
    --facts-lucky) OVERRIDE_FL="$2"; shift 2;;
    --no-discord) NO_DISCORD=1; shift;;
    *) echo "arg desconocido: $1"; exit 64;;
  esac
done

# mes anterior (America/Bogota) por defecto: el cron corre el día 1
MES="${MES:-$(TZ=$TZ date -d 'first day of this month - 1 day' +%Y-%m)}"
RUNDIR="$RENDICION_BASE/$MES"
mkdir -p "$RUNDIR/facts" "$RUNDIR/docs" "$RUNDIR/videos" "$RUNDIR/staging" "$RUNDIR/logs"
LOG="$RUNDIR/logs/run_$(date +%Y%m%d_%H%M%S)_$MODE.log"
exec > >(tee -a "$LOG") 2>&1

echo "=== RENDICIÓN MENSUAL $MES · modo=$MODE · $(TZ=$TZ date '+%F %T %Z') ==="
RC=0

# ---------------------------------------------------------- 1) consolidar facts
echo "--- 1/5 consolidar facts ($MES)"
if [ -n "${OVERRIDE_FG:-}" ] && [ -n "${OVERRIDE_FL:-}" ]; then
  cp "$OVERRIDE_FG" "$RUNDIR/facts/facts_golden.json"
  cp "$OVERRIDE_FL" "$RUNDIR/facts/facts_lucky.json"
  echo "facts: OVERRIDE externo (verificación/desarrollo)"
else
  set +e
  bash "$DIR/consolidar_facts.sh" --mes "$MES" --outdir "$RUNDIR/facts" --inputs "$DIR/inputs"
  CONS_RC=$?
  set -e
  [ $CONS_RC -le 2 ] || { echo "consolidar_facts falló (rc=$CONS_RC)"; RC=$CONS_RC; }
fi

echo "--- 2/5 validar estructura facts vs schema octubre"
for f in "$RUNDIR/facts/facts_golden.json" "$RUNDIR/facts/facts_lucky.json"; do
  python3 "$DIR/validar_facts.py" --facts "$f" || RC=2
done

# ---------------------------------------------------------- 3) docs
echo "--- 3/5 documentos (plantilla del mes anterior -> python-docx + LibreOffice)"
if [ "$MODE" = "full" ]; then
  python3 "$DIR/generar_docs.py" --mes "$MES" \
    --template-golden "$TEMPLATE_GOLDEN" --template-lucky "$TEMPLATE_LUCKY" \
    --facts-golden "$RUNDIR/facts/facts_golden.json" \
    --facts-lucky "$RUNDIR/facts/facts_lucky.json" \
    --facts-prev-golden "$PREV_FACTS_GOLDEN" --facts-prev-lucky "$PREV_FACTS_LUCKY" \
    --outdir "$RUNDIR/docs" || RC=2
else
  echo "(dry-run: sólo plan; los DOCX/PDF reales se generan en --full o a mano)"
  python3 "$DIR/generar_docs.py" --mes "$MES" \
    --template-golden "$TEMPLATE_GOLDEN" --template-lucky "$TEMPLATE_LUCKY" \
    --facts-golden "$RUNDIR/facts/facts_golden.json" \
    --facts-lucky "$RUNDIR/facts/facts_lucky.json" \
    --outdir "$RUNDIR/docs" --dry-run || RC=2
fi

# ---------------------------------------------------------- 4) videos
echo "--- 4/5 videos (pipeline V2)"
if [ "$MODE" = "full" ]; then
  bash "$DIR/generar_videos.sh" --mes "$MES" --rundir "$RUNDIR" --full || RC=2
else
  # datos de octubre reales como muestra; cero TTS, cero renders
  bash "$DIR/generar_videos.sh" --mes "$MES" --rundir "$RUNDIR" --dry-run || RC=2
fi

# ---------------------------------------------------------- 5) staging + Discord
echo "--- 5/5 staging local + notificación"
RESUMEN="$RUNDIR/staging/resumen_rendicion_$MES.md"
python3 - "$MES" "$MODE" "$RUNDIR" "$RESUMEN" <<'EOF'
import json, sys, os
mes, mode, rundir, out = sys.argv[1:5]
lines = [f"Rendición de cuentas · {mes} · modo {mode}", ""]
for brand in ("golden", "lucky"):
    p = os.path.join(rundir, "facts", f"facts_{brand}.json")
    if not os.path.exists(p):
        lines.append(f"· {brand}: SIN facts"); continue
    F = json.load(open(p, encoding="utf-8"))
    nsd = [c["id"] for c in F["cifras"] if c.get("sin_dato")]
    lines.append(f"· {F['marca']} — cifras {len(F['cifras'])} ({len(nsd)} sin_dato)"
                 + (f": {', '.join(nsd)}" if nsd else "") +
                 f" · sedes {len(F['sedes'])}")
    vn = next((c for c in F["cifras"] if c["id"] == "ventas_netas"), None)
    if vn and not vn.get("sin_dato"):
        lines.append(f"   ventas_netas: {vn['display']}")
lines += ["", f"Staging: {rundir}/staging",
          "Pendiente de revisión (Plon) antes de subir a Drive / enviar al cliente.",
          "Gate de publicación: APPROVED=1 run_rendicion.sh --full --upload-drive"]
open(out, "w", encoding="utf-8").write("\n".join(lines) + "\n")
print("\n".join(lines))
EOF

# copia (no publica) de entregables al staging
cp -f "$RUNDIR/facts/"*.json "$RUNDIR/staging/" 2>/dev/null || true
cp -f "$RUNDIR/docs/"*.docx "$RUNDIR/docs/"*.pdf "$RUNDIR/staging/" 2>/dev/null || true
cp -f "$RUNDIR/videos/"*.mp4 "$RUNDIR/staging/" 2>/dev/null || true
echo "staging: $RUNDIR/staging/ ($(ls "$RUNDIR/staging" | wc -l) archivos)"

if [ "${NO_DISCORD:-0}" != "1" ]; then
  if [ "$MODE" = "dry" ]; then
    python3 "$DIR/notify_discord.py" \
      --title "🧾 Rendición $MES — dry-run listo para revisión (Plon)" \
      --body-file "$RESUMEN" || RC=2
  else
    python3 "$DIR/notify_discord.py" \
      --title "🧾 Rendición $MES — entregables completos en staging (Plon)" \
      --body-file "$RESUMEN" || RC=2
  fi
fi

# ---------------------------------------------------------- GATE: subida a Drive
if [ "$UPLOAD" -eq 1 ]; then
  if [ "${APPROVED:-0}" != "1" ]; then
    echo "GATE HUMANO: --upload-drive sin APPROVED=1 → NO se sube nada."
    echo "  Para publicar: APPROVED=1 run_rendicion.sh --full --upload-drive --mes $MES"
  else
    echo "APPROVED=1 → subida a Drive (<Cliente>/05-informes/rendicion-de-cuentas/$MES/)"
    bash "$DIR/upload_drive.sh" --mes "$MES" --staging "$RUNDIR/staging" || RC=2
  fi
fi

echo "=== FIN rc=$RC · log: $LOG ==="
exit $RC
