# Reelmaker roadmap

## Release 0.3.0 — direct MP4 transcription

Status: implemented; real Windows/GPU validation pending.

- SRT, YouTube and WhisperX providers;
- direct MP4 transcription;
- word timestamps and fingerprinted transcript cache.

## Release 0.4.0 — safer spoken boundaries

Status: implemented; real-video comparison pending.

- pause-aware beginnings/endings;
- punctuation and cue fallback;
- `--boundary-mode auto|words|cues|off`.

## Release 0.5.0 — scene-aware framing

Status: implemented, unit-tested, and synthetic integration-tested.

Delivered:

1. PySceneDetect adapter and fingerprinted `scenes.json`.
2. `scenes` command for isolated detection tests.
3. Framing decisions extracted from rendering.
4. New `--crop-mode scene-smart`.
5. One smart crop per detected shot.
6. Merge of nearly identical adjacent crops.
7. Multi-shot FFmpeg rendering and final subtitle pass.
8. Framing plan exposed in reel metadata.

Acceptance to validate on Xplore footage:

- compare `smart` and `scene-smart` on at least three reels;
- no subject should be lost after a shot change;
- crop jumps are acceptable only on real cuts;
- detection should not split camera motion into excessive false scenes.

Useful tuning:

```bash
--scene-threshold 27
--scene-min-frames 15
--force-scene-detection
```

Lower threshold = more detected cuts. Increase it when pans or flashes create false cuts.

## Release 0.5.1 — reliable Ollama JSON

Status: implemented after the first real WhisperX/Xplore run.

- explicit `think=false` for Qwen 3 API requests;
- JSON Schema structured output for candidates, ranking and subtitle correction;
- structured calls use non-streaming mode and temperature 0;
- clear diagnostics for empty, truncated and rejected responses;
- existing transcript cache remains reusable after a failed candidate run.

## Iteration 4 — relevant beautiful views / B-roll

Refactoring checkpoint: keep frame extraction and scoring outside `renderer.py`.

- extract representative frames per shot;
- score blur, exposure and stability;
- add semantic relevance between transcript and shots;
- propose B-roll, but require human validation before automatic insertion.

## Iteration 5 — music

- local licensed music library with tags;
- intro/outro selection and automatic ducking;
- optional beat-aware cuts;
- disabled by default until rights and loudness rules are configured.

## Stabilization options

Can be selected before Iteration 4 if real tests expose issues:

- stronger face/person detector;
- scene threshold presets for interview/reportage/drone;
- fingerprint Ollama analysis caches;
- reduce scene-aware rendering time;
- improve WhisperX phone-caption regrouping.
