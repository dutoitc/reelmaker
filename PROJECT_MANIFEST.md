# Project manifest — Reelmaker

## Snapshot

- Version: **0.4.0**
- Status: local CLI MVP with direct MP4 transcription and pause-aware spoken boundaries.
- Primary platform: Windows 11 + Git Bash.
- Reference runtime: Python 3.11 + NVIDIA RTX 4070 12 GB.
- Processing policy: local/offline by default.
- License: MIT.

## Product objective

Generate several usable 9:16 reels from a long-form CAPStv/Xplore Swiss TV video, with human validation before rendering.

## Current inputs

- local MP4 with optional WhisperX transcription;
- local SRT/VTT;
- YouTube subtitles;
- Ollama for candidate selection.

## Current pipeline

```text
MP4/SRT/YouTube
  -> TranscriptionProvider
  -> versioned TranscriptDocument with optional word timings
  -> overlapping transcript chunks
  -> Ollama candidate proposals
  -> boundary.py: word-pause or cue-based cut refinement
  -> local or Ollama ranking
  -> human validation
  -> static smart crop + subtitle correction
  -> FFmpeg render
```

## Stable decisions

- Keep Windows + Git Bash as the primary runtime.
- Keep all processing local by default.
- Preserve SRT/YouTube compatibility.
- Keep WhisperX optional and lazily imported.
- Keep JSON boundaries between expensive stages.
- Keep human validation before expensive rendering.
- Add one coherent feature slice per iteration.
- Keep prosody/pitch outside the baseline until pause-aware cuts are measured.

## Current defaults

- transcription mode: `auto`;
- WhisperX model: `large-v3`, language `fr`, batch size 4;
- boundary mode: `auto`, preferring word timestamps and falling back to cues;
- Ollama model: `qwen3:4b`;
- ranking: local;
- candidate chunks: 300 seconds with 20 seconds overlap;
- target reel duration: about 22 seconds;
- output: 1080x1920, H.264/AAC;
- crop: static `smart` mode;
- subtitle correction: `basic`.

## Version 0.4.0 delivered

- dedicated `boundary.py` module, removing boundary responsibility from `analyzer.py`;
- natural start/end scoring from word pauses, sentence punctuation, cue boundaries and speaker changes;
- automatic SRT/VTT cue fallback;
- safe padding clamped to available silence so it does not include the next spoken word;
- boundary method, score and reasons in candidate JSON;
- `--boundary-mode auto|words|cues|off` for comparison;
- small boundary-quality signal in local ranking;
- complete Windows/Git Bash initialization instructions in README;
- 26 passing unit tests.

## Validation status

Verified in the project environment:

- compilation succeeds;
- 26 unit tests pass;
- old SRT/YouTube and transcription tests remain green;
- word pauses select natural boundaries in synthetic tests;
- padding does not cross into the next spoken word;
- cue fallback remains compatible without WhisperX word timestamps.

Still requires a real Windows integration test:

- install WhisperX/CUDA 12.8 in Python 3.11;
- transcribe one representative French MP4 on the RTX 4070;
- compare `--boundary-mode off` and `auto`;
- inspect at least 10 proposed starts and ends;
- record common failures before considering pitch/prosody.

## Accepted technical debt

1. Ollama candidate/ranking caches are not fully fingerprinted by transcript, prompt and boundary version.
2. `renderer.py` remains a refactoring hotspot before scene-aware work.
3. WhisperX aligned segments may need better phone-caption regrouping.
4. Crop remains static for each reel.
5. No real FFmpeg, yt-dlp, Ollama or GPU integration tests run in CI.

## Next strategic direction

Stabilize version 0.4.0 on a real Xplore video. Depending on the measured result:

- tune pause thresholds and search windows;
- add a compact boundary comparison report;
- only then consider pitch/prosody;
- otherwise move to scene-aware selection with PySceneDetect.

Before scene-aware work, propose a small extraction of visual analysis decisions from `renderer.py`.

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
