#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT_NAME="reelmaker"
VERSION="$(python -c 'from reelmaker import __version__; print(__version__)')"
DIST_DIR="$ROOT_DIR/dist"
ARCHIVE="$DIST_DIR/${PROJECT_NAME}-${VERSION}.tgz"

mkdir -p "$DIST_DIR"
rm -f "$ARCHIVE"

# The archive is intentionally source-only so it can be uploaded to ChatGPT.
tar \
  --exclude='./.git' \
  --exclude='./.venv' \
  --exclude='./dist' \
  --exclude='./output' \
  --exclude='*/__pycache__' \
  --exclude='*/.pytest_cache' \
  --exclude='*/.mypy_cache' \
  --exclude='*/.ruff_cache' \
  --exclude='*/build' \
  --exclude='*.egg-info' \
  --exclude='*.pyc' \
  --exclude='*.pyo' \
  --exclude='*.mp4' \
  --exclude='*.mov' \
  --exclude='*.mkv' \
  --exclude='*.webm' \
  --exclude='*.wav' \
  --exclude='*.mp3' \
  -czf "$ARCHIVE" \
  -C "$ROOT_DIR" .

echo "$ARCHIVE"
