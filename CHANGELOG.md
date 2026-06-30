# Changelog

## 0.4.0 — 2026-06-30

- Extracted cut refinement from `analyzer.py` into dedicated `boundary.py`.
- Added word-pause boundary scoring from WhisperX timestamps.
- Combined silence, punctuation, cue boundaries and optional speaker changes.
- Added automatic cue fallback for SRT/VTT and YouTube subtitles.
- Clamped start/end padding to available silence to avoid including adjacent speech.
- Added `--boundary-mode auto|words|cues|off`.
- Added boundary method, score and reasons to candidate outputs and shortlist display.
- Added a small boundary-quality signal to local ranking.
- Expanded README with full Windows/Git Bash, FFmpeg, Ollama, CUDA and WhisperX setup.
- Expanded the suite to 26 passing tests.

## 0.3.0 — 2026-06-30

- Added direct MP4 transcription with optional local WhisperX.
- Added a `TranscriptionProvider` boundary for local subtitles, YouTube subtitles, and WhisperX.
- Added lazy WhisperX/Torch imports so the base workflow stays lightweight.
- Added transcript schema v1 with cue and word-level timing data.
- Added normalized `transcript.json`, `transcript.srt`, and `transcript.txt` outputs.
- Added source-content and transcription-settings fingerprints for cache validation.
- Added `transcribe` command and WhisperX CLI settings.
- Preserved existing SRT/YouTube auto-selection behaviour.
- Added Windows Git Bash / Python 3.11 setup documentation.
- Expanded the suite to 22 passing tests.

## 0.2.3 — 2026-06-30

- Added root `createTarGz.sh` for a complete, clean ChatGPT upload archive.
- Excluded generated output, caches, build artifacts, secrets, and local media from that archive.
- Removed personal names from documentation, license attribution, and package metadata.

## 0.2.2 — 2026-06-30

- Removed generated Python bytecode from the distributable project.
- Added `.gitignore`, `.gitattributes`, GitHub Actions tests, and dev dependencies.
- Added `scripts/check_project.sh` and `scripts/package_project.sh`.
- Added coding-assistant workflow, roadmap, and architecture guardrails.
- Aligned direct `OllamaClient` defaults with the CLI defaults.
- Reassigned candidate IDs after cached chunks are merged to prevent duplicate IDs.
- Scoped YouTube subtitle/video cache selection to the requested video ID.
- Kept basic subtitle cleanup for items omitted by an Ollama correction response.

## 0.2.1

- Smarter static vertical crop, subtitle correction, compact end cards, and safer subtitle display.

## 0.2.0

- Candidate boundary refinement, local ranking, resume/cache support, and interactive selection.
