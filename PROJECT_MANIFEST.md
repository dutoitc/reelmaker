# Project manifest — Reelmaker

## Snapshot

- Version: **0.6.0**
- Status: local CLI + optional Windows GUI MVP with MP4 transcription, structured editorial analysis, composite montage, safer framing, subtitles, and progress reporting.
- Primary platform: Windows 11 + Git Bash.
- Reference runtime: Python 3.11 + NVIDIA RTX 4070 12 GB.
- Processing policy: local/offline by default.
- License: MIT.

## Product objective

Generate several usable 9:16 reels from a long-form Xplore Swiss TV video, with optional human validation before rendering.

## Current pipeline

```text
MP4/SRT/YouTube
  -> TranscriptionProvider
  -> TranscriptDocument schema v1
  -> transcript chunks
  -> Ollama continuous/composite candidate proposals
  -> pause/cue boundary refinement per source segment
  -> local or Ollama ranking
  -> human or automatic selection
  -> optional PySceneDetect shot analysis
  -> framing plan: crop or fit-blur per shot
  -> contextual subtitle correction
  -> FFmpeg segment render + concatenation + subtitle burn
  -> render report
```

The optional PySide6 GUI starts the same CLI pipeline through `QProcess`; it owns no media-processing logic.

## Stable decisions

- Windows + Git Bash remains the primary runtime.
- Processing stays local by default.
- SRT/YouTube compatibility is preserved.
- WhisperX, PySceneDetect, and PySide6 remain optional and lazily loaded where practical.
- Expensive stages use explicit caches or local timing history.
- Refactor before adding another major responsibility to `analyzer.py` or `renderer.py`.
- Render failures are explicit; no silent cloud or subtitle-free fallback.
- Root `run_*` scripts are local-only and excluded from Git/archive.

## Current defaults

- transcription: `auto`;
- WhisperX: `large-v3`, French, batch size 4;
- spoken boundaries: `auto`;
- Ollama: `qwen3:4b`, `think=false`, JSON Schema structured outputs;
- composition: `hybrid` from the CLI/GUI;
- ranking: local;
- CLI crop: `smart` for backward compatibility;
- GUI crop: `scene-smart`;
- scene detector: PySceneDetect threshold 27, minimum 15 frames;
- output: 1080x1920, H.264/AAC;
- subtitle correction: contextual Ollama by default;
- subtitle fallback without burn: disabled;
- GUI timing history: enabled under local application data.

## Version 0.6.0 delivered

- optional PySide6 desktop interface and launch scripts;
- machine-readable progress events emitted by the CLI;
- per-stage progress, logs, elapsed time, cancel support, and stage ETA in the GUI;
- multi-run timing history with median normalized samples;
- typed `ReelSegment` and hybrid composite candidates;
- composite rendering and subtitle timeline remapping;
- stronger editorial prompt and ranking signal;
- stronger natural-ending refinement and incomplete-ending warnings;
- fit-blur layout for ambiguous two-person shots and wide visuals;
- contextual Ollama subtitle correction as CLI/GUI default;
- no truncation of long subtitle text;
- explicit failure on missing subtitles, subtitle burn failure, missing render dependencies, or zero generated reels;
- 45 passing tests;
- synthetic FFmpeg validation for composite montage and fit-blur subtitles.

## Validation status

Verified in the project environment:

- compilation succeeds;
- 45 tests pass;
- source-segment persistence and continuous subtitle remapping work;
- timing history records and estimates median normalized durations;
- scene cache reuse/invalidation works;
- composite FFmpeg rendering produces a continuous vertical MP4 with audio/subtitles;
- fit-blur rendering preserves the full horizontal frame;
- subtitle burn errors do not silently produce incomplete deliverables;
- existing `center`, `face`, `motion`, `smart`, and `scene-smart` modes remain available.

Still requires Windows/Xplore validation:

- launch the GUI from `startGui.bat` and Git Bash;
- run the current Luzerne video in hybrid + scene-smart mode;
- review whether proposed composite reels are editorially coherent;
- review real two-person interviews, profiles, landscapes, slides, and monuments;
- compare corrected subtitles against the actual spoken wording;
- tune scene/crop heuristics only from observed failures.

## Accepted technical debt

1. Hybrid composition can combine passages only within one transcript analysis chunk; there is no full-program global montage pass yet.
2. Active-speaker audio-to-face localization is not implemented; ambiguous two-person shots preserve both people with fit-blur.
3. Face detection still uses a lightweight Haar cascade and can miss profiles/small faces.
4. `renderer.py` still owns subtitle/end-card generation and FFmpeg execution; refactor before music or B-roll.
5. Scene-aware/composite rendering encodes intermediate segments, which is reliable but slower.
6. No visual aesthetic or semantic relevance score yet.
7. No real GPU/Ollama integration test runs in CI.
8. The ETA is per current stage, not a guaranteed full-run completion time.

## Next strategic direction

Validate 0.6.0 on the real Luzerne footage before adding another large subsystem.

Candidate next iterations:

- active-speaker/person tracking for interviews;
- a global editorial montage pass across the full programme;
- representative-frame aesthetic and semantic scoring for beautiful views/B-roll;
- renderer extraction before music/ducking;
- improve progress granularity inside the first WhisperX run.

## Collaboration protocol

When the archive is uploaded and the user says **“on fait la suite”**:

1. read `AGENTS.md`, this manifest, roadmap, architecture, README, changelog, and tests;
2. inspect current real-run feedback and generated reports;
3. identify one coherent user-visible objective;
4. ask only strategic questions not already answered;
5. obtain objective validation before a dedicated refactor, unless immediate implementation was explicitly requested;
6. implement, test, document, and rebuild `reelmaker.tgz`.

## Useful commands

```bash
py -3.11 -m venv .venv
source .venv/Scripts/activate
python -m pip install --upgrade pip setuptools wheel
pip install -e ".[dev,vision,transcription,gui]"
bash scripts/check_project.sh
bash createTarGz.sh
```
