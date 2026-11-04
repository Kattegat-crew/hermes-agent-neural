#!/bin/bash
# assemble-reel.sh - Assemble video clips + narration into a 9:16 vertical reel.
# Usage: ./assemble-reel.sh <clips_dir> <audio_file> <output_file>
set -euo pipefail

CLIPS_DIR="$1"
AUDIO_FILE="$2"
OUTPUT_FILE="$3"

# --- Validate args ---
[ -d "$CLIPS_DIR" ] || { echo "Error: clips directory '$CLIPS_DIR' does not exist"; exit 1; }
[ -f "$AUDIO_FILE" ] || { echo "Error: audio file '$AUDIO_FILE' does not exist"; exit 1; }
command -v ffmpeg  || { echo "Error: ffmpeg not installed"; exit 1; }
command -v ffprobe || { echo "Error: ffprobe not installed (part of ffmpeg)"; exit 1; }

echo "=== Reel Assembly ==="

# --- Find and sort clips ---
mapfile -t CLIPS < <(find "$CLIPS_DIR" -maxdepth 1 -name 'clip_*.mp4' -type f 2>/dev/null | sort)
if [ ${#CLIPS[@]} -eq 0 ]; then
  echo "Error: no clip_*.mp4 files found in $CLIPS_DIR"
  exit 1
fi

echo "Found ${#CLIPS[@]} clips:"
for i in "${!CLIPS[@]}"; do echo "  [$((i+1))] ${CLIPS[$i]}"; done

# --- Get durations ---
DURATIONS=()
for clip in "${CLIPS[@]}"; do
  dur=$(ffprobe -v error -show_entries format=duration \
        -of default=noprint_wrappers=1:nokey=1 "$clip" 2>/dev/null | tr -d ' ')
  if [ -z "$dur" ] || [ "$dur" = "N/A" ]; then dur=5; fi
  DURATIONS+=("$dur")
done

echo "Clip durations (s): ${DURATIONS[*]}"

# --- Build concat list ---
CONCAT_FILE=$(mktemp)  # cleanup handled by exec
for clip in "${CLIPS[@]}"; do echo "file '${clip}'" >> "$CONCAT_FILE"; done
echo "Created concat list: $CONCAT_FILE"

# --- Get total duration ---
TOTAL=$(printf '%s\n' "${DURATIONS[@]}" | paste -sd+ | bc)
echo "Total duration: ${TOTAL}s"

# --- Execute ffmpeg ---
mkdir -p "$(dirname "$OUTPUT_FILE")"

echo "Encoding (this may take a while)..."

ffmpeg -hide_banner -y \
  -f concat -safe 0 -i "$CONCAT_FILE" \
  -i "$AUDIO_FILE" \
  -filter_complex "[0:v]setsar=1,scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black,fade=t=in:st=0:d=1,fade=t=out:st=${TOTAL}:d=1[v]" \
  -map "[v]" -map 1:a \
  -shortest \
  -c:v libx264 -pix_fmt yuv420p -crf 18 -preset medium \
  -c:a aac -b:a 192k -ar 48000 \
  "$OUTPUT_FILE"

rm -f "$CONCAT_FILE"

echo ""
echo "Done: $OUTPUT_FILE"