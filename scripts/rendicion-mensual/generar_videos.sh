#!/usr/bin/env bash
# generar_videos.sh — orquesta el pipeline V2 de rendición (el mismo de octubre 2026):
#   guion desde facts → locución ElevenLabs (gated) → timeline audio-first
#   → render 16:9 + reel 9:16 → mix (loudnorm -16 LUFS) → verify_v2.
#
# uso: generar_videos.sh --mes YYYY-MM --rundir DIR [--dry-run] [--reuse-audio-oct DIR]
#
# --dry-run: valida facts, valida el guion generado, verifica herramientas y
#   locuciones existentes (muestra de octubre), estima el costo TTS contra el tope
#   mensual y NO llama a ElevenLabs ni ejecuta renders.
# --full:    pipeline completo. Requiere además TTS_APPROVED=1 para gastar ElevenLabs
#            (gate humano). El tope $2/mes se impone en tts_elevenlabs.py.
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
OCT="/opt/hermes-agent-data/home/proyectos/videos-rendicion-oct2026"
MES=""
RUNDIR=""
DRY_RUN=1

while [ $# -gt 0 ]; do
  case "$1" in
    --mes) MES="$2"; shift 2;;
    --rundir) RUNDIR="$2"; shift 2;;
    --dry-run) DRY_RUN=1; shift;;
    --full) DRY_RUN=0; shift;;
    --reuse-audio-oct) REUSE_OCT="$2"; shift 2;;
    *) echo "arg desconocido: $1"; exit 64;;
  esac
done
[ -n "$MES" ] || { echo "falta --mes YYYY-MM"; exit 64; }
RUNDIR="${RUNDIR:-/opt/hermes-agent-data/home/proyectos/rendicion-mensual/$MES}"
FG="$RUNDIR/facts/facts_golden.json"
FL="$RUNDIR/facts/facts_lucky.json"
WORK="$RUNDIR/videos_work"
mkdir -p "$WORK"

FAIL=0
say(){ echo "[videos] $*"; }
fail(){ echo "[videos][FALLO] $*"; FAIL=1; }

# ---------------------------------------------------------------- 1) datos
say "1/6 validando facts ($MES)"
[ -f "$FG" ] || { fail "no existe $FG"; }
[ -f "$FL" ] || { fail "no existe $FL"; }
if [ "$FAIL" -eq 0 ]; then
  for f in "$FG" "$FL"; do
    out=$(python3 "$DIR/validar_facts.py" --facts "$f" || true)
    echo "$out"
    echo "$out" | grep -q "ESTRUCTURA INVALIDA" && fail "estructura de facts inválida: $f"
  done
  # gate: los beats de video exigen las cifras clave consolidadas
  for cid in ventas_netas meta_ventas cumplimiento breb_total ads_total; do
    if python3 - "$FG" "$FL" "$cid" <<'EOF'
import json, sys
missing = any(
    (c.get("sin_dato") or "valor" not in c)
    for F in (json.load(open(sys.argv[1])), json.load(open(sys.argv[2])))
    for c in F["cifras"] if c["id"] == sys.argv[3])
sys.exit(1 if missing else 0)
EOF
    then :; else fail "campo '$cid' sin dato en alguna marca → los videos NO se renderizan (nada se inventa)"; fi
  done
fi

# ---------------------------------------------------------------- 2) guion
say "2/6 generando guion desde facts"
if [ "$FAIL" -eq 0 ]; then
  if ! python3 "$DIR/gen_guion.py" --mes "$MES" --facts-golden "$FG" --facts-lucky "$FL" \
        --outdir "$WORK/v2build"; then
    fail "guion con campos sin dato (bloqueante para TTS)"
  fi
  CHARS=$(python3 -c "
import json; l=json.load(open('$WORK/v2build/locuciones.json'))
print(sum(len(b['voz']) for b in l['golden']+l['paradise']))" 2>/dev/null || echo "?")
  say "   TTS estimado: $CHARS chars ≈ \$$(python3 -c "print(round($CHARS/1000*0.18,2))" 2>/dev/null || echo '?') (tope mensual \$2.00 en tts_elevenlabs.py)"
fi

# ---------------------------------------------------------------- 3) herramientas
say "3/6 verificando herramientas del pipeline V2"
for tool in ffmpeg ffprobe node; do
  command -v $tool >/dev/null || fail "falta $tool"
done
for f in "$OCT/v2/render/render.js" "$OCT/v2/render/compose.js" "$OCT/v2/render/engine.js" \
         "$OCT/v2/render/index.html" "$OCT/v2/gen_timeline.py" "$OCT/v2/gen_captions.py" \
         "$OCT/v2/mix_v2.py" "$OCT/v2/assemble_v2.sh" "$OCT/v2/verify_v2.py" \
         "$OCT/audio/music_golden.mp3" "$OCT/audio/music_paradise.mp3" \
         "$OCT/audio/sfx_whoosh.mp3" "$OCT/audio/sfx_chime.mp3"; do
  [ -e "$f" ] || fail "falta pieza del pipeline V2: $f"
done
[ -e "$OCT/v2/render/node_modules" ] || fail "falta node_modules del render (puppeteer)"

# ---------------------------------------------------------------- 4) locuciones
say "4/6 locuciones"
REUSE_DIR="${REUSE_OCT:-$OCT/v2/voz}"
if [ "$DRY_RUN" -eq 1 ]; then
  # muestra de octubre: se VALIDAN, no se regeneran (cero gasto TTS)
  N_OK=0
  for b in golden paradise; do
    for i in 01 02 03 04 05 06 07 08 09; do
      w="$REUSE_DIR/${b}_b${i}.wav"
      if [ -f "$w" ] && ffprobe -v error -show_entries format=duration -of csv=p=0 "$w" >/dev/null 2>&1; then
        N_OK=$((N_OK+1))
      fi
    done
  done
  [ "$N_OK" -eq 18 ] && say "   18/18 locuciones de muestra ($REUSE_DIR) legibles con ffprobe" \
                        || fail "muestra de locuciones incompleta ($N_OK/18)"
  say "   DRY-RUN: NO se llama a ElevenLabs. En --full se usa Angie/Daniela (eleven_multilingual_v2), tope \$2/mes con MANIFEST."
else
  [ "${TTS_APPROVED:-0}" = "1" ] || { fail "full mode sin TTS_APPROVED=1 (gate humano de gasto)"; }
  if [ "$FAIL" -eq 0 ]; then
    mkdir -p "$WORK/voz"
    python3 "$DIR/tts_elevenlabs.py" --mes "$MES" \
      --locuciones "$WORK/v2build/locuciones.json" --outdir "$WORK/voz"
  fi
fi

# ---------------------------------------------------------------- 5) plan de render
say "5/6 plan de render (16:9 + 9:16 por marca)"
say "   workdir: $WORK"
say "   piezas: piece_golden_169.mp4 piece_golden_916.mp4 piece_paradise_169.mp4 piece_paradise_916.mp4"
say "   QA: verify_v2.py (LUFS -16±1, OCR por beat, safe-area, sincronía voz-pantalla)"

if [ "$DRY_RUN" -eq 0 ] && [ "$FAIL" -eq 0 ]; then
  # ---------------------------------------------------------------- 6) render real
  say "6/6 ejecutando pipeline V2"
  mkdir -p "$WORK/v2" "$WORK/audio"
  cp -r "$OCT/v2/render" "$WORK/v2/render" 2>/dev/null || true
  cp "$OCT/v2/gen_timeline.py" "$OCT/v2/gen_captions.py" "$OCT/v2/mix_v2.py" \
     "$OCT/v2/assemble_v2.sh" "$OCT/v2/verify_v2.py" "$WORK/v2/"
  cp "$OCT/audio/music_golden.mp3" "$OCT/audio/music_paradise.mp3" \
     "$OCT/audio/sfx_whoosh.mp3" "$OCT/audio/sfx_chime.mp3" "$WORK/audio/"
  cp "$FG" "$WORK/facts_golden.json"; cp "$FL" "$WORK/facts_lucky.json"
  # parametrizar los W= hardcodeados de los scripts V2 hacia el workdir del mes
  grep -rl 'videos-rendicion-oct2026' "$WORK/v2" --include='*.py' | while read -r f; do
    sed -i "s#$OCT#$WORK#g" "$f"
  done
  cp "$WORK/v2build/cards_golden.json" "$WORK/v2/build/cards_golden.json" 2>/dev/null || { mkdir -p "$WORK/v2/build"; cp "$WORK/v2build/cards_golden.json" "$WORK/v2/build/cards_golden.json"; }
  cp "$WORK/v2build/cards_paradise.json" "$WORK/v2/build/cards_paradise.json"
  cp "$WORK/v2build/locuciones.json" "$WORK/v2/locuciones.json"
  mkdir -p "$WORK/v2/voz"; cp "$WORK/voz/"*.wav "$WORK/v2/voz/" 2>/dev/null || true
  python3 "$WORK/v2/gen_captions.py" || true
  python3 "$WORK/v2/gen_timeline.py"
  for b in golden paradise; do
    python3 "$WORK/v2/mix_v2.py" "$b" 169
    python3 "$WORK/v2/mix_v2.py" "$b" 916
    bash "$WORK/v2/assemble_v2.sh" "$b" 169 "$WORK/v2/build/mix_${b}_169/audio_final.m4a"
    bash "$WORK/v2/assemble_v2.sh" "$b" 916 "$WORK/v2/build/mix_${b}_916/audio_final.m4a"
  done
  python3 "$WORK/v2/verify_v2.py" || fail "verify_v2 reportó fallos de QA"
  mkdir -p "$RUNDIR/videos"
  cp "$WORK/v2/build/piece_"*.mp4 "$RUNDIR/videos/" 2>/dev/null || true
  say "   piezas en $RUNDIR/videos/"
fi

if [ "$FAIL" -ne 0 ]; then
  echo "[videos] RESULTADO: FALLO (ver líneas FALLO arriba)"
  exit 1
fi
if [ "$DRY_RUN" -eq 1 ]; then
  echo "[videos] RESULTADO: DRY-RUN OK — datos y pipeline validados, sin gasto TTS ni renders"
else
  echo "[videos] RESULTADO: PIPELINE COMPLETO"
fi
