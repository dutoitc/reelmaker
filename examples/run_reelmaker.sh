#!/usr/bin/env bash
set -euo pipefail

# Adapt these values.
YOUTUBE_URL="https://www.youtube.com/watch?v=VIDEO_ID"
SOURCE_VIDEO="/c/Users/cedric/Videos/source.mp4"
OUTPUT_DIR="output/my-video"
OLLAMA_URL="http://localhost:11434"
MODEL="qwen3:4b"
SUBTITLE_LANGS="fr.*,fr"
EPISODE_TITLE="Titre de l'episode YouTube"

# Git Bash compatible venv activation.
if [ -d ".venv" ]; then
  source .venv/Scripts/activate 2>/dev/null || source .venv/bin/activate
fi

# If accents are mojibaked in Git Bash, keep this disabled.
# export REELMAKER_UNICODE_CONSOLE=1

python -m reelmaker all \
  --youtube-url "$YOUTUBE_URL" \
  --source-video "$SOURCE_VIDEO" \
  --ollama-url "$OLLAMA_URL" \
  --model "$MODEL" \
  --subtitle-langs "$SUBTITLE_LANGS" \
  --target-count 10 \
  --shortlist-count 20 \
  --candidates-per-chunk 3 \
  --chunk-seconds 300 \
  --ranking-mode local \
  --ollama-timeout 600 \
  --ollama-num-predict 1024 \
  --min-duration 18 \
  --target-duration 22 \
  --max-duration 60 \
  --subtitle-font-size 60 \
  --subtitle-margin-v 150 \
  --subtitle-wrap-width 23 \
  --subtitle-max-lines 2 \
  --subtitle-correction basic \
  --crop-mode smart \
  --end-card-seconds 3.0 \
  --end-card-style short \
  --youtube-cta "Suite sur YouTube" \
  --end-card-comment-text "Voir commentaire" \
  --episode-title "$EPISODE_TITLE" \
  --output-dir "$OUTPUT_DIR"
