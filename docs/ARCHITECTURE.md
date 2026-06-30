# Architecture

## Pipeline

```text
MP4 / SRT / YouTube
  -> TranscriptionProvider
  -> TranscriptDocument schema v1
  -> transcript chunks
  -> Ollama candidate generation (continuous or composite)
  -> segment-aware boundary refinement and ranking
  -> human or automatic selection
  -> optional SceneDocument schema v1
  -> framing plan (crop or fit-blur)
  -> subtitle correction and display splitting
  -> FFmpeg segment rendering / concatenation / subtitle burn
  -> render report
```

```text
PySide6 GUI
  -> QProcess: python -m reelmaker all --progress-json
  -> parses progress events
  -> displays progress, logs, elapsed time, ETA, and cancellation
```

## Module responsibilities

- `cli.py`: command orchestration, preflight, dependency wiring, and progress stage boundaries.
- `models.py`: shared transcript/candidate/selection/segment dataclasses.
- `transcription.py`: SRT, YouTube, and WhisperX providers.
- `transcript_io.py`: transcript JSON/SRT persistence and fingerprints.
- `subtitles.py`: parsing, chunking, source-segment remapping, normalization, and display splitting.
- `youtube.py`: yt-dlp adapter.
- `ollama_client.py`: Ollama HTTP adapter, explicit thinking control, structured-output contracts, and JSON extraction.
- `analyzer.py`: continuous/composite candidate generation, ranking, and human selection.
- `boundary.py`: pause/cue boundary scoring and segment-aware cut snapping.
- `scene_analysis.py`: PySceneDetect adapter, scene schema, and cache.
- `vision.py`: lightweight face/motion framing hints and fit-blur safety decisions.
- `framing.py`: static or per-shot framing plan; no FFmpeg execution.
- `subtitle_corrector.py`: conservative/basic and contextual Ollama correction with fingerprinted cache.
- `renderer.py`: executes framing/source-segment plans, subtitle burn, end cards, and FFmpeg rendering.
- `progress.py`: machine-readable progress events and local multi-run timing history.
- `gui.py`: optional PySide6 UI; starts the CLI as a subprocess and owns no pipeline logic.

## Composite reel boundary

A `ReelCandidate` or `ReelSelection` may contain ordered `ReelSegment` values. The fallback `start/end` fields remain for compatibility.

The renderer:

1. intersects each source interval with scene decisions;
2. renders source intervals in editorial order;
3. concatenates them;
4. remaps subtitle cues onto one continuous output timeline;
5. performs one final subtitle burn.

Hybrid Ollama caches use separate filenames from legacy contiguous caches.

## Ollama boundary

All model-assisted stages request JSON Schema structured outputs. The adapter sets `think=false`, temperature 0, and non-streaming mode. Prompts still describe the expected JSON, while Python validates and converts values.

Subtitle correction is fingerprinted by cues, selection, episode title, model, and schema. If contextual correction fails, conservative local cleanup is used and an error file is persisted.

## Scene and framing boundary

`scene_analysis.py` lazily imports PySceneDetect and exposes `SceneDocument schema v1`.

`framing.py` receives source intervals plus optional scenes and returns `FramingSegment` values. Each segment has a `CropHint` with a layout:

- `crop`: 9:16 source crop;
- `fit-blur`: complete horizontal frame over a blurred 9:16 background.

The fit-blur layout is used for ambiguous two-person shots and wide visuals when a safe subject crop is not available. Active-speaker detection is deliberately not guessed.

## Progress and timing boundary

The CLI emits prefixed JSON events only when `--progress-json` is enabled. Human-readable logs remain unchanged.

`TimingHistory` stores up to 20 normalized samples per configuration and estimates by median. The file lives outside the repository under local application data. Failure to read/write history must never fail a media run.

The current ETA is for the active stage. It is an estimate, not a scheduling guarantee.

## Render correctness boundary

- FFmpeg and required scene dependencies are checked before expensive processing.
- Requested burned subtitles with no cues are an error.
- Subtitle burn failure is an error unless `--allow-subtitle-fallback` is explicit.
- Output-file existence and non-zero size are validated.
- A run that renders zero successful reels exits as failure.
- Partial success writes the complete `render_report.json` and prints a warning.

## Anti-spaghetti constraints

- no transcription implementation in `cli.py`;
- no WhisperX structures in `analyzer.py`;
- no PySceneDetect structures outside `scene_analysis.py`;
- no crop decision algorithms in `renderer.py`;
- no FFmpeg commands in `framing.py`;
- no media processing in `gui.py`;
- visual scoring/B-roll must be a separate module;
- active-speaker tracking should be a separate subsystem if added;
- music requires renderer responsibility extraction first;
- provider failures remain explicit; no cloud fallback;
- persisted structure changes require a schema/version boundary.

## Deliberate non-goals for 0.6.0

- no pitch/prosody scoring;
- no active-speaker audio/face localization;
- no full-program global montage pass;
- no visual aesthetic/semantic scoring;
- no automatic B-roll insertion;
- no music workflow;
- no web server.
