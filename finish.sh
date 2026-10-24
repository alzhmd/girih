#!/bin/bash
# Post-process every rendered frame (titled + clean), then encode all deliverables and verify them.
set -euo pipefail
cd "$(dirname "$0")"
PY=python3
OUT=final
mkdir -p "$OUT" post/titled post/clean

# 1) post in parallel chunks (skips nothing: always regenerates for consistency)
JOBS=${JOBS:-6}
for kind in titled clean; do
  flag=""; [ "$kind" = clean ] && flag="--clean"
  seq 1 110 660 | while read a; do b=$((a+109)); [ $b -gt 660 ] && b=660; echo "$a $b"; done | \
    xargs -P "$JOBS" -L 1 bash -c "nice -n 8 $PY src/post.py \$0 \$1 $flag > /dev/null"
  n=$(ls post/$kind/p_*.png | wc -l); echo "post $kind: $n frames"; [ "$n" -eq 660 ]
done

A=audio/score.wav
CM="scale=out_color_matrix=bt709:out_range=tv"
TAGS="-colorspace bt709 -color_primaries bt709 -color_trc bt709 -color_range tv"

# 2) editing master: ProRes 422 HQ 10-bit + 24-bit PCM, native 2.39:1
ffmpeg -y -v error -framerate 30 -i post/titled/p_%04d.png -i $A -map 0:v -map 1:a \
  -vf "$CM,format=yuv422p10le" -c:v prores_ks -profile:v 3 -vendor apl0 $TAGS -c:a pcm_s24le \
  "$OUT/the-story-starts-here_master_prores.mov"
ffmpeg -y -v error -framerate 30 -i post/clean/p_%04d.png -i $A -map 0:v -map 1:a \
  -vf "$CM,format=yuv422p10le" -c:v prores_ks -profile:v 3 -vendor apl0 $TAGS -c:a pcm_s24le \
  "$OUT/the-story-starts-here_clean_prores.mov"

# 3) YouTube / sharing: 1920x1080 letterboxed H.264, closed GOP of 15 (half the frame rate)
X264="-c:v libx264 -preset slower -profile:v high -tune film -g 15 -keyint_min 15 -sc_threshold 0 -bf 2 -flags +cgop"
ffmpeg -y -v error -framerate 30 -i post/titled/p_%04d.png -i $A -map 0:v -map 1:a \
  -vf "pad=1920:1080:0:138:black,$CM,format=yuv420p" $X264 -crf 14 $TAGS \
  -c:a aac -b:a 320k -ar 48000 -movflags +faststart "$OUT/the-story-starts-here_1080p.mp4"
ffmpeg -y -v error -framerate 30 -i post/clean/p_%04d.png -i $A -map 0:v -map 1:a \
  -vf "pad=1920:1080:0:138:black,$CM,format=yuv420p" $X264 -crf 14 $TAGS \
  -c:a aac -b:a 320k -ar 48000 -movflags +faststart "$OUT/the-story-starts-here_clean_1080p.mp4"

# YouTube trick: a 1440p upload gets the better VP9/AV1 ladder even for 1080p viewers
ffmpeg -y -v error -framerate 30 -i post/titled/p_%04d.png -i $A -map 0:v -map 1:a \
  -vf "scale=2560:1072:flags=lanczos,pad=2560:1440:0:184:black,$CM,format=yuv420p" $X264 -crf 15 $TAGS \
  -c:a aac -b:a 320k -ar 48000 -movflags +faststart "$OUT/the-story-starts-here_youtube_1440p.mp4"

# 4) web (GitHub Pages): native 1920x804, streamable
ffmpeg -y -v error -framerate 30 -i post/titled/p_%04d.png -i $A -map 0:v -map 1:a \
  -vf "$CM,format=yuv420p" -c:v libx264 -preset veryslow -profile:v high -tune film -crf 20 -maxrate 14M -bufsize 28M \
  -g 60 $TAGS -c:a aac -b:a 192k -ar 48000 -movflags +faststart site/film.mp4

cp $A "$OUT/the-story-starts-here_score.wav"
ls -la "$OUT" site/film.mp4
echo FINISH-DONE
