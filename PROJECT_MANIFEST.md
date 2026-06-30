# Project manifest — Reelmaker

## Snapshot

- Version: **0.5.0**
- Status: local CLI MVP with MP4 transcription, pause-aware spoken cuts, and optional scene-aware framing.
- Primary platform: Windows 11 + Git Bash.
- Reference runtime: Python 3.11 + NVIDIA RTX 4070 12 GB.
- Processing policy: local/offline by default.
- License: MIT.

## Product objective

Generate several usable 9:16 reels from a long-form CAPStv/Xplore Swiss TV video, with human validation before rendering.

## Current pipeline

```text
MP4/SRT/YouTube
  -> TranscriptionProvider
  -> TranscriptDocument schema v1
  -> Ollama candidate proposals
  -> pause/cue boundary refinement
  -> local or Ollama ranking
  -> human validation
  -> optional PySceneDetect shot analysis
  -> framing plan: one crop or one crop per shot
  -> subtitle correction + FFmpeg render
```

## Stable decisions

- Windows + Git Bash remains the primary runtime.
- Processing stays local by default.
- SRT/YouTube compatibility is preserved.
- WhisperX and PySceneDetect remain optional and lazily imported.
- Expensive stages use fingerprinted JSON caches.
- Human validation happens before rendering.
- One coherent feature slice per iteration.
- Refactor before adding another responsibility to `analyzer.py` or `renderer.py`.

## Current defaults

- transcription: `auto`;
- WhisperX: `large-v3`, French, batch size 4;
- spoken boundaries: `auto`;
- Ollama: `qwen3:4b`;
- ranking: local;
- crop: static `smart` for backward compatibility;
- optional improved crop: `scene-smart`;
- scene detector: PySceneDetect ContentDetector, threshold 27, minimum 15 frames;
- output: 1080x1920, H.264/AAC;
- subtitle correction: `basic`.

## Version 0.5.0 delivered

- dedicated `scene_analysis.py` adapter with lazy PySceneDetect import;
- `scenes.json` schema v1, source/settings fingerprints, and cache reuse;
- dedicated `framing.py` for static and per-shot crop decisions;
- `--crop-mode scene-smart` with smart crop recalculated for each shot;
- adjacent crops within 32 pixels merged to reduce unnecessary FFmpeg segments;
- `scenes` command and scene tuning options;
- scene-aware FFmpeg rendering with a final subtitle pass;
- framing plan persisted in each reel `metadata.json`;
- 34 passing unit tests;
- successful local integration render with three detected shots, three distinct crops, audio, and burned subtitles.

## Validation status

Verified in the project environment:

- compilation succeeds;
- 34 unit tests pass;
- PySceneDetect 0.7 detects synthetic cuts correctly;
- scene cache reuse/invalidation works;
- scene-aware rendering produces a valid vertical MP4 with audio;
- subtitle burn after scene concatenation works;
- existing `center`, `face`, `motion`, and `smart` modes remain available.

Still requires Windows/Xplore validation:

- install the full environment with Python 3.11;
- run one representative Xplore MP4 with `--crop-mode smart` and `scene-smart`;
- compare framing on interviews, monuments, landscapes, and moving subjects;
- tune `--scene-threshold` only from observed false cuts or missed cuts.

## Accepted technical debt

1. Ollama candidate/ranking caches are not fully fingerprinted by transcript, prompt and boundary version.
2. `renderer.py` still owns subtitle/end-card generation and FFmpeg execution; refactor it before music or B-roll.
3. Scene-aware rendering encodes each shot separately, then performs a final subtitle pass; reliable but slower.
4. Face detection still uses a lightweight Haar cascade and can miss profiles or small faces.
5. No visual aesthetic or semantic relevance score yet.
6. No real FFmpeg, yt-dlp, Ollama or GPU integration tests run in CI.

## Next strategic direction

Validate version 0.5.0 on a representative video before adding visual ranking.

Possible next iteration after feedback:

- tune scene detection and crop stability;
- replace Haar face detection with a stronger local person/face detector;
- begin representative-frame quality scoring for beautiful views;
- alternatively stabilize Ollama cache fingerprints first.

## Collaboration protocol

When the archive is uploaded and the user says **“on fait la suite”**:

1. read `AGENTS.md`, this manifest, roadmap, architecture, README and tests;
2. identify one user-visible objective;
3. ask only strategic questions not already answered;
4. obtain objective validation unless the user explicitly orders immediate implementation;
5. implement, test, update documentation and rebuild the archive.

## Useful commands

```bash
py -3.11 -m venv .venv
source .venv/Scripts/activate
python -m pip install --upgrade pip setuptools wheel
pip install -e ".[dev,vision,transcription]"
bash scripts/check_project.sh
bash createTarGz.sh
```
