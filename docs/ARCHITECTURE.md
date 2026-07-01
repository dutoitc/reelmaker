# Architecture

## Pipeline

```text
MP4 / SRT / YouTube
  -> TranscriptionProvider
  -> TranscriptDocument schema v1
  -> transcript chunks
  -> Ollama chunk candidate generation
  -> optional full-transcript composite generation
  -> segment-aware boundary refinement
  -> ranking and selection
  -> optional SceneDocument schema v1
  -> framing plan (crop or fit-blur)
  -> embedded-text analysis / subtitle placement
  -> dictionary + contextual subtitle correction
  -> display-safe subtitle splitting
  -> FFmpeg rendering / concatenation / subtitle burn / end card
  -> optional Final Cut Pro 7 XML export referencing original media
  -> render report
```

```text
PySide6 GUI
  -> QProcess: python -m reelmaker all --progress-json
  -> parses progress events
  -> displays progress, logs, elapsed time, ETA, and cancellation
```

## Module responsibilities

- `cli.py`: orchestration, preflight, dependency wiring, and progress stage boundaries.
- `models.py`: shared transcript/candidate/selection/segment dataclasses.
- `transcription.py`: SRT, YouTube, and WhisperX providers.
- `transcript_io.py`: transcript JSON/SRT persistence and fingerprints.
- `subtitles.py`: parsing, chunking, source-segment remapping, normalization, and lossless display splitting.
- `correction_dictionary.py`: packaged/custom JSON dictionaries and deterministic text substitutions.
- `youtube.py`: yt-dlp adapter.
- `ollama_client.py`: Ollama HTTP adapter, thinking control, structured-output contracts, and JSON extraction.
- `analyzer.py`: chunk/global candidate generation, ranking, and human selection.
- `boundary.py`: pause/cue scoring and controlled complete-sentence extensions.
- `scene_analysis.py`: PySceneDetect adapter, scene schema, and cache.
- `visual_text.py`: lightweight embedded-text band analysis; no OCR or semantic interpretation.
- `vision.py`: lightweight face/motion hints and full-frame safety decisions.
- `framing.py`: static or per-shot framing plan; no FFmpeg execution.
- `subtitle_corrector.py`: conservative/basic and contextual Ollama correction with dictionary-aware cache.
- `subtitle_layout.py`: balanced ASS line layout, safe-width estimation, and dynamic font fitting.
- `renderer.py`: executes framing/source-segment plans, subtitle burn, end cards, FFmpeg rendering, and successful-artifact cleanup.
- `progress.py`: machine-readable progress events and local multi-run timing history.
- `davinci_xml.py`: ffprobe media adapter and Final Cut Pro 7 XML timeline export; no rendering logic.
- `gui_style.py`: PySide6 visual theme only.
- `gui.py`: optional PySide6 UI; starts the CLI as a subprocess and owns no media logic.

## Editorial boundaries

Chunk generation discovers local continuous/composite ideas. In hybrid quality mode, a second full-transcript request proposes only two/three-segment mini-stories spanning distant parts of the programme. It is skipped when the transcript exceeds a conservative character limit.

Candidate/ranking caches are versioned by filename (`impact_v2`) to avoid silently reusing weaker 0.6.x prompt results.

## Subtitle correctness boundary

- correction order: conservative typography -> packaged/custom dictionary -> optional contextual Ollama correction -> final dictionary pass;
- cache fingerprint includes cues, selection, episode, model, schema, and dictionary content;
- long captions are split proportionally without deleting words;
- ASS output never adds ellipsis or discards overflow text;
- subtitle cues use balanced lines and estimated rendered width; font size is reduced only when needed to fit the safe area;
- automatic position chooses top/bottom from sampled embedded-text bands;
- manual `top` or `bottom` remains available because the detector is not OCR.

## Scene and framing boundary

Each `CropHint` has one layout:

- `crop`: 9:16 source crop;
- `fit-blur`: complete horizontal frame over a blurred 9:16 background.

`fit-blur` is mandatory for detected title cards/embedded text and for two similarly important faces. A dominant face may still be cropped. Active-speaker identity is deliberately not guessed.

## Complete-sentence boundary

The nominal `max_duration` remains the editorial target. `boundary.py` may extend the final cut by `max_end_extension` (default 2 seconds) to reach punctuation, a clear pause, speaker change, or transcript end. Beyond that hard extension, the candidate is marked incomplete/too long rather than expanded indefinitely.

## Progress and timing boundary

The CLI emits prefixed JSON events only with `--progress-json`. `TimingHistory` stores up to 20 normalized samples per configuration and estimates by median. The file lives outside the repository under local application data and contains timing data only.

## Render correctness boundary

- runtime dependencies are checked before expensive processing;
- requested subtitles with no cues are an error;
- subtitle burn failure is an error unless explicit fallback is enabled;
- output existence/non-zero size is validated;
- zero successful reels fails the run;
- partial success writes a complete report;
- successful final renders remove temporary content/end-card MP4, ASS, and concat files unless explicitly retained;
- failed renders preserve intermediates for diagnosis;
- a 1.5-second `Voir sur YouTube` card is enabled by default and can be disabled.

## Anti-spaghetti constraints

- no transcription implementation in `cli.py`;
- no WhisperX structures in `analyzer.py`;
- no PySceneDetect structures outside `scene_analysis.py`;
- no crop algorithms in `renderer.py`;
- no FFmpeg commands in `framing.py`;
- no media processing in `gui.py`;
- no DaVinci XML construction in `renderer.py`;
- visual aesthetic/B-roll scoring must be a separate module;
- active-speaker tracking must be a separate subsystem;
- music requires renderer responsibility extraction first;
- provider failures remain explicit; no cloud fallback;
- persisted structure changes require a schema/version boundary.

## Deliberate non-goals for 0.8.1

- no OCR transcription of text already present in images;
- no pitch/prosody scoring;
- no active-speaker audio/face localisation;
- no visual aesthetic/semantic B-roll scoring;
- no automatic B-roll insertion;
- no music workflow;
- no web server.
