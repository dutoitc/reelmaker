#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ARCHIVE="$ROOT_DIR/reelmaker.tgz"
PARENT_DIR="$(dirname "$ROOT_DIR")"
TEMP_ARCHIVE="$(mktemp "$PARENT_DIR/reelmaker.XXXXXX.tgz")"

trap 'rm -f "$TEMP_ARCHIVE"' EXIT
rm -f "$ARCHIVE"

tar \
  --exclude='./.git' \
  --exclude='./.github/.cache' \
  --exclude='./.venv' \
  --exclude='./venv' \
  --exclude='./env' \
  --exclude='./build' \
  --exclude='./dist' \
  --exclude='./output' \
  --exclude='./run_*' \
  --exclude='./reelmaker.tgz' \
  --exclude='./.idea' \
  --exclude='./.vscode' \
  --exclude='./.pytest_cache' \
  --exclude='./.mypy_cache' \
  --exclude='./.ruff_cache' \
  --exclude='*/__pycache__' \
  --exclude='*.egg-info' \
  --exclude='*.pyc' \
  --exclude='*.pyo' \
  --exclude='*.log' \
  --exclude='.env' \
  --exclude='.env.*' \
  --exclude='*.mp4' \
  --exclude='*.mov' \
  --exclude='*.mkv' \
  --exclude='*.webm' \
  --exclude='*.wav' \
  --exclude='*.mp3' \
  -czf "$TEMP_ARCHIVE" \
  -C "$ROOT_DIR" .

mv "$TEMP_ARCHIVE" "$ARCHIVE"
chmod 644 "$ARCHIVE"
trap - EXIT
