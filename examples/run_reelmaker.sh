#!/usr/bin/env bash
set -euo pipefail

# Adapt these values.
SOURCE_VIDEO="/c/Videos/reportage.mp4"
OUTPUT_DIR="output/reportage"
OLLAMA_URL="http://localhost:11434"
MODEL="qwen3:4b"
EPISODE_TITLE="Titre de l'episode YouTube"

# Git Bash compatible venv activation.
if [ -d ".venv" ]; then
  source .venv/Scripts/activate 2>/dev/null || source .venv/bin/activate
fi

python -m reelmaker all \
  --source-video "$SOURCE_VIDEO" \
  --transcription whisperx \
  --whisper-model "large-v3" \
  --whisper-language "fr" \
  --whisper-device "auto" \
  --whisper-batch-size 4 \
  --ollama-url "$OLLAMA_URL" \
  --model "$MODEL" \
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
  --crop-mode scene-smart \
  --scene-detection auto \
  --end-card-seconds 3.0 \
  --end-card-style short \
  --youtube-cta "Suite sur YouTube" \
  --end-card-comment-text "Voir commentaire" \
  --episode-title "$EPISODE_TITLE" \
  --output-dir "$OUTPUT_DIR"
