# Architecture

## Pipeline

```text
MP4 / SRT / YouTube
  -> TranscriptionProvider
  -> TranscriptDocument schema v1
  -> transcript chunks
  -> Ollama candidate generation
  -> boundary refinement and ranking
  -> human selection
  -> optional SceneDocument schema v1
  -> framing plan
  -> subtitle correction + FFmpeg render
```

## Module responsibilities

- `cli.py`: command orchestration and dependency wiring only.
- `models.py`: shared transcript/candidate dataclasses.
- `transcription.py`: SRT, YouTube and WhisperX providers.
- `transcript_io.py`: transcript JSON/SRT persistence and fingerprints.
- `subtitles.py`: parsing, chunking and reel subtitle normalization.
- `youtube.py`: yt-dlp adapter.
- `ollama_client.py`: Ollama HTTP adapter and JSON extraction.
- `analyzer.py`: candidate generation, ranking and human selection.
- `boundary.py`: pause/cue boundary scoring and cut snapping.
- `scene_analysis.py`: PySceneDetect adapter, scene schema and cache.
- `vision.py`: lightweight face/motion crop hints.
- `framing.py`: static or per-shot crop plan; no FFmpeg execution.
- `renderer.py`: executes framing plans, subtitles, end cards and FFmpeg rendering.

## Scene boundary

`scene_analysis.py` imports PySceneDetect lazily. The rest of the application consumes:

```text
SceneDocument schema v1
  source fingerprint
  detector settings fingerprint
  list of Scene(start, end)
```

The cache is reused only when the video fingerprint and detector settings match.

## Framing boundary

`framing.py` receives:

- source video;
- selected reel start/end;
- crop mode;
- optional detected scenes.

It returns a list of `FramingSegment` values with explicit source intervals and `CropHint` decisions. It never invokes FFmpeg.

Modes:

- `center`, `face`, `motion`, `smart`: one framing segment;
- `scene-smart`: one smart decision per detected shot, with similar adjacent crops merged.

The renderer executes one segment directly or renders multiple shot segments and concatenates them before subtitles are burned.

## Anti-spaghetti constraints

- no transcription implementation in `cli.py`;
- no WhisperX structures in `analyzer.py`;
- no PySceneDetect structures outside `scene_analysis.py`;
- no crop decision algorithms in `renderer.py`;
- no FFmpeg commands in `framing.py`;
- visual scoring/B-roll must be a new module, not additions to `renderer.py`;
- provider failures remain explicit; no cloud fallback;
- persisted structure changes require a schema version.

## Deliberate non-goals

- no pitch/prosody scoring yet;
- no visual aesthetic or semantic scoring yet;
- no B-roll insertion yet;
- no music workflow yet;
- no web framework while the CLI pipeline is evolving.
