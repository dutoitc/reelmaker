# Reelmaker roadmap

## Release 0.3.0 — direct MP4 transcription foundation

Status: implemented; unit-tested; real Windows/GPU validation pending.

Delivered:

- `TranscriptionProvider` boundary;
- SRT, YouTube and WhisperX providers;
- direct `--source-video` transcription;
- optional/lazy WhisperX dependency;
- transcript schema v1 with aligned words;
- source/settings fingerprint cache;
- Windows Git Bash installation documentation.

## Release 0.4.0 — safer spoken boundaries

Status: implemented and unit-tested; real-video validation pending.

Delivered:

1. Dedicated `boundary.py` module.
2. Pause derivation from WhisperX word timestamps.
3. Start/end scoring with silence, punctuation, cue boundaries and speaker changes.
4. Candidate cuts snapped to nearby natural boundaries.
5. Padding limited to actual silence.
6. Boundary method, score and reasons exposed in JSON and shortlist display.
7. Cue-based fallback for SRT/VTT and YouTube subtitles.
8. `--boundary-mode off` for objective before/after comparison.

Acceptance still to validate on a representative Xplore video:

- compare at least 10 candidates in `off` and `auto` modes;
- most selected cuts should start and finish naturally without manual extension;
- record whether bad endings are caused by missing punctuation, inaccurate word timing or actual prosody.

Do **not** add pitch/prosody before this measurement.

## Stabilization option after real-video test

- tune pause thresholds and search windows;
- add a generated boundary comparison report;
- improve mobile subtitle grouping if WhisperX cues are too long;
- fingerprint Ollama analysis caches before changing prompts substantially.

## Iteration 3 — scene-aware selection and framing

- Detect shot boundaries with PySceneDetect.
- Avoid cuts across transitions.
- Replace one static crop with per-shot crop decisions.
- Add face/person tracking only if the simpler approach is insufficient.

Refactoring checkpoint: separate scene analysis and crop decisions from rendering before visual ranking.

## Iteration 4 — relevant beautiful views / B-roll

- Extract representative frames per shot.
- Score blur, exposure and stability.
- Add semantic relevance between transcript and shots.
- Insert B-roll only above relevance and timing thresholds.

## Iteration 5 — music

- Local licensed music library with tags.
- Intro/outro selection and automatic ducking.
- Optional beat-aware cuts.
- Music disabled by default until rights and loudness rules are configured.
