#!/usr/bin/env bash
set -euo pipefail

SCREENSHOT_DIR="${1:-docs/screenshots}"
AUDIO="${2:-.local/demo/model-observability-judge-demo.mp3}"
OUTPUT="${3:-docs/demo/model-observability-judge-demo.mp4}"
SUBTITLES="${4:-.local/demo/model-observability-judge-demo.srt}"

command -v ffmpeg >/dev/null || { echo "ffmpeg is required" >&2; exit 1; }
test -f "$AUDIO" || { echo "Missing narration: run make demo-voice" >&2; exit 1; }
test -f "$SUBTITLES" || { echo "Missing subtitles: run make demo-voice" >&2; exit 1; }
for screenshot in dashboard.png dashboard-recovery.png dashboard-delivery.png dashboard-mobile.png; do
  test -f "$SCREENSHOT_DIR/$screenshot" || { echo "Missing screenshot: $screenshot" >&2; exit 1; }
done

mkdir -p "$(dirname "$OUTPUT")"
ffmpeg -y \
  -loop 1 -t 69 -i "$SCREENSHOT_DIR/dashboard.png" \
  -loop 1 -t 77 -i "$SCREENSHOT_DIR/dashboard-recovery.png" \
  -loop 1 -t 61 -i "$SCREENSHOT_DIR/dashboard-delivery.png" \
  -loop 1 -t 51 -i "$SCREENSHOT_DIR/dashboard-mobile.png" \
  -i "$AUDIO" \
  -i "$SUBTITLES" \
  -filter_complex \
    "[0:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=#f5f7fa,fps=30,format=yuv420p[v0]; \
     [1:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=#f5f7fa,fps=30,format=yuv420p[v1]; \
     [2:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=#f5f7fa,fps=30,format=yuv420p[v2]; \
     [3:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=#f5f7fa,fps=30,format=yuv420p[v3]; \
     [v0][v1]xfade=transition=fade:duration=1:offset=68[x01]; \
     [x01][v2]xfade=transition=fade:duration=1:offset=144[x012]; \
     [x012][v3]xfade=transition=fade:duration=1:offset=204,format=yuv420p[video]; \
     [4:a]loudnorm=I=-16:TP=-1.5:LRA=11[audio]" \
  -map "[video]" -map "[audio]" -map 5:s:0 \
  -c:v libx264 -profile:v high -crf 20 \
  -c:a aac -b:a 160k -ar 48000 \
  -c:s mov_text -metadata:s:s:0 language=eng \
  -movflags +faststart -shortest "$OUTPUT"
echo "$OUTPUT"
