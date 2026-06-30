# Changelog

## 0.6.0 — 2026-06-30

- Added an optional PySide6 Windows GUI with file selection, current stage, per-stage and overall progress, elapsed time, ETA, live console logs, cancellation, and output-folder access.
- Added local multi-run timing history using median normalized durations for WhisperX, Ollama, PySceneDetect, and FFmpeg.
- Added `--composition-mode hybrid|contiguous`; hybrid candidates may combine two or three source passages into one editorial reel.
- Added typed source segments and continuous subtitle/time remapping for composite reels.
- Strengthened candidate prompts around concrete value, hooks, narrative progression, and natural endings.
- Strengthened word/cue boundary refinement and marks uncertain unfinished endings.
- Added fit-blur framing for ambiguous two-person shots and wide visuals so faces, landscapes, monuments, and slides are not destructively cropped.
- Prevented uncertain motion from forcing an arbitrary crop.
- Changed the CLI subtitle-correction default to contextual Ollama correction, with conservative basic cleanup on correction failure.
- Split long subtitles into timed cues instead of truncating text.
- Made missing subtitles and subtitle-burn failures explicit render errors unless fallback is deliberately enabled.
- Added early FFmpeg/PySceneDetect runtime checks and a non-zero failure when no reel MP4 is generated.
- Added `run_*` to `.gitignore` and excluded root local run scripts from `createTarGz.sh`.
- Added `startGui.sh`, `startGui.bat`, the `reelmaker-gui` entry point, and the `gui` optional dependency.
- Expanded the suite to 45 passing tests and validated composite/fit-blur FFmpeg rendering with synthetic media.

## 0.5.1 — 2026-06-30

- Fixed Qwen 3 candidate generation returning prose, thinking-only output, or truncated non-JSON responses.
- Disabled Ollama thinking explicitly through the API instead of relying only on `/no_think`.
- Added Ollama JSON Schema structured outputs for candidate generation, ranking, and subtitle correction.
- Forced structured requests to non-streaming mode and temperature 0 for deterministic parsing.
- Added explicit diagnostics for empty output, token-limit truncation, HTTP errors, and streaming errors.
- Expanded the suite to 36 passing tests.

## 0.5.0 — 2026-06-30

- Added lazy PySceneDetect 0.7 integration and fingerprinted `scenes.json`.
- Added the `scenes` command plus scene threshold/minimum-length controls.
- Extracted framing decisions into dedicated `framing.py`.
- Added `--crop-mode scene-smart` for one smart crop per detected shot.
- Merged similar adjacent crop decisions to limit needless segment rendering.
- Added scene-aware FFmpeg rendering with a final subtitle pass.
- Persisted the full framing plan in each reel metadata file.
- Added synthetic integration validation for cuts, distinct crops, audio, and burned subtitles.
- Expanded the suite to 34 passing tests.

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
