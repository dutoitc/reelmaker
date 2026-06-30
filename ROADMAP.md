# Reelmaker roadmap

## Releases delivered

### 0.3.0 — direct MP4 transcription

- SRT, YouTube, and WhisperX providers;
- direct MP4 input;
- word timestamps and fingerprinted transcript cache.

### 0.4.0 — safer spoken boundaries

- pause-aware beginnings/endings;
- punctuation and cue fallback;
- `--boundary-mode auto|words|cues|off`.

### 0.5.0 — scene-aware framing

- PySceneDetect adapter and `scenes.json`;
- isolated `framing.py` decisions;
- `--crop-mode scene-smart`;
- per-shot FFmpeg rendering and final subtitle pass.

### 0.5.1 — reliable Ollama JSON

- explicit `think=false`;
- JSON Schema outputs;
- deterministic non-streaming structured requests;
- actionable parsing diagnostics.

### 0.6.0 — usable desktop workflow and quality safeguards

- optional PySide6 Windows GUI;
- progress JSON events and local multi-run ETA history;
- hybrid two/three-passage editorial montage;
- composite segment/subtitle rendering;
- stronger natural endings;
- fit-blur preservation for two-person/wide shots;
- contextual subtitle correction by default;
- complete subtitle display and explicit render failure rules;
- dependency preflight and zero-video failure;
- local `run_*` scripts ignored and excluded from archives.

## Validation gate for 0.6.x

Before another large feature, test the same real reportages through:

```bash
--composition-mode contiguous
--composition-mode hybrid
--crop-mode smart
--crop-mode scene-smart
--subtitle-correction ollama
```

Record observations for:

- first/last spoken words;
- grammatical/substantive subtitle accuracy;
- two-person interviews;
- landscapes, monuments, slides, and full-screen wide visuals;
- editorial coherence of recomposed reels;
- missing/failed render outputs;
- ETA accuracy after two or three runs.

## Candidate iteration 0.6.1 — observed defect stabilization

Only after real-video feedback:

- tune incomplete-ending thresholds;
- tune fit-blur vs crop decisions;
- improve subtitle correction cache/errors;
- improve GUI diagnostics and progress granularity;
- fingerprint candidate caches more completely if stale results appear.

## Candidate iteration 0.7 — active speaker and person tracking

Refactoring checkpoint: do not add this directly to `vision.py` if it becomes a full tracking subsystem.

- stronger face/person detector;
- track people across a shot;
- use audio/speaker timing where possible;
- crop the active speaker only when confidence is high;
- preserve both people otherwise.

## Candidate iteration 0.8 — global editorial montage

- summarize topics across all transcript chunks;
- propose complementary passages across the complete programme;
- require coherent hook/explanation/conclusion;
- reject repetitions and factual discontinuities;
- expose source segments clearly for review.

## Candidate iteration 0.9 — beautiful views and B-roll

- representative frames per scene;
- blur/exposure/stability scores;
- semantic relevance between transcript and shots;
- human validation before automatic insertion.

## Candidate iteration 1.0 — music

Refactor renderer responsibilities first.

- local licensed music library with tags;
- automatic ducking under speech;
- optional beat-aware cuts;
- loudness and rights rules;
- disabled by default until configured.
