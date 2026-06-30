# Reelmaker roadmap

## Release 0.2.3 — publishable MVP

Status: ready after local checks.

- Clean source archive and Git ignore rules.
- CI tests on Python 3.10, 3.12, and 3.13.
- Reproducible project checks and a root `createTarGz.sh` archive script.
- Coding-assistant workflow and architecture guardrails.

Known debt accepted for this MVP:

- candidate cache has no full content/config fingerprint;
- one output directory should currently be used for one source project;
- `analyzer.py` and `renderer.py` are refactoring hotspots;
- vertical crop is static per reel.

## Iteration 1 — direct MP4 transcription foundation

Objective: accept `--source-video video.mp4` without requiring YouTube or an external SRT.

Planned slice:

1. Add a small `TranscriptionProvider` protocol.
2. Wrap the current subtitle-file/YouTube path as a provider.
3. Add a WhisperX provider behind an optional `transcription` dependency.
4. Produce normalized `transcript.json` plus SRT from the same internal model.
5. Cache transcription using source-file fingerprint + settings.

Acceptance criteria:

- a local MP4 produces usable French cues with word-level timing data retained;
- current YouTube/SRT modes still pass their tests;
- WhisperX is not imported when its mode is unused;
- Windows Git Bash setup is documented and reproducible.

Refactoring checkpoint: validate the provider boundary before adding prosody or diarization.

## Iteration 2 — safer spoken boundaries

Objective: reduce starts/ends in the middle of speech.

- Use word timestamps, VAD silences, punctuation, and speech energy.
- Add a boundary score and expose reasons in candidate JSON.
- Add optional pitch/prosody analysis only after a baseline with silence + text is measured.

Acceptance criterion: on a reference video, most selected cuts start and finish naturally without manual extension.

## Iteration 3 — scene-aware selection and framing

- Detect shot boundaries with PySceneDetect.
- Avoid cuts across transitions.
- Replace one static crop with per-shot crop decisions.
- Add face/person tracking only if the simpler approach is insufficient.

Refactoring checkpoint: separate scene analysis from rendering before adding visual ranking.

## Iteration 4 — relevant beautiful views / B-roll

- Extract representative frames per shot.
- Score technical quality: blur, exposure, stability.
- Add semantic relevance between transcript and shots.
- Insert B-roll only when relevance and timing thresholds are met.

## Iteration 5 — music

- Local licensed music library with tags.
- Intro/outro selection and automatic ducking under speech.
- Optional beat-aware cuts.
- Music remains disabled by default until rights and loudness rules are configured.
